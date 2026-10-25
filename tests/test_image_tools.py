"""Verify host image envelopes and refusal to overwrite existing outputs."""
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ImageTools(unittest.TestCase):
    def run_tool(self, tool, *args, success=True):
        r = subprocess.run([sys.executable, str(ROOT/'tools'/tool), *map(str, args)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode == 0, success, r.stderr)

    def test_sd_layout_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = pathlib.Path(tmp)/'disk', pathlib.Path(tmp)/'sd'
            payload = bytes(range(256))*3200
            source.write_bytes(payload)
            self.run_tool('make_sd_image.py', '--disk', source, '--out', out)
            data = out.read_bytes()
            self.assertEqual(data[:8], b'P1715SD1')
            self.assertEqual(struct.unpack_from('<II', data, 8), (2048, 1600))
            self.assertEqual(struct.unpack_from('<I', data, 508)[0], zlib.crc32(data[:508]))
            self.assertEqual(data[512:1536], bytes(1024))
            self.assertEqual(data[2048*512:], payload)
            self.run_tool('make_sd_image.py', '--disk', source, '--out', out, success=False)
            self.assertEqual(out.read_bytes(), data)
            source.write_bytes(b'bad')
            self.run_tool('make_sd_image.py', '--disk', source, '--out', pathlib.Path(tmp)/'bad', success=False)

    def test_uf2_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = pathlib.Path(tmp)/'fw.bin', pathlib.Path(tmp)/'fw.uf2'
            payload = bytes(range(256))*3+b'final'
            source.write_bytes(payload)
            self.run_tool('make_uf2.py', '--bin', source, '--out', out)
            data = out.read_bytes()
            self.assertEqual(len(data), 4*512)
            decoded = bytearray()
            for i in range(4):
                block = data[i*512:(i+1)*512]
                self.assertEqual(struct.unpack_from('<8I', block),
                    (0x0a324655, 0x9e5d5157, 0x2000, 0x10000000+i*256, 256, i, 4, 0xe48bff59))
                self.assertEqual(struct.unpack_from('<I', block, 508)[0], 0x0ab16f30)
                decoded.extend(block[32:288])
            self.assertEqual(decoded[:len(payload)], payload)
            self.assertEqual(decoded[len(payload):], bytes(1024-len(payload)))
            self.run_tool('make_uf2.py', '--bin', source, '--out', out, success=False)
            self.assertEqual(out.read_bytes(), data)
