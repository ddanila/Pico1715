# SPDX-License-Identifier: MIT
import binascii
import ctypes
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import controller_usb as usb


def request(cmd=1, req=1, version=1):
    raw = struct.pack('<4sBBHI', b'P1CQ', version, cmd, 0, req)
    return raw + struct.pack('<I', binascii.crc32(raw))


class Port:
    def __init__(self, lib):
        self.lib = lib
        self.corrupt = self.truncate = False
        self.flush_storage = False

    def write(self, data):
        for b in data:
            self.lib.fixture_feed(b)
        self.lib.fixture_poll()
        return len(data)

    def read(self, size):
        if self.truncate:
            return b''
        if self.flush_storage:
            self.lib.fixture_storage()
        out = (ctypes.c_uint8 * min(size, 7))()
        n = self.lib.fixture_read(out, len(out))
        data = bytes(out[:n])
        if self.corrupt and data and (self.corrupt is True or len(data) == 4):
            data = data[:-1] + bytes([data[-1] ^ 1])
        return data


class ControllerUSBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        lib = Path(cls.build.name)/'controller.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined', '-fno-sanitize-recover=all', '-DP1715_HOST_SIM',
                        '-Itools/firmware_host', 'tests/controller_usb_fixture.c',
                        'firmware/controller_usb.c', 'firmware/service.c', 'firmware/store.c',
                        'model/controller.c', 'tools/firmware_host/host_hal.c', '-o', str(lib)],
                       cwd=ROOT, check=True)
        cls.adapter = Path(cls.build.name)/'adapter'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined', '-fno-sanitize-recover=all', '-DP1715_HOST_SIM',
                        '-Itools/firmware_host', '-Itests/usb_stub', 'tests/controller_usb_device_test.c',
                        'tests/controller_usb_fixture.c', 'firmware/controller_usb_device.c',
                        'firmware/controller_usb.c', 'firmware/service.c', 'firmware/store.c',
                        'model/controller.c', 'tools/firmware_host/host_hal.c', '-o', str(cls.adapter)],
                       cwd=ROOT, check=True)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.fixture_read.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        cls.lib.fixture_read.restype = ctypes.c_size_t

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.lib.fixture_init(1)
        self.port = Port(self.lib)
        self.client = usb.Client(self.port)

    def feed(self, raw):
        for b in raw:
            self.lib.fixture_feed(b)

    def test_status_and_snapshot(self):
        self.lib.fixture_big_counters()
        self.feed(request())
        self.lib.fixture_core()
        # The immutable response is a snapshot, even if live counters later change.
        self.lib.fixture_clear_counters()
        self.lib.fixture_poll_usb()
        raw = bytearray()
        while chunk := self.port.read(1024):
            raw.extend(chunk)
        self.assertEqual(len(raw), 132)
        status = dict(zip(usb.FIELDS, struct.unpack('<10I9Q', raw[16:-4])))
        self.assertEqual(status['requests'], 0x123456789abcdef0)
        self.assertEqual(status['overruns'], 0xfedcba9876543210)
        self.assertEqual(status['state'], 2)
        self.assertEqual(struct.unpack('<I', raw[-4:])[0], binascii.crc32(raw[:-4]))

    def test_eject_dirty_and_repeat(self):
        self.lib.fixture_dirty()
        self.assertEqual(self.client.status()['dirty_blocks'], 2)
        self.port.flush_storage = True
        result = self.client.eject()
        self.assertEqual(result['shutdown'], 2)
        self.assertEqual(self.lib.fixture_persisted(), 1)
        self.assertEqual(self.client.eject()['shutdown'], 2)

    def test_readonly_and_startup_failure(self):
        self.lib.fixture_init(0)
        self.assertEqual(self.client.status()['write_policy'], 0)
        self.assertEqual(self.client.eject()['shutdown'], 2)
        self.lib.fixture_init(2)
        self.assertEqual(self.client.status()['state'], 0xe2)
        with self.assertRaisesRegex(RuntimeError, 'cannot accept'):
            self.client.eject()

    def test_storage_failure_unsafe(self):
        self.lib.fixture_dirty()
        self.lib.fixture_fail()
        self.port.flush_storage = True
        with self.assertRaisesRegex(RuntimeError, 'UNSAFE'):
            self.client.eject()
        result = self.client.status()
        self.assertEqual(result['shutdown'], 3)
        self.assertEqual(result['shutdown_reason'], 1)
        self.assertTrue(result['storage_error'])
        self.assertTrue(result['dirty_blocks'])

    def test_disconnect_before_and_after_submit(self):
        self.feed(request(2)[:10])
        self.lib.fixture_disconnect()
        self.assertEqual(self.client.status()['shutdown'], 0)
        self.lib.fixture_dirty()
        self.feed(request(2))
        self.lib.fixture_disconnect()
        self.lib.fixture_poll()
        self.assertEqual(self.lib.fixture_shutdown(), 1)
        self.assertEqual(self.port.read(1024), b'')
        self.lib.fixture_storage()
        self.assertEqual(self.client.status()['shutdown'], 2)
        self.assertTrue(self.lib.fixture_persisted())

    def test_disconnect_partial_response_and_backpressure(self):
        self.feed(request())
        self.feed(request(2))  # single outstanding slot: cannot queue eject
        self.lib.fixture_poll()
        self.assertEqual(self.lib.fixture_shutdown(), 0)
        self.assertTrue(self.port.read(3))
        self.lib.fixture_disconnect()
        self.assertEqual(self.client.status()['shutdown'], 0)

    def test_bad_requests_and_resynchronization(self):
        for raw, error in [(request(99), 2), (request(version=2), 1),
                           (request()[:-1] + bytes([request()[-1] ^ 1]), 1)]:
            self.feed(b'garbage' + raw)
            data = bytearray()
            while chunk := self.port.read(1024):
                data.extend(chunk)
            self.assertEqual(data[6], error)
        self.assertEqual(self.client.status()['state'], 2)

    def test_host_rejects_corruption_and_short_reads(self):
        self.port.corrupt = 'crc'
        with self.assertRaisesRegex(ValueError, 'CRC mismatch'):
            self.client.status()
        self.lib.fixture_disconnect()
        self.port.corrupt = True
        with self.assertRaises(ValueError):
            self.client.status()
        self.lib.fixture_disconnect()
        self.port.corrupt = False
        self.port.truncate = True
        with self.assertRaises(TimeoutError):
            self.client.status()

    def test_eject_timeout_does_not_cancel(self):
        self.lib.fixture_dirty()
        with self.assertRaises(TimeoutError):
            self.client.eject(timeout=0.01)
        self.assertEqual(self.lib.fixture_shutdown(), 1)
        self.lib.fixture_storage()
        self.assertEqual(self.client.status()['shutdown'], 2)

    def test_snapshot_and_eject_during_inflight_sd(self):
        self.lib.fixture_dirty()
        self.feed(request(2))
        self.lib.fixture_io_control()
        self.lib.fixture_storage()
        raw = bytearray()
        while chunk := self.port.read(1024):
            raw.extend(chunk)
        status = dict(zip(usb.FIELDS, struct.unpack('<10I9Q', raw[16:-4])))
        self.assertEqual(status['shutdown'], 1)
        self.assertEqual(status['storage_busy'], 1)
        self.assertEqual(status['dirty_blocks'], 2)
        self.assertEqual(self.lib.fixture_shutdown(), 2)
        self.assertTrue(self.lib.fixture_persisted())
        self.assertEqual(self.client.status()['shutdown'], 2)

    def test_device_adapter(self):
        subprocess.run([str(self.adapter)], check=True, timeout=10)
