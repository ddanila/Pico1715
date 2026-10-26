#!/usr/bin/env python3
"""Portable review-board check against independently exported schematic nets."""
import json
import argparse
import hashlib
import math
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
  at=list(map(float,one(f,'at')[1:]));placed=plan['placements'][ref]
  assert at[:2]==placed[:2] and ((at[2] if len(at)>2 else 0)-placed[2])%360==0,ref
  pads=children(f,'pad');assert {p[1] for p in pads}=={str(p[0]) for p in c['pins']},ref
  for p in pads:
   ns=children(p,'net');got=ns[0][-1] if ns else None
   want=next(q[3] for q in c['pins'] if str(q[0])==p[1])
   # KiCad exports explicitly NC contacts as unconnected-(...); no copper net.
   if want is not None:assert got==exported[(ref,p[1])]=="/"+want,(ref,p[1],got,want)
   else:assert got is None,(ref,p[1],got)
   count+=1
 zones=children(board,'zone');assert len(zones)==2
 hold=next(z for z in zones if children(z,'keepout'))
 keep=one(hold,'keepout')
 assert all(one(keep,k)[1]=='not_allowed' for k in ['tracks','vias','copperpour'])
 assert set(one(hold,'layers')[1:])=={'F.Cu','B.Cu'}
 assert one(one(hold,'polygon'),'pts')[1:]==[['xy','160','28'],['xy','178','28'],['xy','178','47'],['xy','160','47']]
 ground=next(z for z in zones if not children(z,'keepout'))
 assert one(ground,'net')[-1]=='/GND' and one(ground,'layer')[1]=='B.Cu'
 assert children(ground,'filled_polygon'),'ground plane not filled'
 assert max(float(x[2]) for x in one(one(ground,'polygon'),'pts')[1:])<=201,'host reservation crossed'
 assert len(children(actual['J3'],'zone'))>=1,'library SD exclusions lost'
 def pos(ref,pin):
  f=actual[ref];p=next(p for p in children(f,'pad') if p[1]==str(pin))
  x,y,*a=map(float,one(f,'at')[1:]);px,py=map(float,one(p,'at')[1:3]);a=math.radians(a[0] if a else 0)
  return (round(x+px*math.cos(a)+py*math.sin(a),6),round(y-px*math.sin(a)+py*math.cos(a),6))
 def signature(t):return (one(t,'net')[-1],tuple(map(float,one(t,'start')[1:])),tuple(map(float,one(t,'end')[1:])),float(one(t,'width')[1]),one(t,'layer')[1])
 segments=children(board,'segment');got=sorted(signature(t) for t in segments)
 want=sorted(('/'+t['net'],tuple(t['start']),tuple(t['end']),t['width'],t['layer']) for t in plan['routes'])
 assert got==want,'route inventory differs from copper'
 assert all(t[3]>=.25 and t[4]=='F.Cu' for t in got)
 via_actual=sorted((one(v,'net')[-1],tuple(map(float,one(v,'at')[1:])),float(one(v,'size')[1]),float(one(v,'drill')[1])) for v in children(board,'via'))
 assert via_actual==sorted(('/'+v['net'],tuple(v['at']),v['diameter'],v['drill']) for v in plan['vias'])
 assert all(v[0]=='/GND' for v in via_actual),'unexpected rail via'
 # Independent device list prevents a matching generator/manifest error from
 # assigning a cap to the wrong supply or moving it back to the staging row.
 devices=[*(('RX'+str(i),'20') for i in range(1,6)),('U4','20'),('U5','5'),
          ('U6','14'),('U7','14'),('U8','14'),('U13','14'),('U9','14'),
          ('U10','3'),('U11','3'),('U12','3'),('ISO1','20'),('ISO2','20'),('ISO3','20')]
 lengths=[]
 for i,(ref,pin) in enumerate(devices,1):
  cap='C'+str(i);a=pos(ref,pin);z=pos(cap,1)
  assert plan['decoupling'][cap]==dict(device=ref,supply_pin=pin)
  length=math.dist(a,z);assert length<=2.1,(cap,'bypass too far from supply',length)
  net=next(p[3] for p in expected[ref]['pins'] if str(p[0])==pin)
  assert any(t[:3]==('/'+net,a,z) for t in got),(cap,'supply trace missing')
  g=pos(cap,2)
  exits=[t[2] for t in got if t[0]=='/GND' and t[1]==g and math.dist(t[1],t[2])<=1.5]
  assert any(v[0]=='/GND' and v[1] in exits for v in via_actual),(cap,'short ground return missing')
  lengths.append(length)
 # Verify support circuits from actual copper, independently of route tags
 # and the manifest. These routes deliberately meet at explicit endpoints.
 def connected(net,a,z):
  edges={}
  for n,start,end,_,_ in got:
   if n!='/'+net:continue
   edges.setdefault(start,set()).add(end);edges.setdefault(end,set()).add(start)
  seen={a};pending=[a]
  while pending:
   for point in edges.get(pending.pop(),()):
    if point not in seen:seen.add(point);pending.append(point)
  return z in seen
 for dev,up,down,rail,pg in [('U10','R1','R2','V3P3','PG3'),
                            ('U11','R3','R4','V5_HOST','PG5'),
                            ('U12','R5','R6','P3V3','PGP')]:
  assert connected(rail,pos(dev,3),pos(up,1)),(dev,'pull-up supply disconnected')
  assert connected(pg,pos(dev,2),pos(up,2)),(dev,'sense disconnected')
  assert connected(pg,pos(dev,2),pos(down,1)),(dev,'pull-down disconnected')
 grounded=['R2','R4','R6','R7','R8','R9','R10','R11','R12','R13','R16','R19','R20']
 for ref in grounded:
  a=pos(ref,2)
  assert any(n=='/GND' and math.dist(a,z)<=1.5 and connected('GND',a,z)
             for n,z,_,_ in via_actual),(ref,'short plane return missing')
 return {'electrical_footprints':len(expected),'pads_checked':count,'unplaced':['X2'],'fabrication_ready':False,
         'supervisor_networks':3,'resistor_ground_returns':len(grounded),
         'routed_segments':len(segments),'ground_vias':len(via_actual),'local_bypass_capacitors':len(devices),
         'maximum_bypass_supply_length_mm':round(max(lengths),3),'ground_plane':'B.Cu',
         'sd_hold_layers':['F.Cu','B.Cu']}
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--drc',type=Path,help='fresh KiCad JSON report; fail on geometric violations, retain open nets')
 parser.add_argument('--report',type=Path,help='write checked summary with source fingerprints')
 args=parser.parse_args()
 result=check(parse((BASE/'carrier.kicad_pcb').read_text()),json.loads((BASE/'connections.json').read_text())['parts'],ET.parse(BASE/'carrier.net.xml'),json.loads((BASE/'pcb-placement.json').read_text()))
 if args.drc:
  drc=json.loads(args.drc.read_text());assert not drc['violations'],drc['violations']
  result.update(drc_violations=0,drc_unconnected_items=len(drc['unconnected_items']),
                drc_ignored_checks=drc.get('ignored_checks',[]),hardware_executed=False,
                drc_note='Partial routing; open nets are reported, not waived or a production pass.')
 if args.report:
  assert args.drc,'report requires fresh geometric DRC evidence'
  files=['tools/generate_carrier_pcb.py','tools/check_carrier_pcb.py','tests/carrier_pcb_test.py',
         'hardware/carrier/carrier.kicad_pcb','hardware/carrier/carrier.kicad_pro','hardware/carrier/pcb-placement.json',
         'hardware/carrier/carrier.kicad_sch','hardware/carrier/carrier.net.xml']
  result['source_sha256']={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
  args.report.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
if __name__=='__main__':main()
