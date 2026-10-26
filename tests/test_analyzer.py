# SPDX-License-Identifier: MIT
import importlib.util
import io
from pathlib import Path
import struct
import sys
import unittest

SPEC = importlib.util.spec_from_file_location('analyzer_trace', Path(__file__).resolve().parents[1] / 'tools/analyzer_trace.py')
trace = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = trace
SPEC.loader.exec_module(trace)


class AnalyzerFormatTests(unittest.TestCase):
    def capture(self):
        return trace.Capture(50000000, 2, 1, 1, False,
                             [(0xfffffffe, 0), (0xffffffff, 1), (0, 2)])

    def test_roundtrip_wrap_and_exports(self):
        capture = self.capture()
        self.assertEqual(trace.decode(capture.encode()), capture)
        output = io.StringIO()
        trace.export_vcd(capture, output)
        self.assertIn('#40000\n', output.getvalue())
        self.assertIn('1t\n', output.getvalue())
        output = io.StringIO()
        trace.export_csv(capture, output)
        self.assertIn('2,0,40,0,reset', output.getvalue())

    def test_reject_malformed_captures(self):
        blob = self.capture().encode()
        for bad in (b'', blob[:10], blob[:-1], blob+b'\0', b'INVALID!'+blob[8:]):
            with self.subTest(bad=bad[:12]), self.assertRaises(ValueError):
                trace.decode(bad)
        for offset, value in ((8, 2), (10, 13), (12, 0), (20, 99), (24, 128)):
            bad = bytearray(blob)
            struct.pack_into('<H' if offset < 12 else '<I', bad, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                trace.decode(bad)
        for records in ([(0, 0), (2, 0), (3, 0)], [(0, 1 << 38), (1, 0), (2, 0)]):
            capture = self.capture()
            capture.records = records
            with self.assertRaises(ValueError):
                capture.encode()

    def test_stopped_capture(self):
        capture = trace.Capture(50000000, 3, 2, trace.NO_TRIGGER, True, [])
        self.assertEqual(trace.decode(capture.encode()), capture)
        capture.stopped = False
        with self.assertRaises(ValueError):
            capture.encode()
        capture = self.capture()
        capture.records.pop()
        with self.assertRaises(ValueError):
            capture.encode()
        capture.stopped = True
        self.assertEqual(trace.decode(capture.encode()), capture)

    def test_bus_classification(self):
        # All active-low lines released, clock low; full address survives decoding.
        idle = sum(1 << bit for _, bit, width in trace.SIGNALS if width == 1) | 0xbeef
        cases = [('idle', ()), ('memory_read', (24, 26)),
                 ('memory_write', (24, 27)), ('io_read', (25, 26)),
                 ('io_write', (25, 27)), ('opcode_fetch', (24, 26, 28)),
                 ('refresh', (24, 28, 29)), ('interrupt_ack', (25, 28)),
                 ('reset', (31,)), ('invalid', (24, 26, 27)),
                 ('invalid', (24, 25, 26)), ('bus_setup', (24,))]
        for expected, bits in cases:
            sample = idle
            for bit in bits:
                sample &= ~(1 << bit)
            with self.subTest(expected=expected):
                self.assertEqual(trace.cycle_kind(sample), expected)
                self.assertEqual(trace.fields(sample)['addr'], 0xbeef)
