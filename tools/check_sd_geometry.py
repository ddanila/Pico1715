#!/usr/bin/env python3
"""Catalog-datum comparison; deliberately does not release the SD routing hold."""
import hashlib,json,math
from pathlib import Path
from check_carrier_pcb import parse,children,one
ROOT=Path(__file__).resolve().parents[1]
def check(board):
 f=next(f for f in children(board,'footprint') if any(p[1:3]==['Reference','J3'] for p in children(f,'property')))
 # Datasheet page 3: local datum = pin-1 centre X, bottom edge of signal lands Y.
 x,y=2.775,-7.125
 expected=[(str(i+1),x-1.1*i,y-.6,.7,1.2) for i in range(8)]
 expected += [('9',x-8.65,y-.6,.7,1.2),('10',x-9.6,y+9.9,1,.8),('SH',x-9.6,y+3.7,1,1.2),('SH',x-9.6,y+14.05,1,2.8),('SH',x+1.55,y-.6,1,1.2),('SH',x+3.9,y+14.5,1.3,1.9)]
 pads=[]
 for p in children(f,'pad'):
  pads.append((p[1],*map(float,one(p,'at')[1:3]),*map(float,one(p,'size')[1:3])))
 rounded=lambda row:(row[0],*(round(v,4) for v in row[1:]))
 assert sorted(map(rounded,pads))==sorted(map(rounded,expected))
 rectangles=[(x-10,y-.15,x-9.25,y+3.1),(x-10,y+4.3,x-9.25,y+7.9),(x-8.9,y+5.7,x-8.2,y+13.3),(x+.15,y+14.1,x+2.7,y+15.45),(x-8.2,y+4.4,x+.5,y+6)]
 actual=[]
 for z in children(f,'zone'):
  points=[list(map(float,p[1:])) for p in one(one(z,'polygon'),'pts')[1:]]
  points=[[169-p[0],38-p[1]] for p in points]
  assert len(points)==4 and len({tuple(round(v,4) for v in p) for p in points})==4
  actual.append((min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)))
  assert one(z,'layer')[1]=='F.Cu'
  keep=one(z,'keepout');assert all(one(keep,n)[1]=='not_allowed' for n in ['tracks','vias','copperpour'])
 assert sorted(tuple(round(v,4) for v in r) for r in actual)==sorted(tuple(round(v,4) for v in r) for r in rectangles)
 at=list(map(float,one(f,'at')[1:]));assert at==[169,38,180]
 # Catalog body rear edge at local Y=-7.825, card CL at X=-.425.
 card=[169-5.075,38-13.725,169+5.925,38-(-7.825)]
 mount_clearances=[]
 for fp in children(board,'footprint'):
  ref=next(p[2] for p in children(fp,'property') if p[1]=='Reference')
  if ref not in ['H1','H2','H3','H4']:continue
  hx,hy=map(float,one(fp,'at')[1:3])
  # Reserve a 6.4 mm diameter head/courtyard around each provisional M3 hole.
  dx=max(card[0]-hx,0,hx-card[2]);dy=max(20-hy,0,hy-29.875)
  distance=math.hypot(dx,dy);assert distance>=3.2,(ref,'SD access collision')
  mount_clearances.append(dict(ref=ref,centre_mm=[hx,hy],clearance_to_access_mm=round(distance-3.2,3)))
 result=dict(schema=1,mounting_clearances=mount_clearances,routing_released=False,hardware_executed=False,pad_comparisons=14,exclusion_rectangles=5,local_datum_mm=[x,y],local_exclusion_bounds_mm=rectangles,card_ejected_envelope_board_mm=card,mouth_board_y_mm=29.875,ejected_tip_board_y_mm=24.275,board_north_edge_y_mm=20,limitations=['Catalog confirms installed pad/exclusion geometry but is not current engineering-drawing revision approval.','Lower-right exclusion extends conservatively to lower shield-land edge, 15.45 mm from datum; catalog labels its upper edge 14.1 MAX.','Card ejection envelope extends north of the existing copper hold (Y=28); reserve mechanical access to the board edge.','Enclosure/finger access and actual socket fit still need verification.'],source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'hardware/carrier/carrier.kicad_pcb']})
 return result
def main():
 result=check(parse((ROOT/'hardware/carrier/carrier.kicad_pcb').read_text()))
 (ROOT/'reports/sd-geometry.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS 14 lands and 5 catalog-derived exclusions; hold retained')
if __name__=='__main__':main()
