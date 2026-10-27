#!/usr/bin/env python3
"""Allocation safety and routing-screen geometry regression tests."""
import copy,sys,unittest,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from classic_workload import install,program,small_file
from review_carrier_routing import metrics
class Workload(unittest.TestCase):
 def image(self):
  d=bytearray(819200);d[20480:24576]=bytes([229])*4096;return d
 def test_allocation(self):
  d=self.image();e=bytearray(32);e[:12]=b'\x00EXISTINGTXT';e[15]=1;e[16:18]=(62).to_bytes(2,'little');d[20480:20512]=e;d[147456:149504]=b'x'*2048
  original=bytes(d);out,payload=install(original,96,None)
  self.assertEqual(d,original);self.assertEqual(out[147456:149504],b'x'*2048)
  self.assertEqual(small_file(out,b'PICOTESTCOM'),program(96)[0]);self.assertEqual(len(payload),128)
  changed={i for i,(a,b) in enumerate(zip(original,out)) if a!=b}
  self.assertTrue(changed <= set(range(20512,20544))|set(range(24576,25216)))
  with self.assertRaises(ValueError):install(original)
  with self.assertRaises(ValueError):install(out,block=None)
 def test_full_directory(self):
  d=self.image();d[20480:24576]=bytes(4096)
  with self.assertRaises(ValueError):install(d,block=None)
 def test_default_binary_compatible(self):
  self.assertEqual(hashlib.sha256(program()[0]).hexdigest(),'56183b982622cc73aa4bf06e4ac207a4da8580dc2d483813b8cdfb17d2f2339c')
 def test_record_bounds(self):
  for n in (0,129,-1):
   with self.assertRaises(ValueError):program(n)
  self.assertEqual(len(program(1)[0]),len(program(128)[0]))
 def test_short_file(self):
  d=self.image();e=bytearray(32);e[:12]=b'\x00PICOTESTTXT';e[15]=20;d[20480:20512]=e
  with self.assertRaises(ValueError):small_file(d,b'PICOTESTTXT')
class Routing(unittest.TestCase):
 def track(self,net,start,end,layer='F.Cu'):return dict(net=net,start=start,end=end,layer=layer,width=.25)
 def test_parallel(self):
  a=self.track('A',[0,0],[20,0]);b=self.track('B',[20,.5],[0,.5]);p=dict(routes=[a,b],vias=[])
  nets,pairs=metrics(p);self.assertEqual(nets['A']['copper_length_mm'],20);self.assertEqual(pairs[0]['overlap_mm'],20);self.assertEqual(pairs[0]['edge_gap_mm'],.25)
  for change in [dict(layer='B.Cu'),dict(net='A'),dict(start=[30,.5],end=[50,.5]),dict(start=[10,-10],end=[10,10])]:
   q=copy.deepcopy(p);q['routes'][1].update(change);self.assertEqual(metrics(q)[1],[])
if __name__=='__main__':unittest.main()
