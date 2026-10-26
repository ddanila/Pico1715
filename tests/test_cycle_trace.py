# SPDX-License-Identifier: MIT
import importlib.util
import io
from pathlib import Path
import struct
import sys
import unittest

SPEC = importlib.util.spec_from_file_location('cycle_trace', Path(__file__).resolve().parents[1]/'tools/cycle_trace.py')
trace = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = trace
SPEC.loader.exec_module(trace)


class CompactTraceTests(unittest.TestCase):
    def test_roundtrip_and_filtered_gaps(self):
        header = trace.Header(9832000, 2, filtered=6, capture_mask=0x170)
        rows = [trace.Cycle(4, 0, 0x5a, 0x1234, 8, 12, 0xfffffff8, 2),
                trace.Cycle(6, 0, 0xe0, 0x1234, 0, 4, 8, 7)]
        blob = header.encode() + b''.join(r.encode() for r in rows)
        self.assertEqual(trace.decode(blob), (header, [(rows[0], 2), (rows[1], 4)]))
        output = io.StringIO()
        trace.export_csv(io.BytesIO(blob[trace.HEADER.size:]), header, output)
        self.assertIn('interrupt_ack,1234,e0,4,0,0,0,0,0,4', output.getvalue())

    def test_loss_and_trailing_loss(self):
        row = trace.Cycle(2, 0, 1, 2, 0, 4, 0, 1)
        header = trace.Header(50000000, 1, dropped=3)
        self.assertEqual(len(trace.decode(header.encode()+row.encode())[1]), 1)
        with self.assertRaises(ValueError):
            trace.decode(trace.Header(50000000, 1).encode()+row.encode())
        trace.decode(trace.Header(50000000, 0, dropped=10).encode())

    def test_bad_header_and_records(self):
        row = trace.Cycle(2, 0, 1, 2, 0, 4, 0, 0)
        blob = trace.Header(50000000, 1).encode()+row.encode()
        for bad in (b'', blob[:30], blob[:-1], blob+b'x', b'INVALID!'+blob[8:]):
            with self.subTest(bad=bad[:10]), self.assertRaises(ValueError):
                trace.decode(bad)
        for offset, value in ((8, 2), (10, 12), (12, 0), (28, 1)):
            bad = bytearray(blob)
            struct.pack_into('<H' if offset < 12 else '<I', bad, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                trace.decode(bad)
        for bad in (trace.Cycle(0, 0, 1, 2, 0, 4, 0, 0),
                    trace.Cycle(2, 4, 1, 2, 0, 4, 0, 0),
                    trace.Cycle(2, 0, 1, 2, 5, 4, 0, 0),
                    trace.Cycle(8, 0, 1, 0, 0, 4, 0, 0)):
            with self.assertRaises(ValueError):
                bad.encode()
        with self.assertRaises(ValueError):
            trace.decode(trace.Header(50000000, 2).encode()+row.encode()+row.encode())
        second = trace.Cycle(2, 0, 1, 2, 0, 4, 2, 1)
        with self.assertRaises(ValueError):
            trace.decode(trace.Header(50000000, 2).encode()+row.encode()+second.encode())

    def test_saturation_flags_and_empty_filter(self):
        row = trace.Cycle(2, 15, 0xff, 0xffff, 65535, 65535, 0, 0)
        self.assertEqual(trace.decode(trace.Header(50000000, 1).encode()+row.encode())[1][0][0], row)
        self.assertEqual(trace.decode(trace.Header(50000000, 0, filtered=12, capture_mask=0).encode())[1], [])
