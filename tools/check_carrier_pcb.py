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
def check_drc(board,drc,require_only_held=True):
 assert not drc['violations'],drc['violations']
 held={one(p,'uuid')[1] for f in children(board,'footprint')
       if any(q[1:3]==['Reference','J3'] for q in children(f,'property'))
       for p in children(f,'pad')}
 ordinary=[gap for gap in drc['unconnected_items']
           if not any(item['uuid'] in held for item in gap['items'])]
 if require_only_held:assert not ordinary,('unconnected outside SD hold',ordinary)
 return dict(drc_violations=0,drc_unconnected_items=len(drc['unconnected_items']),
             drc_nonheld_unconnected_items=len(ordinary),
             drc_ignored_checks=drc.get('ignored_checks',[]),hardware_executed=False,
             drc_note='SD socket held and X2 unplaced; not a fabrication release.')
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
 zones=children(board,'zone');assert len(zones)==1+len(plan.get('ground_layers',['B.Cu']))
 hold=next(z for z in zones if children(z,'keepout'))
 keep=one(hold,'keepout')
 assert all(one(keep,k)[1]=='not_allowed' for k in ['tracks','vias','copperpour'])
 assert set(one(hold,'layers')[1:])=={'F.Cu','B.Cu'}
 assert one(one(hold,'polygon'),'pts')[1:]==[['xy','160','28'],['xy','178','28'],['xy','178','47'],['xy','160','47']]
 grounds=[z for z in zones if not children(z,'keepout')]
 assert sorted(one(z,'layer')[1] for z in grounds)==sorted(plan.get('ground_layers',['B.Cu']))
 for ground in grounds:
  assert one(ground,'net')[-1]=='/GND'
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
 assert all(t[3]>=.25 and t[4] in ['F.Cu','B.Cu'] for t in got)
 via_actual=sorted((one(v,'net')[-1],tuple(map(float,one(v,'at')[1:])),float(one(v,'size')[1]),float(one(v,'drill')[1])) for v in children(board,'via'))
 assert via_actual==sorted(('/'+v['net'],tuple(v['at']),v['diameter'],v['drill']) for v in plan['vias'])
 power_nets={'/V5_HOST','/P3V3'}
 signal_nets={'/'+pin[3] for c in parts for pin in c['pins'] if pin[3]}-power_nets-{'/GND','/V3P3','/V5_MODULE','/P_VSYS'}
 assert all(v[0] in {'/GND','/V3P3','/V5_MODULE','/P_VSYS'}|power_nets|signal_nets for v in via_actual),'unexpected via net'
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
 # Derive layer-aware connectivity from copper, including T junctions.
 # A crossing on opposite layers is connected only by an actual via/PTH pad.
 graph_cache={}
 def connected(net,a,z):
  if net in graph_cache:
   labels=graph_cache[net]
   return labels.get((a,'F.Cu'),-1)==labels.get((z,'F.Cu'),-2)
  traces=[(start,end,layer) for n,start,end,_,layer in got if n=='/'+net]
  junctions={a,z}|{v[1] for v in via_actual if v[0]=='/'+net}
  for start,end,_ in traces:junctions.update([start,end])
  through={v[1] for v in via_actual if v[0]=='/'+net}
  for ref,f in actual.items():
   for p in children(f,'pad'):
    ns=children(p,'net')
    if ns and ns[0][-1]=='/'+net:
     junctions.add(pos(ref,p[1]))
     if p[2]=='thru_hole':through.add(pos(ref,p[1]))
  edges={}
  def join(x,y):
   edges.setdefault(x,set()).add(y);edges.setdefault(y,set()).add(x)
  for start,end,layer in traces:
   dx,dy=end[0]-start[0],end[1]-start[1]
   points=[p for p in junctions
           if abs((p[0]-start[0])*dy-(p[1]-start[1])*dx)<1e-6
           and min(start[0],end[0])-1e-6<=p[0]<=max(start[0],end[0])+1e-6
           and min(start[1],end[1])-1e-6<=p[1]<=max(start[1],end[1])+1e-6]
   points.sort(key=lambda p:math.dist(start,p))
   for x,y in zip(points,points[1:]):join((x,layer),(y,layer))
  for p in through:join((p,'F.Cu'),(p,'B.Cu'))
  labels={}
  for start in edges:
   if start in labels:continue
   group=len(labels);labels[start]=group;pending=[start]
   while pending:
    for point in edges.get(pending.pop(),()):
     if point not in labels:labels[point]=group;pending.append(point)
  graph_cache[net]=labels
  return labels.get((a,'F.Cu'),-1)==labels.get((z,'F.Cu'),-2)
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
 rail_counts={}
 for net,source in [('V3P3',('EXT1',3)),('P3V3',('J2',36)),('V5_HOST',('U11',3))]:
  targets=[(ref,pin[0]) for ref,c in expected.items() for pin in c['pins']
           if pin[3]==net and ref!='J3']
  for ref,pin in targets:
   assert connected(net,pos(*source),pos(ref,pin)),(net,ref,pin,'rail disconnected')
  rail_counts[net]=len(targets)
 for net,a,z in [('CDONE',('J1',1),('R16',1)),
                 ('MODE_CTL',('SW1',2),('R7',1)),
                 ('H_PRIORITY',('SW1',5),('R18',2))]:
  assert connected(net,pos(*a),pos(*z)),(net,'local control branch disconnected')
 a=pos('C19',2)
 assert any(n=='/GND' and math.dist(a,z)<=1.5 and connected('GND',a,z)
            for n,z,_,_ in via_actual),'SD bypass ground return missing'
 # Retain explicit interlock and local branch checks; the complete placed-net
 # check below also covers the external POWER_GOOD and ARMED branches.
 interlock_counts={}
 for net in ['PG3','PG5','PGP','RAILS_OK','POWERED',
             'QUALIFIED','BACKEND_OK','RESET_OK','LINK_OK','LINK_OE_N','CDONE','PERSONALITY_CTL']:
  targets=[(c['ref'],pin[0]) for c in parts for pin in c['pins'] if pin[3]==net]
  assert len(targets)>=2
  for ref,pin in targets[1:]:
   assert connected(net,pos(*targets[0]),pos(ref,pin)),(net,ref,pin,'interlock disconnected')
  interlock_counts[net]=len(targets)
 local_interlock={'POWER_GOOD':[('U6',3),('U6',12)],
                    'ARMED':[('U7',11),('U8',1),('U8',4),('U8',9),('U8',12),('U8',13)]}
 for net,targets in local_interlock.items():
  for target in targets[1:]:
   assert connected(net,pos(*targets[0]),pos(*target)),(net,target,'gate branch disconnected')
 terminal_groups={}
 for ref,c in expected.items():
  if ref=='J3':continue  # Manufacturer land-pattern review is still held.
  for pin in c['pins']:
   if pin[3] and pin[3]!='GND':terminal_groups.setdefault(pin[3],[]).append((ref,pin[0]))
 remaining=[]
 for net,targets in terminal_groups.items():
  for target in targets[1:]:
   if not connected(net,pos(*targets[0]),pos(*target)):
    remaining.append(dict(net=net,source=targets[0],target=target))
 assert not remaining,('placed terminal disconnected',remaining)
 return {'electrical_footprints':len(expected),'pads_checked':count,'unplaced':['X2'],'fabrication_ready':False,
         'remaining_placed_signal_connections':remaining,
         'connected_placed_net_pads':{n:len(p) for n,p in terminal_groups.items() if len(p)>1},
         'supervisor_networks':3,'resistor_ground_returns':len(grounded),
         'routed_segments':len(segments),'ground_vias':sum(v[0]=='/GND' for v in via_actual),
         'power_vias':sum(v[0] in power_nets for v in via_actual),
         'signal_vias':sum(v[0] in signal_nets for v in via_actual),
         'complete_interlock_net_pads':interlock_counts,
         'local_interlock_branch_pads':{n:len(p) for n,p in local_interlock.items()},'distributed_rail_pads':rail_counts,
         'local_control_branches':3,'local_bypass_capacitors':len(devices),
         'maximum_bypass_supply_length_mm':round(max(lengths),3),'ground_layers':plan['ground_layers'],
         'sd_hold_layers':['F.Cu','B.Cu']}
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--drc',type=Path,help='fresh KiCad JSON report; only held J3 airwires are permitted')
 parser.add_argument('--report',type=Path,help='write checked summary with source fingerprints')
 args=parser.parse_args()
 board=parse((BASE/'carrier.kicad_pcb').read_text())
 result=check(board,json.loads((BASE/'connections.json').read_text())['parts'],ET.parse(BASE/'carrier.net.xml'),json.loads((BASE/'pcb-placement.json').read_text()))
 if args.drc:
  result.update(check_drc(board,json.loads(args.drc.read_text())))
 if args.report:
  assert args.drc,'report requires fresh geometric DRC evidence'
  files=['tools/generate_carrier_pcb.py','tools/check_carrier_pcb.py','tests/carrier_pcb_test.py',
         'tools/prepare_carrier_routing.py','tools/import_carrier_routing.py','hardware/carrier/additional-routes.json',
         'hardware/carrier/carrier.kicad_pcb','hardware/carrier/carrier.kicad_pro','hardware/carrier/pcb-placement.json',
         'hardware/carrier/carrier.kicad_sch','hardware/carrier/carrier.net.xml']
  result['source_sha256']={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
  args.report.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
if __name__=='__main__':main()
