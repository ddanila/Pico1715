#!/usr/bin/env python3
"""Check and export only the isolated contact-test board, then seal evidence."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'hardware/efs58-coupon'
BUILD=ROOT/'build/efs58-coupon'; BUILD.mkdir(parents=True,exist_ok=True)
FAB=OUT/'fabrication'; FAB.mkdir(exist_ok=True)
def run(*args): subprocess.run(args,cwd=ROOT,check=True)
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
for path,sha in json.loads((OUT/'cad-inputs.json').read_text()).items():
    assert digest(ROOT/path)==sha, 'Regenerate FreeCAD models first: '+path
run('kicad-cli','sch','erc',str(OUT/'coupon.kicad_sch'),'--exit-code-violations','-o',str(BUILD/'erc.rpt'))
run('kicad-cli','pcb','drc',str(OUT/'coupon.kicad_pcb'),'--schematic-parity','--exit-code-violations','-o',str(BUILD/'drc.rpt'))
run('kicad-cli','pcb','export','gerbers',str(OUT/'coupon.kicad_pcb'),'-l','F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,Edge.Cuts','-o',str(FAB)+'/')
run('kicad-cli','pcb','export','drill',str(OUT/'coupon.kicad_pcb'),'--format','excellon','--excellon-units','mm','--excellon-separate-th','-o',str(FAB)+'/')
paths=[*OUT.glob('*.stl'),*OUT.glob('*.step'),*OUT.glob('*.kicad_sch'),
       *OUT.glob('*.kicad_pcb'),*OUT.glob('*.kicad_sym'),*OUT.glob('*.kicad_pro'),
       *OUT.glob('*-lib-table'),*OUT.glob('Coupon.pretty/*'),*FAB.glob('*'),
       OUT/'parameters.json',OUT/'cad-checks.json',OUT/'cad-inputs.json',
       ROOT/'tools/generate_efs58_coupon_pcb.py',ROOT/'tools/generate_efs58_coupon_cad.py']
paths.extend([OUT/'drawing.svg',ROOT/'tools/draw_efs58_coupon.py'])
result={'schema':1,'scope':'unpowered four-contact fixture only','physical_fit':'not tested',
        'kicad_version':subprocess.check_output(['kicad-cli','version'],text=True).strip(),
        'erc_violations':0,'drc_violations':0,'unconnected':0,'schematic_parity_issues':0,
        'sha256':{str(path.relative_to(ROOT)):digest(path) for path in sorted(paths)}}
(OUT/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print('Exported and checked test PCB; EFS mating remains unqualified')
