#!/usr/bin/env python3
"""Trace-path DC screening, with explicit assumptions; not measured power qualification."""
import argparse,hashlib,heapq,json,math
from pathlib import Path
import pcbnew as k
ROOT=Path(__file__).resolve().parents[1]
def review(board,out):
 b=k.LoadBoard(str(board));result=[]
 xy=lambda p:(round(k.ToMM(p.x),6),round(k.ToMM(p.y),6))
 for net,source,targets,current in [
  ('V5_MODULE',('J4','1'),[('EXT1','1'),('D1','2')],1.0),
  ('P_VSYS',('D1','1'),[('J2','39')],.5),
  ('P3V3',('J2','36'),[('J3','4'),('U12','3')],.2),
  ('V3P3',('EXT1','3'),[(f'RX{i}','20') for i in range(1,6)]+[(f'ISO{i}','20') for i in range(1,4)]+[('U10','3')],.1)]:
  tracks=[];vias=[];pads={};nodes=set();graph={}
  def node(p,layer):return (*p,layer)
  def edge(a,z,r):
   graph.setdefault(a,[]).append((z,r));graph.setdefault(z,[]).append((a,r))
  for t in b.GetTracks():
   if t.GetNetname()!='/'+net:continue
   if isinstance(t,k.PCB_VIA):vias.append(t)
   else:
    a=node(xy(t.GetStart()),t.GetLayer());z=node(xy(t.GetEnd()),t.GetLayer());nodes.update([a,z]);tracks.append((a,z,k.ToMM(t.GetWidth())))
  for f in b.GetFootprints():
   for p in f.Pads():
    if p.GetNetname()!='/'+net:continue
    keys=[node(xy(p.GetPosition()),layer) for layer in [k.F_Cu,k.B_Cu] if p.IsOnLayer(layer)]
    nodes.update(keys);pads[(f.GetReference(),p.GetNumber())]=(p,keys)
  for v in vias:
   a=node(xy(v.GetPosition()),k.F_Cu);z=node(xy(v.GetPosition()),k.B_Cu);nodes.update([a,z])
   # 18 um plated barrel, 1.6 mm board, 20 C resistivity.
   edge(a,z,.01724*.0016/(math.pi*k.ToMM(v.GetDrillValue())*.018))
  for a,z,width in tracks:
   dx=z[0]-a[0];dy=z[1]-a[1];l2=dx*dx+dy*dy
   if not l2:continue
   on=[]
   for p in nodes:
    if p[2]!=a[2]:continue
    t=((p[0]-a[0])*dx+(p[1]-a[1])*dy)/l2
    if -.000001<=t<=1.000001 and math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)<.00001:on.append((t,p))
   on.sort()
   for (_,x),(_,y) in zip(on,on[1:]):edge(x,y,.01724*math.dist(x[:2],y[:2])/(width*35))
  for pad,keys in pads.values():
   for p in nodes:
    if p[2] in [x[2] for x in keys] and pad.HitTest(k.VECTOR2I(round(p[0]*1e6),round(p[1]*1e6))):edge(next(q for q in keys if q[2]==p[2]),p,0)
   for p in keys[1:]:edge(keys[0],p,.002) # conservative plated component barrel approximation
  start=pads[source][1][0];distance={start:0};queue=[(0,start)]
  while queue:
   d,p=heapq.heappop(queue)
   if d!=distance[p]:continue
   for q,r in graph.get(p,[]):
    nd=d+r
    if nd<distance.get(q,float('inf')):distance[q]=nd;heapq.heappush(queue,(nd,q))
  paths=[]
  for target in targets:
   resistance=min(distance.get(p,float('inf')) for p in pads[target][1]);assert math.isfinite(resistance),(net,target,'unresolved conductive path')
   paths.append(dict(target='.'.join(target),trace_and_via_resistance_ohm=round(resistance,5),drop_at_budget_V=round(current*resistance,5)))
  result.append(dict(net=net,source='.'.join(source),assumed_total_rail_budget_A=current,paths=paths))
 r=dict(schema=2,tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),board_sha256=hashlib.sha256(board.read_bytes()).hexdigest(),hardware_qualified=False,method='Shortest conductive trace path at 20 C, nominal 35 um copper and 18 um via barrel; parallel paths ignored. Total rail budget conservatively applied to each path. Pad metal idealized; return plane, connector and diode losses require separate budget. This does not establish thermal or transient limits.',nets=result)
 out.write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--board',type=Path,default=ROOT/'hardware/carrier-reva/carrier.kicad_pcb');p.add_argument('--out',type=Path,required=True);a=p.parse_args();review(a.board,a.out)
