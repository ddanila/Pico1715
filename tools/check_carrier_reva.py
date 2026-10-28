#!/usr/bin/env python3
"""Independent Rev A harness, power and schematic/PCB contract checks."""
import argparse,copy,hashlib,json,uuid,xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
from check_carrier import check as check_interlocks
from check_carrier_pcb import parse,children,one,check_drc
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'hardware/carrier-reva'
def check_contract(c,tree):
 assert c['fabrication_ready'] is False and c['physical_orientation_verified'] is False
 parts={p['ref']:p for p in c['parts']};assert 'X2' not in parts and 'J6' in parts and 'J7' in parts
 pins={str(n):net for n,_,_,net in parts['J6']['pins']}
 assert set(pins)=={str(i) for i in range(1,61)} and pins['59'] is None and pins['60'] is None
 assert [net for _,_,_,net in parts['J7']['pins']]==['GND','V5_MODULE','P_VSYS']
 assert [str(n) for n,_,_,_ in parts['J7']['pins']]==['1','2','3']
 assert c['reserve']['status_gpio']=={'SUPPLY_OK':32,'RESERVE_OK':33,'PRESENT_N':36}
 assert not c['reserve']['daughterboard_in_first_order']
 assert c['host_harness']['maximum_cable_mm']==100
 assert c['host_harness']['header']=='61206021621' and c['host_harness']['mate']=='61206023021'
 assert len(c['host_harness']['pins'])==58
 for row in c['host_harness']['pins']:
  n=row['pin'];assert row['contact']==('A' if n%2 else 'B')+str((n+1)//2)
  assert row['net']==pins[str(n)]
 # Adapt only connector identity to the independently maintained 58-contact,
 # rail-isolation and 2048-state interlock oracle. Do not derive its expectations
 # from the new generator or manifest.
 mapped=copy.deepcopy(c);host=next(p for p in mapped['parts'] if p['ref']=='J6');host['ref']='X2'
 host['pins']=[[('A' if int(n)%2 else 'B')+str((int(n)+1)//2),name,typ,net] for n,name,typ,net in host['pins'] if int(n)<=58]
 xml=copy.deepcopy(tree)
 for net in xml.findall('nets/net'):
  for node in list(net.findall('node')):
   if node.attrib['ref']=='J6':
    n=int(node.attrib['pin'])
    if n>58:net.remove(node);continue
    node.attrib.update(ref='X2',pin=('A' if n%2 else 'B')+str((n+1)//2))
 return check_interlocks(xml,mapped)
def check_board(c,tree,board):
 parts={p['ref']:p for p in c['parts']}
 fps={next(x[2] for x in children(f,'property') if x[1]=='Reference'):f for f in children(board,'footprint')}
 assert set(fps)==set(parts)|{'H1','H2','H3','H4'},'missing or unexpected footprint'
 exported={}
 for n in tree.findall('nets/net'):
  for p in n.findall('node'):exported[(p.attrib['ref'],p.attrib['pin'])]=n.attrib['name']
 for ref,p in parts.items():
  f=fps[ref];assert f[1]==p['footprint'],ref
  uid=lambda key:str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/carrier-reva/'+key))
  assert one(f,'path')[1]=='/'+uid('root')+'/'+uid(ref),(ref,'schematic path')
  pads=children(f,'pad');assert {pad[1] for pad in pads}=={str(n) for n,_,_,_ in p['pins']},ref
  for pad in pads:
   want=next(net for n,_,_,net in p['pins'] if str(n)==pad[1]);ns=children(pad,'net');got=ns[0][-1] if ns else None
   if want is None:assert got is None or got.startswith('unconnected-'),(ref,pad[1],got)
   else:assert got==exported[(ref,pad[1])]=='/'+want,(ref,pad[1],got,want)
 # Existing decoupling, isolator and module placement must survive this ECO.
 baseline=parse((ROOT/'hardware/carrier/carrier.kicad_pcb').read_text())
 for f in children(baseline,'footprint'):
  ref=next(x[2] for x in children(f,'property') if x[1]=='Reference')
  assert one(fps[ref],'at')==one(f,'at'),(ref,'baseline placement changed')
 copper=[x[1] for x in one(board,'layers')[1:] if isinstance(x,list) and x[1].endswith('.Cu')]
 assert copper==['F.Cu','In1.Cu','In2.Cu','B.Cu'],copper
 zones=children(board,'zone');hold=[z for z in zones if children(z,'keepout')];assert len(hold)==1
 assert set(one(hold[0],'layers')[1:])=={'F.Cu','In1.Cu','In2.Cu','B.Cu'}
 for flag in ['tracks','vias','copperpour']:assert one(one(hold[0],'keepout'),flag)[1]=='not_allowed'
 for layer in ['In1.Cu','In2.Cu']:
  z=next(z for z in zones if children(z,'layer') and one(z,'layer')[1]==layer)
  assert one(z,'net')[-1]=='/GND' and children(z,'filled_polygon')
 assert all(one(t,'layer')[1] in ('F.Cu','B.Cu') for t in children(board,'segment')),'signal route on ground plane'
 if (BASE/'routes.json').exists():
  routes=json.loads((BASE/'routes.json').read_text())
  assert routes['baseline_sha256']==hashlib.sha256((ROOT/'hardware/carrier/carrier.kicad_pcb').read_bytes()).hexdigest()
  xy=lambda p:tuple(round(float(v),6) for v in p)
  def segment(net,layer,width,a,z):return (net,layer,round(float(width),6),tuple(sorted([xy(a),xy(z)])))
  def track(t):return segment(one(t,'net')[-1],one(t,'layer')[1],one(t,'width')[1],one(t,'start')[1:],one(t,'end')[1:])
  expected=Counter(track(t) for t in children(baseline,'segment') if one(t,'net')[-1].removeprefix('/') not in routes['replace_nets'])
  expected.update(segment('/'+t['net'],t['layer'],t['width'],t['start'],t['end']) for t in routes['tracks'])
  assert Counter(track(t) for t in children(board,'segment'))==expected,'copper segment mismatch'
  def via(v):return (one(v,'net')[-1],xy(one(v,'at')[1:]),float(one(v,'size')[1]),float(one(v,'drill')[1]))
  expected=Counter(via(v) for v in children(baseline,'via') if one(v,'net')[-1].removeprefix('/') not in routes['replace_nets'])
  expected.update(('/'+v['net'],xy(v['at']),v['diameter'],v['drill']) for v in routes['vias'])
  assert Counter(via(v) for v in children(board,'via'))==expected,'copper via mismatch'

 return {'placed_components':len(parts),'mounting_holes':4,'inner_ground_planes':2}
def main():
 p=argparse.ArgumentParser();p.add_argument('--netlist',type=Path,default=BASE/'carrier.net.xml');p.add_argument('--allow-open',action='store_true',help='Engineering review only: report ordinary opens instead of rejecting them');p.add_argument('--drc',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
 c=json.loads((BASE/'connections.json').read_text());tree=ET.parse(a.netlist).getroot();board=parse((BASE/'carrier.kicad_pcb').read_text())
 review=json.loads((BASE/'pcb-review.json').read_text());assert review['fabrication_ready'] is False
 assert review['board_sha256']==hashlib.sha256((BASE/'carrier.kicad_pcb').read_bytes()).hexdigest(),'stale board review metadata'
 r=check_contract(c,tree);r.update(check_board(c,tree,board));r.update(schema=1,hardware_executed=False,fabrication_ready=False)
 if a.drc:
  r.update(check_drc(board,json.loads(a.drc.read_text()),require_only_held=not a.allow_open))
  r['drc_note']='Rev A review only: all opens, including SD, block fabrication.'
 r['source_sha256']={str(f.resolve().relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [BASE/'connections.json',a.netlist,BASE/'carrier.kicad_pcb']}
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print('Rev A contract PASS:',r['placed_components'],'components; keyed harness, reserve rails, interlocks, four-layer net parity')
if __name__=='__main__':main()
