#!/usr/bin/env python3
"""Original assembly view, explicit viewing direction; not a physical fit claim."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def draw():
 s=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="470" viewBox="0 0 1000 470"><rect width="1000" height="470" fill="white"/><g font-family="sans-serif" fill="#182b40">']
 def text(x,y,t,size=16):s.append(f'<text x="{x}" y="{y}" font-size="{size}">{t}</text>')
 text(25,30,'Pico1715 Rev A — J6 host harness',23)
 for y,mirror,title in [(80,False,'Carrier top view: looking down into header; north is up'),(245,True,'Cable socket mating face: looking into sockets; key kept down')]:
  text(25,y-15,title)
  s.append(f'<rect x="25" y="{y}" width="940" height="85" rx="4" fill="#edf1f6" stroke="#182b40"/>')
  for col in range(30):
   x=55+(29-col if mirror else col)*30
   for row in range(2):
    n=2*col+(2 if row==0 else 1);cy=y+25+row*35
    s.append(f'<rect x="{x-11}" y="{cy-12}" width="22" height="24" fill="{"#f5cf78" if n==1 else "white"}" stroke="#182b40"/>')
    text(x-8,cy+5,str(n),13)
  s.append(f'<rect x="460" y="{y+78}" width="70" height="14" fill="white" stroke="#182b40"/>')
  text(465,y+113,'KEY',14)
 text(25,405,'Straight-through 60 conductors, ≤100 mm. Stripe marks pin 1. Verify all conductors by continuity.')
 text(25,435,'A1→1, B1→2, … A29→57, B29→58. Pins 59/60 NC. EFS58 physical fit remains unqualified.')
 s.append('</g></svg>');(ROOT/'hardware/carrier-reva/harness.svg').write_text('\n'.join(s)+'\n')
if __name__=='__main__':draw()
