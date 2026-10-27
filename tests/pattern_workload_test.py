#!/usr/bin/env python3
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from pattern_workload import *
class Pattern(unittest.TestCase):
 def image(self):
  d=bytearray(819200);d[DIRECTORY:DIRECTORY+4096]=bytes([229])*4096;return bytes(d)
 def test_unique_records(self):
  self.assertEqual(len({record(i) for i in range(4096)}),4096)
  self.assertNotEqual(record(0,83),record(0,166))
 def test_bounds(self):
  for kwargs in [dict(records=0),dict(records=4097),dict(seed=256)]:
   with self.assertRaises(ValueError):program(**kwargs)
 def test_extents(self):
  d=bytearray(self.image());payload=b''.join(record(i) for i in range(256))
  for ordinal in range(2):
   e=bytearray(32);e[:12]=b'\0PICOTESTTXT';e[12]=ordinal;e[15]=128
   for i in range(8):e[16+2*i:18+2*i]=(2+ordinal*8+i).to_bytes(2,'little')
   # Reverse physical directory order to check logical extent sorting.
   at=DIRECTORY+(1-ordinal)*32;d[at:at+32]=e
  d[DIRECTORY+2*BLOCK:DIRECTORY+18*BLOCK]=payload
  self.assertEqual(read_file(d),payload)
  for mutation in ['duplicate','gap','short','allocation']:
   bad=bytearray(d)
   if mutation=='duplicate':bad[DIRECTORY+12]=0
   if mutation=='gap':bad[DIRECTORY+12]=2
   if mutation=='short':bad[DIRECTORY+32+15]=127
   if mutation=='allocation':bad[DIRECTORY+16: DIRECTORY+18]=(2).to_bytes(2,'little')
   with self.subTest(mutation=mutation),self.assertRaises(ValueError):read_file(bad)
 def test_full_fixture(self):
  d=nearly_full(fixture(self.image()),10);used={0,1}
  for i in range(DIRECTORY,DIRECTORY+4096,32):
   if d[i]<16:used.update(int.from_bytes(d[j:j+2],'little') for j in range(i+16,i+32,2))
  self.assertEqual(BLOCKS-len(used),10)
if __name__=='__main__':unittest.main()
