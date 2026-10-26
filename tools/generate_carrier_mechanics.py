#!/usr/bin/env python3
"""Original MIT footprint geometry and conservative, non-fabrication placement study."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'hardware/carrier'
LIB=OUT/'Pico1715_Carrier.pretty';LIB.mkdir(exist_ok=True)
def footprint(name,pads,body):
    w,h=body
    s=f'(footprint "{name}" (version 20250114) (generator "pico1715") (layer "F.Cu") (attr '+('through_hole' if name.startswith('PIM') else 'smd')+')\n'
    s+='(fp_text reference "REF**" (at 0 '+str(-h/2-2)+') (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n'
    for layer,margin in [('F.Fab',0),('F.CrtYd',0.5)]:
        s+=f'(fp_rect (start {-w/2-margin} {-h/2-margin}) (end {w/2+margin} {h/2+margin}) (stroke (width 0.05) (type default)) (fill none) (layer "{layer}"))\n'
    for num,x,y,sx,sy,drill in pads:
        s+=f'(pad "{num}" '+('thru_hole rect' if drill and str(num)=='1' else 'thru_hole oval' if drill else 'smd rect')+f' (at {x} {y}) (size {sx} {sy}) '+(f'(drill {drill}) (layers "*.Cu" "*.Mask")' if drill else '(layers "F.Cu" "F.Paste" "F.Mask")')+')\n'
    mx,my=(-10,-25) if name.startswith('PIM') else (-3.7,2.0)
    s+=f'(fp_circle (center {mx} {my}) (end {mx+0.2} {my}) (stroke (width 0.15) (type default)) (fill solid) (layer "F.SilkS"))\n'
    s+=')\n';(LIB/(name+'.kicad_mod')).write_text(s)
# Manufacturer bottom view reflected about X axis for a component-side PCB view.
# Upper-row numbers are NOT the installed KiCad symbol's 4/5/6 convention.
switch=[(i,x,1.2,1,1.6,0) for i,x in [(1,-2.5),(2,0),(3,2.5)]]+[(i,x,-1.2,1,1.6,0) for i,x in [(5,-2.5),(6,0),(7,2.5)]]
footprint('JS202011JCQN_VendorPins',switch,(9,3.6))
pico=[(i,-8.89,round(-24.13+(i-1)*2.54,3),1.7,1.7,1) for i in range(1,21)]
pico += [(41-i,8.89,round(-24.13+(i-1)*2.54,3),1.7,1.7,1) for i in range(1,21)]
footprint('PIM724_SocketPair',pico,(21,53))
# This is a spatial allocation, not board outline or PCB coordinates.
zones=[dict(name='HX8K Rev B1',x=5,y=5,w=65,h=67,kind='module',note='source-board envelope; mating height pending'),
 dict(name='PIM724 + access',x=78,y=5,w=27,h=64,kind='module',note='21 x 53 module plus connector/access allowance'),
 dict(name='microSD + eject',x=112,y=5,w=20,h=30,kind='access',note='card stroke and finger space; no routing beneath restricted areas'),
 dict(name='MODE switch',x=112,y=42,w=20,h=14,kind='access',note='power-off operation; confirm actuator labels on sample'),
 dict(name='receivers / host drivers',x=5,y=82,w=68,h=50,kind='logic',note='host-facing zone; X2 datum not yet known'),
 dict(name='isolation / supervisors',x=80,y=82,w=52,h=50,kind='logic',note='keep separate 3V3 domains'),
 dict(name='X2 mechanical reserve',x=5,y=141,w=127,h=15,kind='unresolved',note='NO connector or board-edge geometry assumed')]
plan={'schema':1,'fabrication_ready':False,'units':'mm','study_area':[137,161],'zones':zones,
 'warning':'Allocation study only: no PCB edge, routes, connector mating or enclosure fit approval.',
 'hx8k_source_envelope':[65,67],
 'hx8k_headers':{'EXT1':{'center_from_source_top_left':[15.175,12.405]},'EXT2':{'center_from_source_top_left':[46.925,12.405]},'EXT3':{'center_from_source_top_left':[15.175,3.515]}},
 'hx8k_header_contact_pitch':1.27,'hx8k_smd_tail_row_spacing':4.064,
 'header_warning':'4.064 is copper-tail spacing, not mating-contact row spacing; do not use it for a female connector footprint.'}
(OUT/'placement-study.json').write_text(json.dumps(plan,indent=2)+'\n')
s=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1120" viewBox="0 0 180 224">','<rect width="180" height="224" fill="#f6f7fa"/>','<g font-family="DejaVu Sans">','<text x="12" y="12" font-size="6" fill="#14253d">Pico1715 placement study</text>','<text x="12" y="20" font-size="3.6">Allocation only — not a PCB outline or fabrication file</text>']
colors={'module':'#cce5fa','access':'#ccedde','logic':'#e2dcfa','unresolved':'#f7d4c6'}
for z in zones:
 x=z['x']+12;y=z['y']+26
 label={'PIM724 + access':'PIM724','microSD + eject':'microSD','MODE switch':'MODE'}.get(z['name'],z['name'])
 s += [f'<rect x="{x}" y="{y}" width="{z["w"]}" height="{z["h"]}" rx="1" fill="{colors[z["kind"]]}" stroke="#596675" stroke-width="0.3"/>',f'<text x="{x+2}" y="{y+6}" font-size="3">{label}</text>',f'<text x="{x+2}" y="{y+11}" font-size="3">{z["w"]} × {z["h"]} mm</text>']
s += ['<text x="12" y="194" font-size="3.4">Keep USB, buttons, mode selector and card travel accessible.</text>','<text x="12" y="202" font-size="3.4">HX8K headers: 1.27 mm pitch; mating connector not yet frozen.</text>','<text x="12" y="210" font-size="3.4">X2 orientation, stacking height and enclosure clearance remain open.</text>','</g></svg>']
(OUT/'preview/placement-study.svg').write_text('\n'.join(s)+'\n')
print('Generated original switch/Pico footprints and non-fabrication allocation study')
