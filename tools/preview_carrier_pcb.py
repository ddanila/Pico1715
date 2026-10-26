#!/usr/bin/env python3
"""Export readable review previews of the saved partial carrier layout."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'hardware/carrier'
for name,layers in [('pcb-placement','F.Cu,F.SilkS,F.Fab,Dwgs.User,Edge.Cuts'),
                    ('pcb-ground','B.Cu,Edge.Cuts')]:
    path=BASE/'preview'/(name+'.svg')
    subprocess.run(['kicad-cli','pcb','export','svg',str(BASE/'carrier.kicad_pcb'),
                    '--layers',layers,'--page-size-mode','2','--exclude-drawing-sheet',
                    '--mode-single','-o',str(path)],check=True)
    s=path.read_text();index=s.index('>',s.index('<svg'))+1
    s=s[:index]+'\n<rect width="100%" height="100%" fill="#141923"/>\n'+s[index:]
    path.write_text('\n'.join(line.rstrip() for line in s.splitlines())+'\n')
