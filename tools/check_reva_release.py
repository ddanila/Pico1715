#!/usr/bin/env python3
"""Keep engineering review, prototype fabrication and hardware qualification separate."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def release_blockers(geometry,review,board_hash,dirty):
 blockers=[]
 if dirty:blockers.append('working tree is not clean')
 if review.get('board_sha256')!=board_hash:blockers.append('assembly/fabrication review is missing or stale')
 for field in ['plane_gaps_reviewed','assembly_access_reviewed','fabrication_exports_reviewed','supplier_hole_tolerance_confirmed']:
  if review.get(field) is not True:blockers.append(field)
 if not geometry.get('signal_via_returns'):blockers.append('missing full-board signal via review')
 elif any(v['nearest_ground_transition_mm']>4 for v in geometry['signal_via_returns']):blockers.append('signal return transitions exceed 4 mm')
 for net,limit,vias in [('F_CLK',170,11),('F_WR_N',184,10)]:
  n=geometry.get('nets',{}).get(net,{})
  # See metrics() output: total routed copper includes branches.
  if n.get('copper_length_mm',float('inf'))>limit or n.get('vias',float('inf'))>vias:blockers.append(net+' routing budget')
 return blockers

def check_release():
 board=ROOT/'hardware/carrier-reva/carrier.kicad_pcb'
 geometry=json.loads((ROOT/'reports/carrier-reva-routing.json').read_text())
 for name,digest in geometry['source_sha256'].items():
  assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,('stale geometry',name)
 review_path=ROOT/'hardware/carrier-reva/release-review.json'
 review=json.loads(review_path.read_text()) if review_path.exists() else {}
 dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
 blockers=release_blockers(geometry,review,hashlib.sha256(board.read_bytes()).hexdigest(),dirty)
 if blockers:raise SystemExit('Prototype fabrication blocked: '+ '; '.join(blockers))
 return review
