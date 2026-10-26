# SPDX-License-Identifier: MIT
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from analyzer_1715 import Decoder, compare, crc16, scan
from cycle_trace import Cycle, Header


def cycle(port=4, data=0xff, kind=5, **kw):
    return Cycle(kind, kw.get('flags', 0), data, port, kw.get('wait', 0),
                 kw.get('duration', 1), kw.get('tick', 0), kw.get('sequence', 0))


def field(payload):
    data = bytes([0xa1] * 3) + bytes(payload)
    return data + crc16(data).to_bytes(2, 'big')


class DecoderTests(unittest.TestCase):
    def test_fields_crc_and_unknown_length(self):
        d = Decoder()
        def feed(data):
            return [n for value in data for n in d.feed(cycle(2, value, 4))]
        self.assertTrue(any('length unknown' in n for n in feed(field([0xfb]))))
        ident = field([0xfe, 0, 0, 1, 3])
        self.assertEqual(ident[-2:], bytes.fromhex('da4e'))
        self.assertIn('ID C=0 H=0 R=1 N=3; CRC ok', feed(ident))
        payload = field([0xfb] + [0xa1, 0xfe, 0, 4] * 256)
        self.assertIn('read data field 1024 bytes; CRC ok', feed(payload))
        self.assertIn('read data field 1024 bytes; CRC BAD', feed(payload[:-1] + bytes([payload[-1] ^ 1])))
        self.assertIn('CRC BAD', feed(ident[:-1] + bytes([ident[-1] ^ 1]))[-1])
        self.assertIsNone(d.size)

    def test_pio_next_word_priority(self):
        d = Decoder()
        d.feed(cycle(7, 0xcf))
        self.assertEqual(d.feed(cycle(7, 0x12)), ['mark PIO direction=12'])
        self.assertNotIn('mark', d.vectors)
        d.feed(cycle(7, 0xb7))
        self.assertEqual(d.feed(cycle(7, 0xcf)), ['mark PIO interrupt mask=cf'])
        d.feed(cycle(7, 0x12))
        self.assertIn('(mark)', d.feed(cycle(0, 0x12, 6))[0])
        d.feed(cycle(0, 0, 8))
        self.assertEqual(d.vectors, {})

    def test_write_gate_partial_and_uncertain(self):
        d = Decoder()
        self.assertIn('unknown', d.feed(cycle(0, 1))[0])
        d.feed(cycle(4, 0xff))
        self.assertIn('ignored', d.feed(cycle(0, 1))[0])
        self.assertIn('write gate opened', d.feed(cycle(4, 0xfe)))
        for value in [0xa1] * 3 + [0xfe]:
            d.feed(cycle(0, value))
        self.assertIn('incomplete observed write field', d.feed(cycle(4, 0xff)))
        d.feed(cycle(7, 0xcf))
        d.feed(cycle(7, 0x12, flags=1))
        self.assertIsNone(d.pending)
        self.assertIsNone(d.control)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def save(self, name, rows, **kwargs):
        path = self.root / name
        clock = kwargs.pop('clock', 1000000)
        path.write_bytes(Header(clock, len(rows), **kwargs).encode() + b''.join(r.encode() for r in rows))
        return path

    def test_filtered_gap_does_not_clear_pio_but_loss_does(self):
        rows = [cycle(7, 0xcf), cycle(7, 0x12, sequence=3, tick=4)]
        normal = scan(self.save('normal', rows, filtered=2))
        self.assertEqual(normal['timeline'][1]['annotations'], ['mark PIO direction=12'])
        lossy = scan(self.save('loss', rows, dropped=2))
        self.assertIn('mark vector=12', lossy['timeline'][1]['annotations'])
        self.assertTrue(any('may include loss' in n for n in lossy['diagnostics']))

    def test_wrap_and_budgets(self):
        rows = [cycle(tick=0xfffffffc), cycle(sequence=1, tick=4, wait=2, duration=3)]
        report = scan(self.save('wrap', rows), wait_us=1, gap_us=5)
        self.assertEqual(report['timeline'][1]['elapsed_us'], 8)
        self.assertEqual(len(report['diagnostics']), 2)

    def test_compare_normalizes_clock_and_address_and_validates_tail(self):
        a = self.save('a', [cycle(0xab04, tick=100), cycle(2, 8, 4, tick=110, sequence=1)])
        b = self.save('b', [cycle(4, tick=200, duration=2), cycle(2, 8, 4, tick=220, duration=2, sequence=1)], clock=2000000)
        self.assertTrue(compare(a, b, tolerance_us=0)['match'])
        c = self.save('c', [cycle(4, tick=100), cycle(2, 9, 4, tick=110, sequence=1)])
        self.assertEqual(compare(a, c)['first_divergence']['event'], 1)
        c.write_bytes(c.read_bytes() + b'x')
        with self.assertRaisesRegex(ValueError, 'trailing'):
            compare(a, c)
        short = self.save('short', [cycle()])
        self.assertEqual(compare(a, short)['first_divergence']['reason'], 'different number of selected events')
        empty = self.save('empty', [])
        self.assertFalse(compare(empty, empty)['match'])

    def test_timing_is_optional(self):
        a = self.save('a', [cycle(), cycle(tick=10, sequence=1)])
        b = self.save('b', [cycle(), cycle(tick=12, sequence=1)])
        self.assertTrue(compare(a, b)['match'])
        self.assertFalse(compare(a, b, tolerance_us=1)['match'])

    def test_trigger_and_output(self):
        rows = [cycle(), cycle(7, 0x12, sequence=1, tick=5), cycle(0, 0x12, 6, sequence=2, tick=10)]
        trigger = (1, 1 << 6, 0, 0, 2, 0, 1, 2, 2, 0, 0, 1)
        a = self.save('trigger', rows, trigger=trigger)
        out = io.StringIO()
        result = scan(a, context=0, output=out)
        self.assertEqual(len(result['timeline']), 1)
        self.assertTrue(result['timeline'][0]['trigger'])
        self.assertEqual(len(out.getvalue().splitlines()), 3)
        self.assertTrue(compare(a, a, 'trigger')['match'])
        self.assertEqual(compare(a, a, 'trigger')['compared_events'], 1)
        b = self.save('plain', rows)
        with self.assertRaisesRegex(ValueError, 'requires a fired trigger'):
            compare(a, b, 'trigger')

    def test_cli_exit_and_input_protection(self):
        script = Path(__file__).resolve().parents[1] / 'tools/analyzer_1715.py'
        a = self.save('a', [cycle()])
        b = self.save('b', [cycle(data=1)])
        result = subprocess.run([sys.executable, str(script), str(a), '--reference', str(b), '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['comparison']['match'])
        original = a.read_bytes()
        result = subprocess.run([sys.executable, str(script), str(a), '--events', str(a)], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(a.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
