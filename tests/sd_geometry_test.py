#!/usr/bin/env python3
import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from check_sd_geometry import check
from check_carrier_pcb import parse,children,one
class Geometry(unittest.TestCase):
 def setUp(self):self.board=parse((ROOT/'hardware/carrier/carrier.kicad_pcb').read_text())
 def test_current(self):check(self.board)
 def test_old_mount_collision(self):
  b=copy.deepcopy(self.board);f=next(f for f in children(b,'footprint') if any(p[1:3]==['Reference','H2'] for p in children(f,'property')));one(f,'at')[1]='176'
  with self.assertRaises(AssertionError):check(b)
 def test_wrong_land(self):
  b=copy.deepcopy(self.board);f=next(f for f in children(b,'footprint') if any(p[1:3]==['Reference','J3'] for p in children(f,'property')));one(children(f,'pad')[0],'size')[1]='1.5'
  with self.assertRaises(AssertionError):check(b)
 def test_lost_exclusion(self):
  b=copy.deepcopy(self.board);f=next(f for f in children(b,'footprint') if any(p[1:3]==['Reference','J3'] for p in children(f,'property')));f.remove(children(f,'zone')[0])
  with self.assertRaises(AssertionError):check(b)
if __name__=='__main__':unittest.main()
