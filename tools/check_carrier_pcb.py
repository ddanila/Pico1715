#!/usr/bin/env python3
"""Portable review-board check against independently exported schematic nets."""
import json
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'hardware/carrier'
def parse(source):
 stack=[];root=None
 for t in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',source):
  if t=='(':
   node=[]
   if stack:stack[-1].append(node)
   else:root=node
   stack.append(node)
  elif t==')':stack.pop()
  else:stack[-1].append(json.loads(t) if t.startswith('"') else t)
 assert not stack
 return root
def children(node,key):return [x for x in node if isinstance(x,list) and x and x[0]==key]
def one(node,key):
 values=children(node,key);assert len(values)==1,(key,len(values));return values[0]
def check(board,parts,xml,plan):
 assert not plan['fabrication_ready'] and plan['unplaced_schematic_refs']==['X2']
 assert not children(board,'segment') and not children(board,'via'),'review board unexpectedly routed'
 expected={c['ref']:c for c in parts if c['footprint']}
 actual={next(p[2] for p in children(f,'property') if p[1]=='Reference'):f for f in children(board,'footprint')}
 assert set(actual)==set(expected)|{'H1','H2','H3','H4'}
 exported={}
 for net in xml.findall('./nets/net'):
  for pin in net.findall('node'):exported[(pin.attrib['ref'],pin.attrib['pin'])]=net.attrib['name']
 count=0
 for ref,c in expected.items():
  f=actual[ref];assert f[1]==c['footprint'],ref
  path='/'+str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/carrier/root'))+'/'+str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/carrier/'+ref))
  assert one(f,'path')[1]==path,ref
  assert [float(x) for x in one(f,'at')[1:]]==plan['placements'][ref][:len(one(f,'at'))-1],ref
  pads=children(f,'pad');assert {p[1] for p in pads}=={str(p[0]) for p in c['pins']},ref
  for p in pads:
   ns=children(p,'net');got=ns[0][-1] if ns else None
   want=next(q[3] for q in c['pins'] if str(q[0])==p[1])
   # KiCad exports explicitly NC contacts as unconnected-(...); no copper net.
   if want is not None:assert got==exported[(ref,p[1])]=="/"+want,(ref,p[1],got,want)
   else:assert got is None,(ref,p[1],got)
   count+=1
 assert len(children(board,'zone'))==1
 keep=one(one(board,'zone'),'keepout')
 assert one(keep,'tracks')[1]=='not_allowed' and one(keep,'vias')[1]=='not_allowed'
 assert len(children(actual['J3'],'zone'))>=1,'library SD exclusions lost'
 return {'electrical_footprints':len(expected),'pads_checked':count,'unplaced':['X2'],'fabrication_ready':False}
def main():
 result=check(parse((BASE/'carrier.kicad_pcb').read_text()),json.loads((BASE/'connections.json').read_text())['parts'],ET.parse(BASE/'carrier.net.xml'),json.loads((BASE/'pcb-placement.json').read_text()))
 print(json.dumps(result))
if __name__=='__main__':main()
