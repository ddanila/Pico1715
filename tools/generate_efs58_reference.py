#!/usr/bin/env python3
"""Original MIT reference geometry, transcribed from TGL 29331/03, Fig. 34.

Not assigned to the carrier: body/courtyard and host installation remain open.
The top-side numbering is an interpretation of the standard's termination view.
"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'hardware/carrier/efs58'
NAME = 'EFS58_202-58_Form7_Reference'

def generate():
    OUT.mkdir(exist_ok=True)
    pads = [{'number': f'{row}{n}', 'x': (n-1)*2.5, 'y': y}
            for row, y in [('A', 0), ('B', 5)] for n in range(1, 30)]
    mounts = [[-7.5, -5], [77.5, -5]]
    facts = dict(schema=1, units='mm', connector='202-58', mounting_form=7,
                 status='reference geometry; not assigned to carrier', fabrication_ready=False,
                 view='PCB component side; connector toward negative Y; A1 at origin',
                 numbering_status='derived from termination view and row A facing PCB; sample continuity pending',
                 pitch=2.5, tail_row_spacing=5, contact_span=70,
                 mounting_centres=85, mounting_hole_diameter=2.7,
                 board_edge_y=-6.5, edge_datum='Fig.34 e7: edge to first tail row, not edge to mounting line',
                 pads=pads, mounting_holes=mounts,
                 chosen_finished_contact_hole=1.0, chosen_copper_pad_diameter=1.8,
                 missing=['verified body/courtyard envelope', 'host installation/clearance transform', 'physical fit and continuity'],
                 source='TGL 29331/03 February 1988 pp3,11,17,18,24-26')
    (OUT/'geometry.json').write_text(json.dumps(facts, indent=2)+'\n')
    s=[f'(footprint "{NAME}" (version 20250114) (generator "pico1715") (layer "F.Cu") (attr through_hole)',
       '(descr "REFERENCE ONLY: 202-58 Form7. See investigation.md; no qualified courtyard or host placement.")',
       '(fp_text reference "REF**" (at 35 9) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
       '(fp_text user "REFERENCE ONLY / 202-58 Form7" (at 35 12) (layer "Dwgs.User") (effects (font (size 1 1) (thickness 0.15))))',
       '(fp_line (start -11 -6.5) (end 81 -6.5) (stroke (width 0.1) (type dash)) (layer "Dwgs.User"))',
       '(fp_text user "PCB edge datum" (at 35 -8.5) (layer "Dwgs.User") (effects (font (size 1 1) (thickness 0.15))))']
    for p in pads:
        shape='rect' if p['number']=='A1' else 'circle'
        s.append(f'(pad "{p["number"]}" thru_hole {shape} (at {p["x"]} {p["y"]}) (size 1.8 1.8) (drill 1) (layers "*.Cu" "*.Mask"))')
    for x,y in mounts:
        s.append(f'(pad "" np_thru_hole circle (at {x} {y}) (size 2.7 2.7) (drill 2.7) (layers "*.Cu" "*.Mask"))')
    s.append(')')
    (OUT/(NAME+'.kicad_mod')).write_text('\n'.join(s)+'\n')
    # Physical millimetre units, with a ruler to detect print scaling.
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="120mm" height="65mm" viewBox="-20 -30 120 65">',
         '<rect x="-20" y="-30" width="120" height="65" fill="white"/>',
         '<g font-family="sans-serif" font-size="2.3" fill="black">',
         '<text x="-15" y="-24">202-58 / Form 7 — component-side reference</text>',
         '<text x="-15" y="-19">Print at 100%; verify ruler. Not a fabrication release.</text>',
         '<text x="0" y="-11">Mating direction ↑ / body envelope not shown</text>',
         '<path d="M -12,-6.5 H 82" stroke="black" stroke-width="0.2" stroke-dasharray="1,1"/>',
         '<text x="18" y="-7.5">PCB edge datum (e7 = 6.5)</text>']
    for p in pads:
        svg.append(f'<circle cx="{p["x"]}" cy="{p["y"]}" r="0.5" fill="none" stroke="black" stroke-width="0.15"/>')
    for x,y in mounts:
        svg.append(f'<circle cx="{x}" cy="{y}" r="1.35" fill="none" stroke="black" stroke-width="0.15"/>')
    for row,y in [('A',0),('B',5)]:
        for n in [1,2,28,29]:
            svg.append(f'<text x="{(n-1)*2.5}" y="{y+2.3}" text-anchor="middle" font-size="1.1">{row}{n}</text>')
    svg += ['<text x="-15" y="14">2.5 pitch / 5 tail rows / 85 mounting centres / Ø2.7 mounts</text>',
            '<text x="-15" y="19">Ø1.0 contact holes are our choice. Numbering needs sample check.</text>',
            '<path d="M 0,26 H 50 M 0,24 V 28 M 50,24 V 28" stroke="black" stroke-width="0.2"/>',
            '<text x="25" y="31" text-anchor="middle">50 mm calibration</text></g></svg>']
    (OUT/'drilling-template.svg').write_text('\n'.join(svg)+'\n')

if __name__ == '__main__':
    generate()
