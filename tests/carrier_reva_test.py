#!/usr/bin/env python3
"""Mutate safety-critical Rev A interfaces and ensure the independent checks fail."""
import copy,json,sys,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from check_carrier_reva import check_contract,check_board
from check_carrier_pcb import parse,children,one
from kicad_text import remove_nodes
BASE=ROOT/'hardware/carrier-reva'
class RevATests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.c=json.loads((BASE/'connections.json').read_text());cls.xml=ET.parse(BASE/'carrier.net.xml').getroot();cls.board=parse((BASE/'carrier.kicad_pcb').read_text())
 def test_contract(self):check_contract(self.c,self.xml);check_board(self.c,self.xml,self.board)
 def test_interface_mutations(self):
  for kind in ['swap-host','swap-power','join-power','lost-header','lost-status','long-cable','connected-spare','wrong-contact','lost-interlock','false-release']:
   with self.subTest(kind=kind):
    c=copy.deepcopy(self.c);parts={p['ref']:p for p in c['parts']}
    if kind=='false-release':c['fabrication_ready']=True
    elif kind=='swap-host':parts['J6']['pins'][0][3],parts['J6']['pins'][6][3]=parts['J6']['pins'][6][3],parts['J6']['pins'][0][3]
    elif kind=='swap-power':parts['J7']['pins'][1][3],parts['J7']['pins'][2][3]=parts['J7']['pins'][2][3],parts['J7']['pins'][1][3]
    elif kind=='join-power':parts['J7']['pins'][2][3]='V5_MODULE'
    elif kind=='lost-header':c['parts'].remove(parts['J6'])
    elif kind=='lost-status':c['reserve']['status_gpio']['PRESENT_N']=0
    elif kind=='long-cable':c['host_harness']['maximum_cable_mm']=1000
    elif kind=='connected-spare':parts['J6']['pins'][-1][3]='V5_HOST'
    elif kind=='wrong-contact':c['host_harness']['pins'][0]['contact']='B1'
    elif kind=='lost-interlock':
     for p in c['parts']:
      for pin in p['pins']:
       if pin[3]=='ARMED':pin[3]='V3P3'
    with self.assertRaises((AssertionError,KeyError,StopIteration)):check_contract(c,self.xml)
 def test_board_mutations(self):
  for kind in ['lost-pad','wrong-net','lost-plane','signal-plane','lost-hold-layer','lost-track','lost-via','wrong-path']:
   with self.subTest(kind=kind):
    b=copy.deepcopy(self.board)
    f=next(f for f in children(b,'footprint') if any(x[1:3]==['Reference','J7'] for x in children(f,'property')))
    if kind=='lost-track':b.remove(children(b,'segment')[0])
    elif kind=='lost-via':b.remove(children(b,'via')[0])
    elif kind=='wrong-path':one(f,'path')[1]='/wrong'
    elif kind=='lost-pad':f.remove(children(f,'pad')[0])
    elif kind=='wrong-net':one(children(f,'pad')[0],'net')[-1]='/V5_HOST'
    elif kind=='lost-plane':b.remove(next(z for z in children(b,'zone') if children(z,'layer') and one(z,'layer')[1]=='In1.Cu'))
    elif kind=='signal-plane':one(children(b,'segment')[0],'layer')[1]='In1.Cu'
    elif kind=='lost-hold-layer':one(next(z for z in children(b,'zone') if children(z,'keepout')),'layers').remove('In2.Cu')
    with self.assertRaises((AssertionError,KeyError,StopIteration)):check_board(self.c,self.xml,b)
 def test_lossless_filter(self):
  s='(board (note "escaped \\\" ( text") (segment (net "/F_CLK")) (via (net "/GND")))'
  self.assertEqual(remove_nodes(s,lambda h,n,d:h=='segment'),'(board (note "escaped \\\" ( text")  (via (net "/GND")))')
  self.assertEqual(remove_nodes(s,lambda h,n,d:False),s)
if __name__=='__main__':unittest.main()
