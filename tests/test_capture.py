"""Reject misleading/malformed evidence before using it for device modelling."""
import json
import tempfile
import unittest
from pathlib import Path
from tools.capture_dac import summarize_trace, validate_inputs


class CaptureTests(unittest.TestCase):
    def trace(self, events):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'trace.jsonl'
            path.write_text(''.join(json.dumps(e) + '\n' for e in events))
            return summarize_trace(path)

    def event(self, **changes):
        return dict(dict(cycle=10, kind='IR', address=0x1235, data=0xaa, master=0), **changes)

    def test_keeps_repeated_ticks_and_separates_dma(self):
        result = self.trace([self.event(), self.event(cycle=11), self.event(master=1, cycle=12)])
        self.assertEqual(result['events'], 3)
        self.assertEqual(result['by_kind_port_master'], {'IR:35:cpu': 2, 'IR:35:dma': 1})

    def test_rejects_time_reversal(self):
        with self.assertRaises(ValueError):
            self.trace([self.event(), self.event(cycle=9)])

    def test_rejects_invalid_bus_events(self):
        for changes in [dict(kind='MR'), dict(data=256), dict(address=65536), dict(master=2)]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.trace([self.event(**changes)])

    def test_rejects_wrong_profile_sizes(self):
        with tempfile.TemporaryDirectory() as folder:
            rom = Path(folder) / 'rom'
            rom.write_bytes(bytes(1024))
            with self.assertRaises(ValueError):
                validate_inputs({'rom': rom})


if __name__ == '__main__':
    unittest.main()
