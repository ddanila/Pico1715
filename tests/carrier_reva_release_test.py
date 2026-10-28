#!/usr/bin/env python3
"""Exercise exact-byte review binding without invoking CAD or a supplier."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import export_carrier_reva as e
class CandidateTests(unittest.TestCase):
 def test_candidate_binding(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);files={}
   for name in ['F_Cu.gtl','In1_Cu.g1','In2_Cu.g2','B_Cu.gbl','F_Mask.gts','B_Mask.gbs','F_Silkscreen.gto','B_Silkscreen.gbo','Edge_Cuts.gm1','PTH.drl','NPTH.drl']:
    p=d/('carrier-'+name);p.write_text('fixture '+name);files[p.name]=e.sha(p)
   digest=e.sha(ROOT/'hardware/carrier-reva/carrier.kicad_pcb')
   m=dict(schema=2,source_sha256=e.source_hashes(),board_sha256=digest,files=files)
   review=dict(inspected_export_sha256=files,board_sha256=digest)
   def save(value):(d/'manifest.json').write_text(json.dumps(value))
   save(m);self.assertEqual(e.verify_candidate(d,review),m)
   sealed=d/'sealed';e.copy_reviewed_exports(d,sealed,review)
   self.assertEqual({p.name:e.sha(p) for p in sealed.iterdir()},files)
   with self.assertRaises(FileExistsError):e.copy_reviewed_exports(d,sealed,review)
   for field,value in [('schema',1),('source_sha256',{}),('board_sha256','stale'),('files',{})]:
    bad=copy.deepcopy(m);bad[field]=value;save(bad)
    with self.assertRaises(AssertionError):e.verify_candidate(d,review)
   save(m)
   with self.assertRaises(AssertionError):e.verify_candidate(d,dict(review,inspected_export_sha256={}))
   p=d/'carrier-F_Cu.gtl';original=p.read_bytes();p.write_bytes(original+b' changed')
   with self.assertRaises(AssertionError):e.verify_candidate(d,review)
   p.unlink()
   with self.assertRaises(AssertionError):e.verify_candidate(d,review)
   p.write_bytes(original);self.assertEqual(e.verify_candidate(d,review),m)
 def test_all_holes_and_outline(self):
  # Small board fixture with independently specified exported coordinates.
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);base=root/'hardware/carrier-reva';base.mkdir(parents=True)
   pads=''.join(f'(pad "{n}" thru_hole circle (at {0 if n%2 else 2.54} {((n-1)//2)*2.54}) (drill 1.1))' for n in range(1,61))
   reserve=''.join(f'(pad "{n+1}" thru_hole circle (at {n*2.5} 0) (drill .95))' for n in range(3))
   mounts=''.join(f'(footprint "mount" (at {x} {y}) (pad "" np_thru_hole circle (at 0 0) (drill 3.2)))' for x,y in [(24,24),(24,226),(157,24),(176,226)])
   (base/'carrier.kicad_pcb').write_text(f'(board (footprint "header" (at 60 215 90) {pads}) (footprint "reserve" (at 164 100) {reserve}) {mounts} (via (at 42.12345 56.78945) (drill .3)))')
   pth='METRIC\nG90\nT1C1.1\nT2C0.95\nT3C0.3\nT1\n'+''.join(f'X{60+((n-1)//2)*2.54:.3f}Y{-215 if n%2 else -212.46}\n' for n in range(1,61))+'T2\nX164Y-100\nX166.5Y-100\nX169Y-100\nT3\nX42.123Y-56.789\n'
   (root/'carrier-PTH.drl').write_text(pth)
   (root/'carrier-NPTH.drl').write_text('METRIC\nG90\nT1C3.2\nT1\nX24Y-24\nX24Y-226\nX157Y-24\nX176Y-226\n')
   outline='%FSLAX46Y46*%\n%MOMM*%\nX20000000Y-20000000D02*\nX180000000Y-20000000D01*\nX180000000Y-230000000D01*\nX20000000Y-230000000D01*\n'
   (root/'carrier-Edge_Cuts.gm1').write_text(outline)
   with patch.object(e,'ROOT',root):
    self.assertEqual(e.drill_checks(root)['plated_round_holes'],64)
    for broken in [pth.replace('X42.123Y-56.789\n',''),pth+'X42.123Y-56.789\n',pth.replace('T3C0.3','T3C0.4'),pth.replace('X42.123','X42.125')]:
     (root/'carrier-PTH.drl').write_text(broken)
     with self.assertRaises(AssertionError):e.drill_checks(root)
    (root/'carrier-PTH.drl').write_text(pth)
    (root/'carrier-Edge_Cuts.gm1').write_text(outline.replace('180000000','181000000'))
    with self.assertRaises(AssertionError):e.drill_checks(root)
if __name__=='__main__':unittest.main()

