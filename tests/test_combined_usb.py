# SPDX-License-Identifier: MIT
import binascii
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_controller_usb import Port, usb, ROOT


class CombinedUSBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        lib = Path(cls.build.name)/'combined.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined', '-fno-sanitize-recover=all', '-DP1715_HOST_SIM', '-DP1715_COMBINED=1',
                        '-Itools/firmware_host', 'tests/controller_usb_fixture.c',
                        'firmware/controller_usb.c', 'firmware/service.c', 'firmware/store.c',
                        'firmware/combined.c', 'firmware/analyzer.c',
                        'model/controller.c', 'tools/firmware_host/host_hal.c', '-o', str(lib)], cwd=ROOT, check=True)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.fixture_read.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        cls.lib.fixture_read.restype = ctypes.c_size_t

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.lib.fixture_init(1)
        self.client = usb.Client(Port(self.lib))
        self.assertEqual(self.lib.fixture_extension_read(14), 0xa7)

    def start(self):
        self.assertEqual(self.client.command(3)['capability'], 1)
        self.assertEqual(self.lib.fixture_extension_read(12), 3)
        self.assertEqual(self.lib.fixture_extension_read(12), 1)

    def frame(self, data, corrupt=False):
        packet = bytes(data) + (binascii.crc_hqx(bytes(data), 0xffff) ^ int(corrupt)).to_bytes(2, 'little')
        for i, byte in enumerate(packet):
            self.lib.fixture_extension_write(15 if i else 13, byte)

    def test_capture_requires_safe_eject_and_roundtrips(self):
        self.start()
        data = bytearray(20);data[:2] = b'\x01\x01';data[4:6] = b'\x40\xa5'
        self.frame(data)
        self.assertEqual(self.client.command(5)['records'], 1)
        self.client.command(4)
        self.assertEqual(self.lib.fixture_extension_read(12), 2)
        terminal = bytearray(20);terminal[:3] = b'\x02\x01\x01';terminal[12] = 1;terminal[16:18] = b'\x70\x01'
        self.frame(terminal)
        self.assertEqual(self.client.command(5)['capture_state'], 4)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'trace.p1715'
            with self.assertRaises(RuntimeError): self.client.trace_save(path)
            self.client.eject()
            self.assertEqual(self.client.trace_save(path)['bytes'], 48)
            capture = path.read_bytes()
            self.assertEqual(capture[:8], b'P1715CY\0')
            self.assertEqual(capture[32:], bytes(data[4:]))
            with self.assertRaises(FileExistsError): self.client.trace_save(path)

    def test_bad_frame_fails_capture_without_ejecting_controller(self):
        self.start()
        data = bytearray(20);data[:2] = b'\x01\x01'
        self.frame(data, corrupt=True)
        trace = self.client.command(5)
        self.assertEqual((trace['capture_state'], trace['crc_errors']), (5, 1))
        self.assertEqual(self.client.status()['shutdown'], 0)
        with self.assertRaises(RuntimeError): self.client.command(6)

    def test_cancel_before_arm_finishes_empty_capture(self):
        self.client.command(3)
        self.assertEqual(self.client.command(4)['capture_state'], 4)
        self.assertEqual(self.lib.fixture_extension_read(12), 2)
        self.assertEqual(self.lib.fixture_extension_read(12), 0)


if __name__ == '__main__':
    unittest.main()
