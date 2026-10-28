#!/usr/bin/env python3
"""Propose nearby GND transitions; DRC still required."""
import argparse,json,math
from pathlib import Path
import numpy as np
import pcbnew as k
from import_carrier_routing import point
POWER={'GND','V3P3','P3V3','V5_HOST','V5_MODULE','P_VSYS'}
def stitch(board,routes,out,max_distance=2,whole_board=False):
 b=k.LoadBoard(str(board));r=json.loads(routes.read_text());lines=[];rects=[];holes=[];ground=[]
 for t in b.GetTracks():
  if isinstance(t,k.PCB_VIA):
   p=point(t.GetPosition());holes.append(p+[k.ToMM(t.GetDrillValue())/2+.15+.27])
   if t.GetNetname()=='/GND':ground.append(p);continue
   lines.append(p+p+[k.ToMM(t.GetWidth(k.F_Cu))/2+.3+.23])
  elif t.GetNetname()!='/GND':lines.append(point(t.GetStart())+point(t.GetEnd())+[k.ToMM(t.GetWidth())/2+.3+.23])
 for f in b.GetFootprints():
  for p in f.Pads():
   if p.GetDrillSize().x:
    holes.append(point(p.GetPosition())+[k.ToMM(max(p.GetDrillSize().x,p.GetDrillSize().y))/2+.15+.27])
    if p.GetNetname()=='/GND':ground.append(point(p.GetPosition()))
   if p.GetNetname()=='/GND':continue
   bb=p.GetBoundingBox();rects.append([k.ToMM(bb.GetLeft())-.53,k.ToMM(bb.GetTop())-.53,k.ToMM(bb.GetRight())+.53,k.ToMM(bb.GetBottom())+.53])
 lines=np.array(lines);rects=np.array(rects);holes=np.array(holes);delta=lines[:,2:4]-lines[:,:2];length2=np.sum(delta*delta,axis=1);length2[length2==0]=1
 planes={z.GetLayer():z for z in b.Zones() if not z.GetIsRuleArea()}
 def free(p):
  x,y=p
  if not(21.6<x<178.4 and 21.6<y<228.4) or (160.47<x<175.53 and 29.57<y<38.43):return False
  if np.any((x>=rects[:,0])&(x<=rects[:,2])&(y>=rects[:,1])&(y<=rects[:,3])):return False
  t=np.clip(np.sum((p-lines[:,:2])*delta,axis=1)/length2,0,1)
  if np.any(np.sum((p-lines[:,:2]-t[:,None]*delta)**2,axis=1)<lines[:,4]**2):return False
  if np.any(np.sum((p-holes[:,:2])**2,axis=1)<holes[:,2]**2):return False
  return all(planes[l].HitTestFilledArea(l,k.VECTOR2I(round(x*1e6),round(y*1e6))) for l in [k.In1_Cu,k.In2_Cu])
 added=[];unresolved=[]
 candidates=[dict(net=t.GetNetname().removeprefix('/'),at=point(t.GetPosition())) for t in b.GetTracks() if isinstance(t,k.PCB_VIA)] if whole_board else list(r['vias'])
 for v in candidates:
  if v['net'] in POWER or min(math.dist(v['at'],g) for g in ground)<=max_distance:continue
  found=None
  for radius in np.arange(.9,max_distance,.2):
   for degrees in range(0,360,15):
    p=[round(v['at'][0]+radius*math.cos(math.radians(degrees)),6),round(v['at'][1]+radius*math.sin(math.radians(degrees)),6)]
    if min(math.dist(p,g) for g in ground)<.65:continue
    if free(p):found=p;break
   if found:break
  if not found:
   offsets=sorted(((x/10,y/10) for x in range(-int(max_distance*10),int(max_distance*10)+1) for y in range(-int(max_distance*10),int(max_distance*10)+1) if .81<(x*x+y*y)/100<=max_distance**2),key=lambda p:p[0]**2+p[1]**2)
   for dx,dy in offsets:
    p=[round(v['at'][0]+dx,6),round(v['at'][1]+dy,6)]
    if min(math.dist(p,g) for g in ground)>=.65 and free(p):found=p;break
  if not found:unresolved.append(v);continue
  ground.append(found);added.append(dict(net='GND',at=found,diameter=.6,drill=.3))
 r['vias']+=added;unresolved=[v for v in unresolved if min(math.dist(v['at'],g) for g in ground)>max_distance];r['ground_stitching']=dict(total_supplemental_ground_vias=sum(v['net']=='GND' for v in r['vias']),whole_board=whole_board,target_max_distance_mm=max_distance,added=len(added),unresolved=unresolved,review_note='Geometric candidates only; regenerate, refill and independently DRC-check.')
 out.write_text(json.dumps(r,indent=2)+'\n');print('Added',len(added),'GND candidates;',len(unresolved),'signal vias remain beyond',max_distance,'mm')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('board',type=Path);p.add_argument('routes',type=Path);p.add_argument('out',type=Path);p.add_argument('--max-distance',type=float,default=2);p.add_argument('--all-signals',action='store_true');a=p.parse_args();assert .9<a.max_distance<=5;stitch(a.board,a.routes,a.out,a.max_distance,a.all_signals)
