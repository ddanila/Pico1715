#!/usr/bin/env python3
"""Build a source-hashed engineering review bundle, never an order ZIP.

An order package remains blocked until the named mechanical and routing reviews
are implemented. Reports are regenerated from this board, not accepted by name.
"""
import argparse,hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
from check_carrier_reva import check_contract,check_board
from check_carrier_pcb import parse,check_drc
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'hardware/carrier-reva'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def package(out):
 if out.exists():raise SystemExit('Use a new output directory to avoid mixing evidence.')
 out.mkdir(parents=True)
 c=json.loads((BASE/'connections.json').read_text());board=parse((BASE/'carrier.kicad_pcb').read_text())
 shutil.copyfile(BASE/'carrier.kicad_pro',out/'carrier.kicad_pro')
 for name in ['carrier.kicad_sch','RevA.kicad_sym','sym-lib-table','fp-lib-table','carrier.kicad_pcb','connections.json','bom.tsv','pcb-review.json']:
  shutil.copyfile(BASE/name,out/name)
 shutil.copytree(ROOT/'hardware/carrier/Pico1715_Carrier.pretty',out/'Pico1715_Carrier.pretty')
 (out/'fp-lib-table').write_text((out/'fp-lib-table').read_text().replace('${KIPRJMOD}/../carrier/Pico1715_Carrier.pretty','${KIPRJMOD}/Pico1715_Carrier.pretty'))
 for path in BASE.glob('*.md'):shutil.copyfile(path,out/path.name)
 if (BASE/'routes.json').exists():shutil.copyfile(BASE/'routes.json',out/'routes.json')
 geometry=ROOT/'reports/carrier-reva-routing.json'
 if geometry.exists():
  evidence=json.loads(geometry.read_text())
  for name,digest in evidence['source_sha256'].items():assert sha(ROOT/name)==digest,('stale routing review',name)
  shutil.copyfile(geometry,out/'routing-review.json')
 # Export from the canonical source so library paths resolve correctly.
 subprocess.run(['kicad-cli','sch','erc',str(BASE/'carrier.kicad_sch'),'--exit-code-violations','-o',str(out/'erc.rpt')],check=True)
 subprocess.run(['kicad-cli','sch','export','netlist',str(BASE/'carrier.kicad_sch'),'--format','kicadxml','-o',str(out/'carrier.net.xml')],check=True)
 subprocess.run(['kicad-cli','pcb','drc',str(BASE/'carrier.kicad_pcb'),'--format','json','-o',str(out/'drc.json')],check=True)
 for name,layers in [('front','F.Cu,F.SilkS,Edge.Cuts'),('back','B.Cu,Edge.Cuts'),('ground-1','In1.Cu,Edge.Cuts'),('ground-2','In2.Cu,Edge.Cuts')]:
  subprocess.run(['kicad-cli','pcb','export','svg',str(BASE/'carrier.kicad_pcb'),'--layers',layers,'--mode-single','--fit-page-to-board','--exclude-drawing-sheet','-o',str(out/(name+'.review.svg'))],check=True)
 tree=ET.parse(out/'carrier.net.xml').getroot();r=check_contract(c,tree);r.update(check_board(c,tree,board))
 r.update(check_drc(board,json.loads((out/'drc.json').read_text()),require_only_held=False))
 r['drc_note']='Rev A engineering review only; all opens, including SD, block fabrication.'
 r.update(schema=1,fabrication_ready=False,hardware_executed=False,holds=c['holds'])
 (out/'review.json').write_text(json.dumps(r,indent=2)+'\n')
 (out/'harness.tsv').write_text('IDC pin\tEFS contact\tNet\n'+''.join(f"{x['pin']}\t{x['contact']}\t{x['net'] or 'NC'}\n" for x in c['host_harness']['pins'])+'59\t-\tNC\n60\t-\tNC\n')
 (out/'README.txt').write_text('ENGINEERING REVIEW ONLY — NOT FOR FABRICATION\nNo manufacturing Gerbers or purchase approval.\nProject-local custom footprints and symbols are included; standard KiCad 10 footprint libraries are required.\nOpen gates: '+ '; '.join(c['holds'])+'\nAll ordinary and SD airwires must be closed before release.\n')
 files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
 manifest=dict(schema=1,kind='engineering-review-not-for-fabrication',fabrication_ready=False,working_tree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sorted(BASE.iterdir()) if p.is_file() and p.suffix!='.kicad_prl'},files=files)
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 archive=out.with_suffix('.review.zip')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(out.rglob('*')):
   if p.is_file():z.write(p,str(p.relative_to(out)))
 print('Review bundle:',archive,'— fabrication BLOCKED')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();package(a.out.resolve())
