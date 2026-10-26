# SPDX-License-Identifier: MIT
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import analyzer_usb as usb
import cycle_trace as trace


class Port:
    def __init__(self, lib):
        self.lib = lib
        self.truncate = False
        self.corrupt = False

    def write(self, data):
        for b in data:
            self.lib.fixture_feed(b)
        return len(data)

    def read(self, n):
        if self.truncate:
            return b''
        buf = (ctypes.c_uint8 * min(n, 7))()
        size = self.lib.fixture_read(buf, len(buf))
        data = bytes(buf[:size])
        if self.corrupt and data:
            data = bytes([data[0] ^ 1]) + data[1:]
        return data


class AnalyzerUSBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        library = Path(cls.build.name)/'usb.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        'tests/analyzer_usb_fixture.c', 'firmware/analyzer_usb.c',
                        'firmware/analyzer.c', '-o', str(library)], cwd=ROOT, check=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.fixture_read.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        cls.lib.fixture_read.restype = ctypes.c_size_t
        cls.lib.fixture_complete.argtypes = [ctypes.c_void_p, ctypes.c_size_t]

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.lib.fixture_init()
        self.port = Port(self.lib)
        self.client = usb.Client(self.port)
        self.blob = trace.Header(50000000, 100, capture_mask=0x170).encode() + b''.join(
            trace.Cycle(4, 0, i, i, 0, 4, i*10, i).encode() for i in range(100))

    def complete(self):
        self.assertEqual(self.lib.fixture_complete(self.blob, len(self.blob)), 0)

    def test_lifecycle_and_exact_download(self):
        self.assertEqual(self.client.status()['state'], 0)
        self.assertEqual(self.client.arm()['generation'], 1)
        with self.assertRaises(RuntimeError):
            self.client.arm()
        self.client.command(3, 1)
        self.assertTrue(self.lib.fixture_stopping())
        self.complete()
        self.assertEqual(self.client.stop()['state'], 4)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'capture.p1715'
            self.client.download(path)
            self.assertEqual(path.read_bytes(), self.blob)
            with self.assertRaises(FileExistsError):
                self.client.download(path)

    def test_ranges_and_capture_id(self):
        self.client.arm(); self.complete()
        for gen, offset, length in [(0, 0, 32), (1, 0, 0), (1, 0, 1025),
                                     (1, 0xffffffff, 16), (1, len(self.blob)-1, 2)]:
            with self.assertRaises(RuntimeError):
                self.client.command(4, gen, offset, length)
        self.assertEqual(self.client.command(4, 1, len(self.blob)-1, 1), self.blob[-1:])
        self.client.arm()
        with self.assertRaises(RuntimeError):
            self.client.command(3, 1)

    def test_disconnect_partial_request_and_response(self):
        self.client.arm()
        self.port.write(b'P17Q\x01')
        self.lib.fixture_disconnect()
        self.assertEqual(self.client.status()['generation'], 1)
        self.port.write(usb.REQUEST.pack(b'P17Q', 1, 1, 0, 55, 0, 0, 0))
        self.port.read(7)
        self.lib.fixture_disconnect()
        self.assertEqual(self.client.status()['state'], 1)
        self.complete()
        self.assertEqual(self.client.command(4, 1, 0, 32), self.blob[:32])

    def test_invalid_commands_and_noise(self):
        self.port.write(b'noisePP')
        self.assertEqual(self.client.status()['state'], 0)
        for cmd in (0, 5, 255):
            with self.assertRaises(RuntimeError):
                self.client.command(cmd)
        with self.assertRaises(RuntimeError):
            self.client.command(1, offset=1)
        # Unsupported version/reserved bytes are rejected, not executed.
        for version, reserved in ((2, 0), (1, 1)):
            self.port.write(usb.REQUEST.pack(b'P17Q', version, 2, reserved, 1, 0, 0, 0))
            response = self.client.exact(28)
            self.assertEqual(response[6], 1)
            self.assertEqual(self.client.status()['state'], 0)

    def test_unfinished_or_failed_not_exported(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'capture'
            for state in ('active', 'error'):
                if state == 'active': self.client.arm()
                else: self.lib.fixture_error()
                with self.assertRaises(RuntimeError): self.client.download(path)
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_interrupted_download_not_published_and_can_restart(self):
        self.client.arm(); self.complete()
        original = self.client.command
        def interrupt(cmd, *args):
            if cmd == 4 and args[1] >= 1024:
                self.port.truncate = True
            return original(cmd, *args)
        self.client.command = interrupt
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'capture'
            with self.assertRaises(TimeoutError): self.client.download(path)
            self.assertEqual(list(Path(d).iterdir()), [])
            self.lib.fixture_disconnect(); self.port.truncate = False
            self.client.command = original
            self.client.download(path)
            self.assertEqual(path.read_bytes(), self.blob)

    def test_crc_and_invalid_capture_rejected(self):
        self.port.corrupt = True
        with self.assertRaises(ValueError): self.client.status()
        self.port.corrupt = False; self.lib.fixture_disconnect()
        self.client.arm(); self.complete()
        original = self.port.read
        def corrupt_crc(n):
            data = original(n)
            if n == 7:  # last 7 bytes of response header, including CRC
                return data[:-1] + bytes([data[-1] ^ 1])
            return data
        self.port.read = corrupt_crc
        with self.assertRaisesRegex(ValueError, 'CRC'): self.client.status()
        self.port.read = original; self.lib.fixture_disconnect()
        self.blob = b'BADMAGIC' + self.blob[8:]; self.complete()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): self.client.download(Path(d)/'capture')
            self.assertEqual(list(Path(d).iterdir()), [])

    @unittest.skipUnless(os.environ.get('P1715_USB_CAPTURE'), 'optional external compact capture')
    def test_external_capture_download(self):
        self.blob = Path(os.environ['P1715_USB_CAPTURE']).read_bytes()
        self.client.arm(); self.complete()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'capture.p1715'
            self.client.download(path)
            self.assertEqual(path.read_bytes(), self.blob)
