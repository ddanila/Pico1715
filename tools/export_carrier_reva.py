#!/usr/bin/env python3
"""Export and independently render Rev A fabrication candidates (not order approval)."""
import argparse,hashlib,json,re,subprocess,math,shutil
from check_carrier_pcb import parse,children,one
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SUFFIXES=['gtl','g1','g2','gbl','gts','gbs','gto','gbo','gm1']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source_hashes():
 base=ROOT/'hardware/carrier-reva'
 paths=[p for p in base.rglob('*') if p.is_file() and p.suffix in {'.kicad_pcb','.kicad_sch','.kicad_pro','.kicad_mod','.kicad_sym'}]
 paths += [base/n for n in ['connections.json','assembly-review.json','routes.json','connector-review.json','sd-land-pattern.json','manufacturing.md','placement-overrides.json','supplier-process.json','power-review.json','fp-lib-table','sym-lib-table']]
 paths += [ROOT/'reports/carrier-reva-routing.json']
 paths += list((ROOT/'reports/carrier-reva-inspection').glob('*'))
 paths += list((ROOT/'hardware/carrier/Pico1715_Carrier.pretty').glob('*.kicad_mod'))
 paths += [ROOT/'tools'/n for n in ['check_carrier_reva.py','check_carrier.py','check_carrier_pcb.py','export_carrier_reva.py','check_reva_release.py','package_carrier_reva.py','review_reva_power.py','generate_carrier_reva_pcb.py']]
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}

def verify_candidate(directory,review):
 m=json.loads((directory/'manifest.json').read_text())
 assert m.get('schema')==2,'unsupported candidate manifest'
 assert m.get('source_sha256')==source_hashes(),'stale fabrication candidate source'
 assert m.get('board_sha256')==sha(ROOT/'hardware/carrier-reva/carrier.kicad_pcb'),'stale candidate board'
 expected={'carrier-'+n for n in ['F_Cu.gtl','In1_Cu.g1','In2_Cu.g2','B_Cu.gbl','F_Mask.gts','B_Mask.gbs','F_Silkscreen.gto','B_Silkscreen.gbo','Edge_Cuts.gm1','PTH.drl','NPTH.drl']}
 assert set(m['files'])==expected,'missing or unexpected fabrication file'
 assert review.get('inspected_export_sha256')==m['files'],'exports differ from reviewed files'
 for name,digest in m['files'].items():
  p=directory/name
  assert p.is_file() and not p.is_symlink() and sha(p)==digest,('changed fabrication file',name)
 assert review.get('board_sha256')==m['board_sha256'],'stale inspection'
 return m

def copy_reviewed_exports(candidate,destination,review):
 m=verify_candidate(candidate,review)
 destination.mkdir()
 for name,digest in m['files'].items():
  shutil.copyfile(candidate/name,destination/name)
  assert sha(destination/name)==digest,('export changed while copying',name)
 verify_candidate(candidate,review)
 return m

def drill_checks(out):
 def read(path):
  text=path.read_text();assert 'METRIC' in text and 'G90' in text
  assert not re.search(r'G85|G00|M15|M16',text),'unexpected slots: update independent slot comparison before release'
  tools={m[1]:float(m[2]) for m in re.finditer(r'^T(\d+)C([0-9.]+)$',text,re.M)}
  hits=[];tool=None
  for line in text.splitlines():
   m=re.fullmatch(r'T(\d+)',line)
   if m:tool=m[1]
   m=re.fullmatch(r'X(-?[0-9.]+)Y(-?[0-9.]+)',line)
   if m:hits.append((float(m[1]),-float(m[2]),tools[tool]))
  return hits
 pth=read(out/'carrier-PTH.drl');npth=read(out/'carrier-NPTH.drl')
 expected_pth=[];expected_npth=[]
 board=parse((ROOT/'hardware/carrier-reva/carrier.kicad_pcb').read_text())
 key=lambda x,y,d:(x,y,round(d,3))
 for v in children(board,'via'):
  x,y=map(float,one(v,'at')[1:3]);expected_pth.append(key(x,y,float(one(v,'drill')[1])))
 for f in children(board,'footprint'):
  at=list(map(float,one(f,'at')[1:]));fx,fy=at[:2];angle=math.radians(at[2] if len(at)>2 else 0)
  for p in children(f,'pad'):
   drills=children(p,'drill')
   if not drills:continue
   assert len(drills[0])==2,'non-round/offset drill needs explicit comparison'
   x,y=map(float,one(p,'at')[1:3]);d=float(drills[0][1])
   target=expected_npth if p[2]=='np_thru_hole' else expected_pth
   target.append(key(fx+x*math.cos(angle)+y*math.sin(angle),fy-x*math.sin(angle)+y*math.cos(angle),d))
 def match(actual,expected):
  remaining=list(expected)
  for x,y,d in actual:
   matches=[i for i,(xx,yy,dd) in enumerate(remaining) if d==dd and abs(x-xx)<=.000501 and abs(y-yy)<=.000501]
   assert len(matches)==1,('missing/ambiguous drill',x,y,d)
   remaining.pop(matches[0])
  assert not remaining,('unexported drill holes',remaining)
 match(pth,expected_pth);match(npth,expected_npth)
 for n in range(1,61):
  expected=(round(60+((n-1)//2)*2.54,3),215 if n%2 else 212.46,1.1)
  assert expected in pth,('header finished hole',n,expected)
 for n in range(3):assert (164+n*2.5,100,.95) in pth
 assert sorted(npth)==sorted([(24,24,3.2),(24,226,3.2),(157,24,3.2),(176,226,3.2)])
 outline=(out/'carrier-Edge_Cuts.gm1').read_text()
 assert '%FSLAX46Y46*%' in outline and '%MOMM*%' in outline
 points={(int(x)/1e6,-int(y)/1e6) for x,y in re.findall(r'X(-?\d+)Y(-?\d+)D0[12]\*',outline)}
 assert points=={(20,20),(180,20),(180,230),(20,230)},'outline dimensions/orientation'
 return dict(outline_mm=[160,210],plated_round_holes=len(pth),nonplated_round_holes=len(npth),j6_holes=60,j7_holes=3)

def export(out):
 if out.exists():raise ValueError('Use a fresh output directory')
 out.mkdir(parents=True);board=ROOT/'hardware/carrier-reva/carrier.kicad_pcb'
 sources=source_hashes();board_digest=sha(board)
 subprocess.run(['kicad-cli','pcb','export','gerbers',str(board),'--layers','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts','--subtract-soldermask','--disable-aperture-macros','--no-x2','--no-netlist','--output',str(out)+'/'],check=True)
 subprocess.run(['kicad-cli','pcb','export','drill',str(board),'--excellon-separate-th','--output',str(out)+'/'],check=True)
 files=[next(out.glob('*.'+suffix)) for suffix in SUFFIXES]+[out/'carrier-PTH.drl',out/'carrier-NPTH.drl']
 assert all(p.is_file() and p.stat().st_size for p in files)
 # gerbv is a separate RS-274X/Excellon parser, not a KiCad PCB screenshot.
 renders=out/'inspection';renders.mkdir()
 for p in files:
  result=subprocess.run(['gerbv','-x','png','-w','1200x1600','-b','#ffffff','-f','#202020','-o',str(renders/(p.name+'.png')),str(p)],text=True,capture_output=True,check=True)
  (renders/(p.name+'.log')).write_text(result.stdout+result.stderr)
  assert not result.stderr.strip(),('independent parser diagnostic',p.name,result.stderr)
 assert source_hashes()==sources and sha(board)==board_digest,'source changed during export'
 r=dict(source_sha256=sources,drill_checks=drill_checks(out),schema=2,kind='fabrication-candidate-not-order-approved',fabrication_ready=False,hardware_qualified=False,independent_parser='gerbv',visual_review_complete=False,board_sha256=sha(board),files={p.name:sha(p) for p in files})
 (out/'manifest.json').write_text(json.dumps(r,indent=2)+'\n')
 (out/'README.txt').write_text('FABRICATION CANDIDATE FOR REVIEW ONLY. Not an order release.\nFour layers F.Cu/In1.Cu/In2.Cu/B.Cu. Both inner layers GND.\nSee hardware/carrier-reva/manufacturing.md for stack-up and acceptance gates.\n')
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();export(a.out.resolve())
