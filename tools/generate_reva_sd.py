#!/usr/bin/env python3
"""Original Würth 693071010811 land pattern, drawing 001.002 page 1."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'hardware/carrier-reva'
def generate():
 # Datum: upper-left dashed body corner of the recommended PCB layout.
 # Dimensions are transcribed from the manufacturer drawing, not another library.
 pads=[]
 for n in range(1,9):
  y=10.7+(.2 if n in (4,6) else -.4 if n==2 else 0)
  pads.append(dict(pin=str(n),at=[round(1.24+(8-n)*1.1,2),round(y,2)],size=[.8,1.5]))
 pads += [dict(pin='9',at=[.45,13.55],size=[1.4,1.9]),dict(pin='9',at=[13.6,14.55],size=[1.4,1.9]),dict(pin='10',at=[2.05,.4],size=[1.8,1.4]),dict(pin='10',at=[7.75,.4],size=[1.8,1.4])]
 d=OUT/'Pico1715_RevA.pretty';d.mkdir(exist_ok=True)
 text='''(footprint "microSD_Wuerth_693071010811" (version 20241229) (generator "pico1715") (layer "F.Cu")
 (descr "Wurth 693071010811; original land pattern from manufacturer drawing 001.002 page 1") (attr smd)
 (fp_text reference "REF**" (at 7 -2) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
 (fp_text value "693071010811" (at 7 17) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
 (fp_rect (start 0 0) (end 14 15.2) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
 (fp_rect (start -0.75 -0.8) (end 14.8 16) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
 (fp_line (start 0 1.5) (end 0 9.2) (stroke (width 0.12) (type default)) (layer "F.SilkS"))
 (fp_line (start 14 1.5) (end 14 12.8) (stroke (width 0.12) (type default)) (layer "F.SilkS"))
 (fp_text user "CARD" (at 10.5 -1.2) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.1))))
'''
 for p in pads:text+=f'(pad "{p["pin"]}" smd rect (at {p["at"][0]} {p["at"][1]}) (size {p["size"][0]} {p["size"][1]}) (layers "F.Cu" "F.Paste" "F.Mask"))\n'
 (d/'microSD_Wuerth_693071010811.kicad_mod').write_text(text+')\n')
 (OUT/'sd-land-pattern.json').write_text(json.dumps(dict(schema=1,part='693071010811',drawing_revision='001.002',drawing_date='2019-01-24',drawing_sha256='e2859032e66b457131233f9345cd0066d3d0aa012c4782b16cf8f15464801d98',datum='Upper-left dashed body corner, recommended PCB layout page 1; +X right, +Y down',pads=pads,board_at=[161,28.6],board_angle=0,body=[0,0,14,15.2],top_copper_exclusion=[0,1.5,14,9.3],exclusion_basis='Conservative project rule beneath body; not a manufacturer-specified all-layer prohibition',card_detection='9–10 closed without card, open with card; unused, both NC',shield='No separate SH terminal documented; none invented',physical_fit_tested=False),indent=2)+'\n')
if __name__=='__main__':generate()
