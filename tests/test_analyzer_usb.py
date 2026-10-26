# SPDX-License-Identifier: MIT
import binascii
import ctypes
import struct
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
        cls.lib.fixture_frame.argtypes = [ctypes.c_void_p]
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

    def test_reset_disabled_and_replay(self):
        self.assertFalse(self.client.reset_status()['enabled'])
        with self.assertRaisesRegex(RuntimeError, 'accessory unavailable'):
            self.client.command(8)
        self.lib.fixture_reset_enable()
        result = self.client.command(8, 0, 0)
        self.assertEqual(result['reset_id'], 1)
        self.assertEqual(result['reset_state'], 2)
        with self.assertRaisesRegex(RuntimeError, 'token changed'):
            self.client.command(8, 0, 0)
        self.assertEqual(self.lib.fixture_reset_calls(), 1)
        # No polling or USB servicing required to release the command output.
        self.lib.fixture_advance(100001)
        self.assertFalse(self.lib.fixture_reset_active())
        self.lib.fixture_poll()
        self.assertEqual(self.client.reset_status()['reset_state'], 3)

    def test_arm_reset_waits_for_run_and_settle(self):
        self.lib.fixture_reset_enable()
        result = self.client.command(9, 0, 0)
        self.assertEqual(result['generation'], 1)
        self.assertEqual(result['reset_state'], 1)
        self.lib.fixture_poll()
        self.assertEqual(self.lib.fixture_reset_calls(), 0)
        self.lib.fixture_advance(100)
        self.lib.fixture_step()
        self.lib.fixture_advance(999)
        self.lib.fixture_poll()
        self.assertEqual(self.lib.fixture_reset_calls(), 0)
        self.lib.fixture_advance(1)
        self.lib.fixture_poll()
        self.assertEqual(self.lib.fixture_reset_calls(), 1)
        self.assertEqual(self.client.reset_status()['reset_state'], 2)
        with self.assertRaises(RuntimeError):
            self.client.arm()
        with self.assertRaises(RuntimeError):
            self.client.configure_trigger()
        self.lib.fixture_disconnect()
        self.assertFalse(self.lib.fixture_reset_active())
        result = self.client.reset_status()
        self.assertEqual((result['reset_state'], result['reason']), (4, 1))
        # Reconnection and status queries do not issue a second pulse.
        self.assertEqual(self.lib.fixture_reset_calls(), 1)

    def test_arm_reset_cancel_timeout_stop_and_error(self):
        self.lib.fixture_reset_enable()
        self.client.command(9, 0, 0)
        self.lib.fixture_advance(100001)
        self.lib.fixture_poll()
        self.assertEqual(self.client.reset_status()['reason'], 2)
        self.assertEqual(self.lib.fixture_reset_calls(), 0)
        self.client.command(3, 1)
        self.complete()
        self.client.command(9, 1, 1)
        self.client.command(3, 2)
        self.assertEqual(self.client.reset_status()['reason'], 4)
        self.complete()
        self.client.command(9, 2, 2)
        self.lib.fixture_error()
        self.lib.fixture_poll()
        self.assertEqual(self.client.reset_status()['reason'], 2)
        self.assertEqual(self.lib.fixture_reset_calls(), 0)

    def test_host_waits_for_reset_completion(self):
        from unittest.mock import patch
        self.lib.fixture_reset_enable()
        def advance(_):
            self.lib.fixture_advance(10000)
            self.lib.fixture_step()
        with patch.object(usb.time, 'sleep', advance):
            result = self.client.arm_reset()
        self.assertEqual((result['reset_state'], result['generation']), (3, 1))
        self.assertGreater(result['released_observed_us32'], result['asserted_us32'])

    def test_reset_backend_failure_consumes_token(self):
        self.lib.fixture_reset_enable()
        self.lib.fixture_reset_fail()
        with self.assertRaises(RuntimeError):
            self.client.command(8, 0, 0)
        result = self.client.reset_status()
        self.assertEqual((result['reset_id'], result['reset_state'], result['reason']), (1, 4, 3))
        with self.assertRaisesRegex(RuntimeError, 'token changed'):
            self.client.command(8, 0, 0)

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

    def packet(self, payload, terminal=False, corrupt=False):
        prefix = bytes((2 if terminal else 1, 1, 1 if terminal else 0, 0)) + payload
        crc = binascii.crc_hqx(prefix, 0xffff) ^ int(corrupt)
        self.lib.fixture_frame(prefix + struct.pack('<H', crc))

    def event(self, seq, kind=4, address=None, data=0, corrupt=False):
        record = trace.Cycle(kind, 0, data, seq if address is None else address, 0, 4, seq*10, seq)
        self.packet(record.encode(), corrupt=corrupt)
        return record

    def finish(self, sent, dropped=0, filtered=0):
        self.packet(struct.pack('<4I', dropped, filtered, sent, 0x170), terminal=True)
        self.assertEqual(self.client.status()['state'], 4)

    def downloaded(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'capture'
            self.client.download(path)
            return trace.decode(path.read_bytes())

    def test_trigger_ring_masks_boundary_and_tail(self):
        self.client.configure_trigger(1, 16, 0xffff000a, 0xff55, 3, 2)
        self.client.arm()
        for seq in range(10): self.event(seq, data=0x55)
        self.event(10, data=0)  # wrong data must not match
        self.event(11, kind=5, address=10, data=0x55)  # wrong kind
        self.event(12, address=10, data=0x55)
        self.assertEqual(self.client.trigger_status()['trigger_index'], 3)
        self.event(13); self.event(14)
        self.assertTrue(self.lib.fixture_stopping())
        self.event(15); self.event(16)  # already in FPGA FIFO when stop took effect
        self.finish(17)
        h, rows = self.downloaded()
        self.assertEqual([r.sequence for r, _ in rows], list(range(9, 15)))
        self.assertEqual(h.trigger[6:], (1, 3, 12, 11, 2, 1))
        self.assertEqual((h.dropped, h.filtered), (0, 11))

    def test_trigger_early_zero_windows_and_reset(self):
        for kinds, kind, pre in [(16, 4, 0), (64, 6, 8), (256, 8, 0)]:
            self.lib.fixture_init()
            self.client.configure_trigger(1, kinds, 0, 0, pre, 0); self.client.arm()
            self.event(0, kind=kind, address=0)
            self.finish(1)
            h, rows = self.downloaded()
            self.assertEqual(len(rows), 1)
            self.assertEqual(h.trigger[7], 0)
            self.assertEqual(h.trigger[-1], 1)

    def test_manual_stop_before_or_after_trigger(self):
        self.client.configure_trigger(1, 16, 0xffff0064, 0, 3, 5); self.client.arm()
        for seq in range(10): self.event(seq)
        self.client.command(3, 1)
        self.event(10, address=100)  # drain must not fire a trigger after manual stop
        self.finish(11)
        h, rows = self.downloaded()
        self.assertEqual([r.sequence for r, _ in rows], [7, 8, 9])
        self.assertEqual(h.trigger[6:9], (0, 0xffffffff, 0xffffffff))
        self.assertEqual(h.trigger[-1], 2)
        self.client.configure_trigger(1, 16, 0, 0, 0, 5); self.client.arm()
        self.event(0); self.event(1); self.client.command(3, 2)
        self.event(2); self.finish(3)
        h, rows = self.downloaded()
        self.assertEqual(len(rows), 2)
        self.assertEqual(h.trigger[-2:], (1, 2))

    def test_trigger_crc_duplicate_and_overflow_metadata(self):
        self.client.configure_trigger(1, 16, 0xffff0004, 0, 2, 1); self.client.arm()
        self.event(0); self.event(3)  # FPGA dropped sequences 1 and 2
        self.event(4, corrupt=True)
        self.assertFalse(self.client.trigger_status()['triggered'])
        self.event(4); self.event(4)  # lost final ACK replay
        self.event(5); self.finish(4, dropped=2)
        h, rows = self.downloaded()
        self.assertEqual([r.sequence for r, _ in rows], [0, 3, 4, 5])
        self.assertEqual(h.dropped, 2)
        self.assertEqual(self.client.status()['retries'], 1)

    def test_trigger_config_atomic_and_active_rejection(self):
        valid = (1, 16, 0xffff0005, 0, 2, 1)
        self.client.configure_trigger(*valid)
        for config in [(2, 16, 0, 0, 0, 0), (1, 2, 0, 0, 0, 0),
                       (1, 16, 0, 0x10000, 0, 0), (1, 16, 0, 0, 0xffffffff, 1)]:
            with self.assertRaises(RuntimeError): self.client.configure_trigger(*config)
        request = usb.REQUEST.pack(b'P17Q', 1, 5, 0, 123, 0, 0, 24)
        self.port.write(request + struct.pack('<2I', 1, 64))
        self.lib.fixture_disconnect()
        self.client.arm()
        self.assertEqual(tuple(self.client.trigger_status()[f] for f in usb.TRIGGER_FIELDS[:6]), valid)
        with self.assertRaises(RuntimeError): self.client.configure_trigger()
        self.lib.fixture_disconnect()
        self.assertEqual(self.client.trigger_status()['pre'], 2)

    def test_trigger_interrupted_download_restart(self):
        self.client.configure_trigger(1, 16, 0xffff005a, 0, 75, 10); self.client.arm()
        for seq in range(101): self.event(seq)
        self.finish(101)
        original = self.client.command
        def interrupt(cmd, *args):
            if cmd == 4 and args[1] >= 1024: self.port.truncate = True
            return original(cmd, *args)
        self.client.command = interrupt
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'capture'
            with self.assertRaises(TimeoutError): self.client.download(path)
            self.assertEqual(list(Path(d).iterdir()), [])
        self.lib.fixture_disconnect(); self.port.truncate = False; self.client.command = original
        h, rows = self.downloaded()
        self.assertEqual([r.sequence for r, _ in rows], list(range(15, 101)))
        self.assertEqual(h.trigger[7], 75)

    def test_trigger_stop_during_initial_clear(self):
        self.client.configure_trigger(1, 16, 0, 0, 0, 0); self.client.arm()
        self.assertEqual(self.client.stop()['state'], 4)
        h, rows = self.downloaded()
        self.assertEqual(rows, [])
        self.assertEqual(h.trigger[6], 0)
        self.assertEqual(h.trigger[-1], 2)

    def test_trigger_file_metadata_and_cli(self):
        self.client.configure_trigger(1, 16, 0, 0, 0, 0); self.client.arm()
        self.event(0); self.finish(1)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'capture'; csv = Path(d)/'trace.csv'
            self.client.download(path)
            subprocess.run([sys.executable, str(ROOT/'tools/cycle_trace.py'), str(path), '--csv', str(csv)], check=True, capture_output=True)
            self.assertIn('trigger', csv.read_text().splitlines()[0])
            self.assertTrue(csv.read_text().splitlines()[1].endswith(',1'))
            original = path.read_bytes()
            for offset, value in [(32, 0), (60, 4), (64, 10), (68, 1), (72, 1), (76, 0)]:
                changed = bytearray(original); struct.pack_into('<I', changed, offset, value)
                with self.assertRaises(ValueError): trace.decode(changed)
