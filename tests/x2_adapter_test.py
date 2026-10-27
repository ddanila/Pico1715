#!/usr/bin/env python3
"""Check independent pin mapping, isolation and routed path continuity."""
import copy,json,sys,unittest,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from check_carrier_pcb import parse,children,one
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'hardware/x2-adapter'
def check(board,manifest,xml):
 assert manifest['fabrication_ready'] is False
 fps={next(p[2] for p in children(f,'property') if p[1]=='Reference'):f for f in children(board,'footprint')}
 assert set(fps)=={'X2','J1'} and len(manifest['mapping'])==58
 expected={}
 for i in range(1,30):
  for row,number in [('A',2*i-1),('B',2*i)]:expected[f'{row}{i}']=number
 assert {r['contact']:r['header_pin'] for r in manifest['mapping']}==expected
 exported={}
 for n in xml.findall('./nets/net'):
  for p in n.findall('node'):exported[(p.attrib['ref'],p.attrib['pin'])]=n.attrib['name']
 for contact,pin in expected.items():
  net='/X2_'+contact
  assert exported[('X2',contact)]==exported[('J1',str(pin))]==net
  for ref,num in [('X2',contact),('J1',str(pin))]:
   pad=next(p for p in children(fps[ref],'pad') if p[1]==num);assert one(pad,'net')[-1]==net
  i=int(contact[1:])-1;x=35+2.5*i;gx=34+2.54*i
  start=(x,31.5 if contact[0]=='A' else 36.5);end=(gx,52 if contact[0]=='A' else 49.46)
  tracks=[t for t in children(board,'segment') if one(t,'net')[-1]==net]
  graph={}
  def point(t,key):return tuple(round(float(v),4) for v in one(t,key)[1:])
  for t in tracks:
   assert one(t,'layer')[1]==('B.Cu' if contact[0]=='A' else 'F.Cu')
   a,z=point(t,'start'),point(t,'end');graph.setdefault(a,set()).add(z);graph.setdefault(z,set()).add(a)
  seen=set();todo=[tuple(round(v,4) for v in start)]
  while todo:
   p=todo.pop()
   if p not in seen:seen.add(p);todo.extend(graph.get(p,set())-seen)
  assert tuple(round(v,4) for v in end) in seen,(contact,'open')
 assert len(children(board,'segment'))==232 and not children(board,'via')
 assert all(one(t,'net')[-1].startswith('/X2_') for t in children(board,'segment'))
 for pin in ['59','60']:
  p=next(p for p in children(fps['J1'],'pad') if p[1]==pin);assert one(p,'net')[-1]==f'unconnected-(J1-Pad{pin})'
class Adapter(unittest.TestCase):
 def setUp(self):
  self.b=parse((BASE/'adapter.kicad_pcb').read_text());self.m=json.loads((BASE/'mapping.json').read_text());self.x=ET.parse(BASE/'adapter.net.xml')
 def test_good(self):check(self.b,self.m,self.x)
 def test_faults(self):
  for kind in ['row-swap','short','open','release']:
   b=copy.deepcopy(self.b);m=copy.deepcopy(self.m)
   if kind=='row-swap':m['mapping'][0]['header_pin']=2
   if kind=='short':one(children(children(b,'footprint')[0],'pad')[0],'net')[-1]='/WRONG'
   if kind=='open':b.remove(children(b,'segment')[0])
   if kind=='release':m['fabrication_ready']=True
   with self.subTest(kind=kind),self.assertRaises(AssertionError):check(b,m,self.x)
if __name__=='__main__':unittest.main()
