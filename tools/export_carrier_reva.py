#!/usr/bin/env python3
"""Export and independently render Rev A fabrication candidates (not order approval)."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SUFFIXES=['gtl','g1','g2','gbl','gts','gbs','gto','gbo','gm1']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def drill_checks(out):
 def read(path):
  text=path.read_text();assert 'METRIC' in text and 'G90' in text
  tools={m[1]:float(m[2]) for m in re.finditer(r'^T(\d+)C([0-9.]+)$',text,re.M)}
  hits=[];tool=None
  for line in text.splitlines():
   m=re.fullmatch(r'T(\d+)',line)
   if m:tool=m[1]
   m=re.fullmatch(r'X(-?[0-9.]+)Y(-?[0-9.]+)',line)
   if m:hits.append((float(m[1]),-float(m[2]),tools[tool]))
  return hits
 pth=read(out/'carrier-PTH.drl');npth=read(out/'carrier-NPTH.drl')
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
 subprocess.run(['kicad-cli','pcb','export','gerbers',str(board),'--layers','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts','--subtract-soldermask','--no-x2','--no-netlist','--output',str(out)+'/'],check=True)
 subprocess.run(['kicad-cli','pcb','export','drill',str(board),'--excellon-separate-th','--output',str(out)+'/'],check=True)
 files=[next(out.glob('*.'+suffix)) for suffix in SUFFIXES]+[out/'carrier-PTH.drl',out/'carrier-NPTH.drl']
 assert all(p.is_file() and p.stat().st_size for p in files)
 # gerbv is a separate RS-274X/Excellon parser, not a KiCad PCB screenshot.
 renders=out/'inspection';renders.mkdir()
 for p in files:
  result=subprocess.run(['gerbv','-x','png','-w','1200x1600','-b','#ffffff','-f','#202020','-o',str(renders/(p.name+'.png')),str(p)],text=True,capture_output=True,check=True)
  (renders/(p.name+'.log')).write_text(result.stdout+result.stderr)
  assert not result.stderr.strip(),('independent parser diagnostic',p.name,result.stderr)
 r=dict(drill_checks=drill_checks(out),schema=1,kind='fabrication-candidate-not-order-approved',fabrication_ready=False,hardware_qualified=False,independent_parser='gerbv',visual_review_complete=False,board_sha256=sha(board),files={p.name:sha(p) for p in files})
 (out/'manifest.json').write_text(json.dumps(r,indent=2)+'\n')
 (out/'README.txt').write_text('FABRICATION CANDIDATE FOR REVIEW ONLY. Not an order release.\nFour layers F.Cu/In1.Cu/In2.Cu/B.Cu. Both inner layers GND.\nSee hardware/carrier-reva/manufacturing.md for stack-up and acceptance gates.\n')
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();export(a.out.resolve())
