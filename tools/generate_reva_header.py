#!/usr/bin/env python3
"""Original 61206021621 footprint from manufacturer drawing 001.002."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def generate():
 d=ROOT/'hardware/carrier-reva/Pico1715_RevA.pretty';d.mkdir(exist_ok=True)
 s='''(footprint "IDC_Wuerth_61206021621" (version 20241229) (generator "pico1715") (layer "F.Cu") (attr through_hole)
 (descr "61206021621 drawing 001.002: 2.54 grid, 1.10 finished holes, 83.86 x 9.10 body")
 (fp_text reference "REF**" (at 1.27 -7) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
 (fp_text value "61206021621" (at 1.27 81) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
 (fp_rect (start -3.28 -5.1) (end 5.82 78.76) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
 (fp_rect (start -3.78 -5.6) (end 6.32 79.26) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
 (fp_line (start -3.4 -5.22) (end 5.94 -5.22) (stroke (width 0.12) (type default)) (layer "F.SilkS"))
 (fp_line (start 5.94 -5.22) (end 5.94 78.88) (stroke (width 0.12) (type default)) (layer "F.SilkS"))
 (fp_line (start 5.94 78.88) (end -3.4 78.88) (stroke (width 0.12) (type default)) (layer "F.SilkS"))
 (fp_line (start -3.4 -5.22) (end -3.4 34.58) (stroke (width 0.12) (type default)) (layer "F.SilkS"))
 (fp_line (start -3.4 39.08) (end -3.4 78.88) (stroke (width 0.12) (type default)) (layer "F.SilkS"))
 (fp_text user "1" (at -2 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
 (fp_text user "KEY" (at -2 36.83 90) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
'''
 for n in range(1,61):s+=f'(pad "{n}" thru_hole {"rect" if n==1 else "circle"} (at {0 if n%2 else 2.54} {round((n-1)//2*2.54,2)}) (size 1.7 1.7) (drill 1.1) (layers "*.Cu" "*.Mask"))\n'
 (d/'IDC_Wuerth_61206021621.kicad_mod').write_text(s+')\n')
if __name__=='__main__':generate()
