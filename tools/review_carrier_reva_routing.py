#!/usr/bin/env python3
"""Measure actual Rev A copper and adjacent ground coverage; not SI sign-off."""
import argparse,hashlib,json,math
from collections import defaultdict
from pathlib import Path
import pcbnew as k
from import_carrier_routing import point
from review_carrier_routing import metrics
ROOT=Path(__file__).resolve().parents[1]
def review(path,out):
 b=k.LoadBoard(str(path));plan={'routes':[],'vias':[]};ground=[];antipads=[]
 for t in b.GetTracks():
  net=t.GetNetname().removeprefix('/')
  if isinstance(t,k.PCB_VIA):
   p=point(t.GetPosition());plan['vias'].append(dict(net=net,at=p))
   if net!='GND':antipads.append((p,k.ToMM(t.GetWidth(k.F_Cu))/2+.25))
   if net=='GND':ground.append(p)
  else:plan['routes'].append(dict(net=net,layer=b.GetLayerName(t.GetLayer()),start=point(t.GetStart()),end=point(t.GetEnd()),width=k.ToMM(t.GetWidth())))
 for f in b.GetFootprints():
  for pad in f.Pads():
   if pad.GetDrillSize().x and pad.GetNetname()!='/GND':antipads.append((point(pad.GetPosition()),math.hypot(k.ToMM(pad.GetSize().x),k.ToMM(pad.GetSize().y))/2+.25))
   if pad.GetNetname()=='/GND' and pad.GetAttribute()==k.PAD_ATTRIB_PTH:ground.append(point(pad.GetPosition()))
 nets,parallel=metrics(plan);planes={z.GetLayer():z for z in b.Zones() if not z.GetIsRuleArea()};coverage=defaultdict(lambda:[0,0,0])
 for t in plan['routes']:
  if t['net']=='GND':continue
  layer=k.In1_Cu if t['layer']=='F.Cu' else k.In2_Cu
  length=math.dist(t['start'],t['end']);n=max(1,math.ceil(length/.25));ds=length/n
  for i in range(n):
   p=[t['start'][j]+(i+.5)/n*(t['end'][j]-t['start'][j]) for j in range(2)]
   coverage[t['net']][0]+=ds
   if not planes[layer].HitTestFilledArea(layer,k.VECTOR2I(round(p[0]*1e6),round(p[1]*1e6))):
    coverage[t['net']][1]+=ds
    if not any(math.dist(p,c)<=radius for c,radius in antipads):coverage[t['net']][2]+=ds
 for net,(length,uncovered,away) in coverage.items():
  nets[net]['uncovered_away_from_nominal_antipads_mm']=round(away,3)
  nets[net]['uncovered_near_nominal_antipads_mm']=round(uncovered-away,3)
  nets[net]['adjacent_ground_uncovered_mm']=round(uncovered,3)
  nets[net]['adjacent_ground_uncovered_percent']=round(100*uncovered/length,2) if length else 0
 returns=[dict(net=v['net'],at=v['at'],nearest_ground_transition_mm=round(min(math.dist(v['at'],g) for g in ground),3)) for v in plan['vias'] if v['net'] not in {'GND','V3P3','P3V3','V5_HOST','V5_MODULE','P_VSYS'}]
 result=dict(schema=1,hardware_executed=False,signal_integrity_qualified=False,fabrication_ready=False,method={'sample_step_max_mm':.25,'reference':'F.Cu→In1.Cu; B.Cu→In2.Cu','limits':'Centre-line samples only, not impedance or transient simulation. Antipad classification uses nominal pad/via envelopes plus 0.25 mm clearance; it is a screening classification, not proof of a continuous return path. Copper lengths include branches. Return distance includes GND vias and plated through-hole pads, not ground-path impedance.'},nets=dict(sorted(nets.items())),parallel_candidates=parallel,signal_via_returns=returns,return_target_mm=4,return_outliers=[v for v in returns if v['nearest_ground_transition_mm']>4],source_sha256={str(path.resolve().relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest(),str(Path(__file__).resolve().relative_to(ROOT)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
 out.write_text(json.dumps(result,indent=2)+'\n');print('Rev A geometry review:',len(nets),'nets; not signal-integrity qualification')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',type=Path,default=ROOT/'hardware/carrier-reva/carrier.kicad_pcb');p.add_argument('--out',type=Path,required=True);a=p.parse_args();review(a.board,a.out)
