# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('source_map', Path(__file__).resolve().parents[1]/'tools/source_map.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceMapTest(unittest.TestCase):
    def test_verified_addresses_and_negative_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'demo.asm'
            source.write_text('entry: nop\nvalue: db 42\n')
            listing = ' 1: 0+4\t0100  00\tentry: nop\n 2: -\t0101  2A\tvalue: db 42\nentry 0100 256\n'
            args = (source, listing, bytes([0, 42]), 256, 'ram', True)
            value = module.generate(*args)
            self.assertEqual([r['code'] for r in value['entries']], [True, False])
            self.assertEqual(value['symbols'], [{'name': 'entry', 'address': 256}])
            for changed in (listing.replace('0100  00', '0100  FF'), listing.replace('entry: nop', 'entry: halt'), listing+listing.splitlines()[0]+'\n'):
                with self.assertRaises(ValueError):
                    module.generate(source, changed, bytes([0, 42]), 256, 'ram')


if __name__ == '__main__':
    unittest.main()
