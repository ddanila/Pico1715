#!/usr/bin/env python3
"""Original assembly drawing; dimensions read from the model parameter file."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'hardware/efs58-coupon'
p=json.loads((OUT/'parameters.json').read_text())
s=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="740" viewBox="0 0 1100 740">',
   '<rect width="1100" height="740" fill="#f8fafc"/>',
   '<style>text{font-family:sans-serif;fill:#172b42} .title{font-size:28px;font-weight:bold} .sub{font-size:19px;font-weight:bold} .small{font-size:16px} .dim{font-size:14px;fill:#42566a}</style>']
def text(x,y,t,cls='small'):
    s.append(f'<text x="{x}" y="{y}" class="{cls}">{t}</text>')
def rect(x,y,w,h,fill,stroke='#42566a'):
    s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>')
def circle(x,y,r,fill):
    s.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="#42566a"/>')
def line(x1,y1,x2,y2):
    s.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="#42566a"/>')
text(35,45,'Pico1715 / four-contact test fixture','title')
text(35,77,'Unpowered experiment • dimensions in mm • not a full EFS58 mating housing')
text(45,125,'Mating face, looking into the sockets','sub')
cx,cy,scale=240,245,18
w,h=p['housing_size'];rect(cx-w/2*scale,cy-h/2*scale,w*scale,h*scale,'#dceaf5')
rect(cx-w/2*scale,cy-h/2*scale,36,36,'#f8fafc','#f8fafc')
for x,y in p['mounts']: circle(cx+x*scale,cy+y*scale,p['screw_clearance']/2*scale,'#f8fafc')
for i,(x,y) in enumerate(p['centres'],1):
    xx,yy=cx+x*scale,cy+y*scale
    circle(xx,yy,p['entry_diameter']/2*scale,'#f8fafc')
    lx=xx-62 if x<0 else xx+42;ly=yy-25 if y<0 else yy+30
    line(xx,yy,lx+10,ly);text(lx,ly-5,'C'+str(i))
text(55,370,'20 × 10 body; M2 holes on 14 mm centres','dim')
text(55,394,'Contacts: 2.5 mm pitch in BOTH directions','dim')
text(55,418,'Clipped corner aligns with KEY on PCB','dim')
text(590,125,'Section through the two left sockets','sub')
# Stack exaggerated laterally for legibility; exact Z datums labelled.
xx,yy,sz=630,165,30
rect(xx,yy,250,p['front_thickness']*sz,'#b9d7ee')
rect(xx,yy+sz,250,(p['body_back_z']-1)*sz,'#dceaf5')
c=p['contact']
for x in [690,810]:
    # Pocket envelope (nominal middle clearance) then socket outer envelope.
    rect(x-20,yy+sz,40,(c['body_length']+0.2)*sz,'#f8fafc')
    rect(x-9,yy,18,sz,'#f8fafc')
    rect(x-16,yy+sz,32,c['flange_height']*sz,'#e8c06a')
    rect(x-12,yy+sz*(1+c['flange_height']),24,(c['body_length']-c['flange_height'])*sz,'#e8c06a')
    rect(x-4,yy+sz*(1+c['body_length']),8,c['tail_length']*sz,'#e8c06a')
rect(xx,yy+p['pcb_front_z']*sz,250,p['pcb_thickness']*sz,'#77b9a1')
# Show tails through PCB, with holes rather than implying a solid intersection.
for x in [690,810]:
    rect(x-7,yy+p['pcb_front_z']*sz,14,p['pcb_thickness']*sz,'#f8fafc')
    rect(x-4,yy+p['pcb_front_z']*sz,8,(1+c['body_length']+c['tail_length']-p['pcb_front_z'])*sz,'#e8c06a')
for z,label in [(0,'Z 0 / face'),(1,'1.0 / socket mouth'),(5.5,'5.5 / body back'),(5.9,'5.9 / PCB front'),(7.5,'7.5 / PCB back'),(8.37,'8.37 / tail end')]:
    ly=yy+z*sz
    # Separate closely spaced leaders at body/PCB interface.
    ty=ly-9 if z==5.5 else ly+8 if z==5.9 else ly+5
    line(885,ly,920,ty-4);text(925,ty,label,'dim')
text(595,456,'Gold = socket envelope; springs omitted','dim')
text(595,478,'0.4 mm body/PCB gap, except at screw feet','dim')
text(45,500,'Assembly','sub')
for y,t in [(530,'1. Qualify a loose socket on a sacrificial EFS blade first.'),(556,'2. Insert four sockets into one body; close with the front plate.'),(582,'3. Fit PCB, align KEY, install two M2 × 12 screws and nuts.'),(608,'4. Solder from the PCB back; check four independent paths.')]:text(45,y,t)
text(45,654,'Print one front and the three clearance variants: c15 / c25 / c35.','dim')
text(45,680,'Broad ears obstruct adjacent host pins. Use loose test pins; never force this fixture onto the motherboard.','dim')
text(45,710,'Original MIT design • see README for sources, material limits and bench acceptance','dim')
s.append('</svg>')
(OUT/'drawing.svg').write_text('\n'.join(s)+'\n')
