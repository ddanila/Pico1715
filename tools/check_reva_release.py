#!/usr/bin/env python3
"""Keep engineering review, prototype fabrication and hardware qualification separate."""
import hashlib,json,subprocess,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def release_blockers(geometry,review,board_hash,dirty):
 blockers=[]
 if dirty:blockers.append('working tree is not clean')
 if review.get('board_sha256')!=board_hash:blockers.append('assembly/fabrication review is missing or stale')
 for field in ['plane_gaps_reviewed','assembly_access_reviewed','fabrication_exports_reviewed','supplier_hole_tolerance_confirmed']:
  if review.get(field) is not True:blockers.append(field)
 if not geometry.get('signal_via_returns'):blockers.append('missing full-board signal via review')
 elif any(not isinstance(v.get('nearest_ground_transition_mm'),(int,float)) or not math.isfinite(v['nearest_ground_transition_mm']) or not 0<=v['nearest_ground_transition_mm']<=4 for v in geometry['signal_via_returns']):blockers.append('signal return transitions exceed 4 mm')
 for net,limit,vias in [('F_CLK',170,11),('F_WR_N',184,10)]:
  n=geometry.get('nets',{}).get(net,{})
  # See metrics() output: total routed copper includes branches.
  if not isinstance(n.get('copper_length_mm'),(int,float)) or not math.isfinite(n.get('copper_length_mm',float('inf'))) or not 0<=n.get('copper_length_mm',float('inf'))<=limit or not isinstance(n.get('vias'),int) or not 0<=n['vias']<=vias:blockers.append(net+' routing budget')
 return blockers

def check_release():
 board=ROOT/'hardware/carrier-reva/carrier.kicad_pcb'
 geometry=json.loads((ROOT/'reports/carrier-reva-routing.json').read_text())
 for name,digest in geometry['source_sha256'].items():
  assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,('stale geometry',name)
 review_path=ROOT/'hardware/carrier-reva/release-review.json'
 review=json.loads(review_path.read_text()) if review_path.exists() else {}
 assembly=json.loads((board.parent/'assembly-review.json').read_text())
 assert assembly['board_sha256']==hashlib.sha256(board.read_bytes()).hexdigest(),'stale assembly review'
 for name,digest in assembly['evidence_sha256'].items():
  assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,('stale assembly evidence',name)
 for field in ['plane_gaps_reviewed','assembly_access_reviewed']:
  assert not review.get(field) or assembly.get(field) is True,('unsupported sign-off',field)
 power=json.loads((board.parent/'power-review.json').read_text())
 assert power['board_sha256']==assembly['board_sha256'],'stale power review'
 assert power['tool_sha256']==hashlib.sha256((ROOT/'tools/review_reva_power.py').read_bytes()).hexdigest(),'stale power method'
 supplier=json.loads((board.parent/'supplier-process.json').read_text())
 assert not review.get('supplier_hole_tolerance_confirmed') or supplier.get('order_specific_acceptance') is True,'supplier acceptance not recorded'
 dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
 blockers=release_blockers(geometry,review,hashlib.sha256(board.read_bytes()).hexdigest(),dirty)
 if blockers:raise SystemExit('Prototype fabrication blocked: '+ '; '.join(blockers))
 return review
