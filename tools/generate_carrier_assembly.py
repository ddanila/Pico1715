#!/usr/bin/env python3
"""Create component-side assembly/probe coordinates from the actual board."""
import hashlib,json,html
from pathlib import Path
import pcbnew as k
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'hardware/carrier'
b=k.LoadBoard(str(base/'carrier.kicad_pcb'));parts=[];probes=[]
for fp in sorted(b.GetFootprints(),key=lambda f:f.GetReference()):
 ref=fp.GetReference();pads=[]
 for p in fp.Pads():
  n=p.GetNumber()
  if n in ['1','A1'] or ref in ['J1','J4','J5','J2','D1','SW1']:
   pos=p.GetPosition();pads.append({'pin':n,'net':p.GetNetname().lstrip('/'),'xy_mm':[round(k.ToMM(pos.x),4),round(k.ToMM(pos.y),4)]})
 parts.append({'ref':ref,'value':fp.GetValue(),'xy_mm':[k.ToMM(fp.GetPosition().x),k.ToMM(fp.GetPosition().y)],'rotation_deg':fp.GetOrientationDegrees(),'pads':pads})
 if ref=='J5':probes=pads
report={'schema':1,'hardware_executed':False,'view':'component side; coordinates in board mm','parts':parts,'probe_header':probes,'source_sha256':{'hardware/carrier/carrier.kicad_pcb':hashlib.sha256((base/'carrier.kicad_pcb').read_bytes()).hexdigest()}}
(base/'assembly-points.json').write_text(json.dumps(report,indent=2)+'\n')
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1160" viewBox="10 8 180 232"><rect x="10" y="8" width="180" height="232" fill="white"/><rect x="20" y="20" width="160" height="210" fill="#f4f8fb" stroke="#223344" stroke-width="0.3"/><g font-family="sans-serif">']
svg.append('<text x="22" y="14" font-size="3">Pico1715 component-side assembly locator</text><text x="22" y="18" font-size="1.8">Dots mark pad 1; schematic and footprint define polarity. PROVISIONAL.</text>')
for part in parts:
 x,y=part['xy_mm'];ref=part['ref'];svg.append(f'<circle cx="{x}" cy="{y}" r="1" fill="#acc7dc"/><text x="{x+1.4}" y="{y-.7}" font-size="1.8">{html.escape(ref)}</text>')
 for pad in part['pads']:
  if pad['pin'] in ['1','A1']:
   px,py=pad['xy_mm'];svg.append(f'<circle cx="{px}" cy="{py}" r=".4" fill="#b52020"/>')
svg.append('<rect x="160" y="28" width="18" height="19" fill="none" stroke="#c43b29" stroke-width=".4"/><text x="22" y="211" font-size="3">X2 UNPLACED — host reservation</text><text x="22" y="218" font-size="2">J4: regulated 5V input. J1: CDONE tap, not programmer.</text><text x="22" y="224" font-size="2">Do not install on a host until geometry and bench gates pass.</text></g></svg>')
(base/'preview/assembly.svg').write_text(''.join(svg)+'\n')
