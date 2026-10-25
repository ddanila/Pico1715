import importlib.util
from pathlib import Path
import struct
import unittest
spec = importlib.util.spec_from_file_location('fixture', Path(__file__).resolve().parents[1]/'tools/read_fixture.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def frame(code=0, count=515, ticks=350):
    b = struct.pack('<BBHI', 0xa5, code, count, ticks)
    x = 0
    for v in b:
        x ^= v
    return b+bytes([x])


class FixtureReport(unittest.TestCase):
    def test_resynchronizes_and_reports_units(self):
        r = fixture.decode(b'noise'+frame()[:4]+b'junk'+frame())
        self.assertEqual(r['result'], 'pass')
        self.assertEqual(r['max_cycle_us'], 14.0)
        self.assertFalse(r['electrical_timing_qualified'])

    def test_rejects_truncation_corruption_and_incomplete_pass(self):
        self.assertIsNone(fixture.decode(frame()[:-1]))
        b = bytearray(frame()); b[4] ^= 1
        self.assertIsNone(fixture.decode(b))
        self.assertIsNone(fixture.decode(frame(count=514)))

    def test_failure_is_not_pass(self):
        r = fixture.decode(frame(code=6, count=1))
        self.assertEqual(r['failure_code'], 6)
        self.assertEqual(r['result'], 'mailbox drain timeout')
