#!/usr/bin/env python3
"""Generate the independent four-channel passive coupon; system pcbnew required."""
import json
import re
from pathlib import Path
import uuid
import pcbnew as k

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'hardware/efs58-coupon'
p = json.loads((OUT / 'parameters.json').read_text())
b = k.BOARD()
b.GetDesignSettings().SetBoardThickness(k.FromMM(p['pcb_thickness']))
uid = lambda s: str(uuid.uuid5(uuid.NAMESPACE_URL, 'pico1715/efs-coupon/'+s))
vec = lambda x,y: k.VECTOR2I(k.FromMM(x), k.FromMM(y))
def stable(o, name): o.SetUuid(k.KIID(uid(name)))
def text(s,x,y,size=0.9):
    t=k.PCB_TEXT(b); t.SetText(s); t.SetPosition(vec(x,y)); t.SetTextSize(vec(size,size))
    t.SetTextThickness(k.FromMM(0.13)); t.SetLayer(k.F_SilkS); stable(t,s); b.Add(t)

nets={}
for i in range(1,5):
    net=k.NETINFO_ITEM(b, '/C'+str(i)); b.Add(net); nets[i]=net

# Local footprints keep fabrication independent of a system library version.
lib=OUT/'Coupon.pretty'; lib.mkdir(exist_ok=True)
types={'Socket1001':(p['contact_pad'],p['contact_drill']),
       'WirePad':(2.5,1.2), 'M2':(p['screw_clearance'],p['screw_clearance'])}
for name,(diameter,drill) in types.items():
    fp=k.FOOTPRINT(b); fp.SetValue(name); fp.SetReference('REF**')
    fp.SetAttributes(k.FP_THROUGH_HOLE)
    pad=k.PAD(fp); pad.SetShape(k.PAD_SHAPE_CIRCLE)
    pad.SetAttribute(k.PAD_ATTRIB_NPTH if name=='M2' else k.PAD_ATTRIB_PTH)
    pad.SetNumber('' if name=='M2' else '1'); pad.SetSize(vec(diameter,diameter))
    pad.SetDrillSize(vec(drill,drill)); pad.SetLayerSet(k.PAD.UnplatedHoleMask() if name=="M2" else k.PAD.PTHMask())
    stable(fp,'library/'+name); stable(pad,'library/'+name+'/pad'); fp.Add(pad)
    for j,field in enumerate(fp.GetFields()): stable(field,'library/'+name+'/field/'+str(j))
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    fp.SetFPID(k.LIB_ID("Coupon",name)); k.PCB_IO_KICAD_SEXPR().FootprintSave(str(lib),fp)
    # KiCad creates fresh library field UUIDs while saving a footprint.
    path=lib/(name+'.kicad_mod'); count=iter(range(100))
    path.write_text(re.sub(r'\(uuid "[^"]+"\)',
        lambda m:'(uuid "'+uid('library/'+name+'/saved/'+str(next(count)))+'")',path.read_text()))

parts=[]
def place(ref,name,x,y,net=None):
    fp=k.FootprintLoad(str(lib),name); fp.SetReference(ref); fp.SetValue(name)
    fp.SetFPID(k.LIB_ID('Coupon',name)); fp.SetPosition(vec(x,y)); stable(fp,ref)
    fp.SetPath(k.KIID_PATH('/'+uid('root')+'/'+uid(ref)))
    for j,pad in enumerate(fp.Pads()):
        stable(pad,ref+'/pad/'+str(j))
        if net: pad.SetNet(nets[net])
    for j,field in enumerate(fp.GetFields()): stable(field,ref+'/field/'+str(j))
    b.Add(fp); parts.append((ref,name,net))

ox,oy=p['pcb_origin']
for i,(x,y) in enumerate(p['centres'],1): place('J'+str(i),'Socket1001',ox+x,oy+y,i)
for i,(x,y) in enumerate(p['outputs'],1):
    place('TP'+str(i),'WirePad',x,y,i); text('C'+str(i),x,y+2.7)
for i,(x,y) in enumerate(p['mounts'],1): place('H'+str(i),'M2',ox+x,oy+y)

paths=[[(12,8.75),(10,6),(3,6),(3,24),(5,24)],
       [(14.5,8.75),(17,6),(25,6),(25,24),(23,24)],
       [(12,11.25),(11,15),(11,24)],
       [(14.5,11.25),(17,15),(17,24)]]
for i,path in enumerate(paths,1):
    for j,(start,end) in enumerate(zip(path,path[1:])):
        tr=k.PCB_TRACK(b); tr.SetStart(vec(*start)); tr.SetEnd(vec(*end))
        tr.SetWidth(k.FromMM(0.35)); tr.SetLayer(k.F_Cu); tr.SetNet(nets[i]); stable(tr,f'C{i}/{j}'); b.Add(tr)
w,h=p['pcb_size']
corners=[(0,0),(w,0),(w,h),(0,h),(0,0)]
for i,(start,end) in enumerate(zip(corners,corners[1:])):
    s=k.PCB_SHAPE(); s.SetShape(k.SHAPE_T_SEGMENT); s.SetStart(vec(*start)); s.SetEnd(vec(*end))
    s.SetLayer(k.Edge_Cuts); s.SetWidth(k.FromMM(0.05)); stable(s,'edge'+str(i)); b.Add(s)
text('EFS CONTACT TEST',14,2.5,1.1)
text('UNPOWERED / REV A',14,18,1)
text('1  2',13.25,7.1,0.8); text('3  4',13.25,13,0.8)
text('KEY',3,3.8,0.8)
k.SaveBoard(str(OUT/'coupon.kicad_pcb'),b)
(OUT/'fp-lib-table').write_text('(fp_lib_table (lib (name "Coupon") (type "KiCad") (uri "${KIPRJMOD}/Coupon.pretty") (options "") (descr "Original coupon footprints")))\n')
(OUT/'coupon.kicad_pro').write_text('{}\n')

# Pin-explicit schematic: four completely separate passive connections.
font='(effects (font (size 1.27 1.27)))'
libs=[]; instances=[]; wires=[]; notes=[]
for idx,(ref,name,net) in enumerate(parts):
    x=60 if ref.startswith('J') else 120 if ref.startswith('TP') else 170
    y=50+15*(int(ref.lstrip('JTPH'))-1)
    x=round(round(x/1.27)*1.27,4); y=round(round(y/1.27)*1.27,4)
    pin='' if net is None else f'(symbol "{ref}_1_1" (pin passive line (at 5.08 0 180) (length 5.08) (name "contact" {font}) (number "1" {font})))'
    libs.append(f'(symbol "Coupon:{ref}" (pin_names (offset 0.5)) (in_bom yes) (on_board yes) (property "Reference" "{ref}" (at 0 5 0) {font}) (property "Value" "{name}" (at 0 2.5 0) {font}) (symbol "{ref}_0_1" (circle (center 0 0) (radius 1) (stroke (width 0.2) (type default)) (fill (type none)))) {pin})')
    props=''.join(f'(property "{key}" "{value}" (at {x} {y+dy} 0) (effects (font (size 1.27 1.27)){hide}))' for key,value,dy,hide in [('Reference',ref,-5,''),('Value',name,-2.5,''),('Footprint','Coupon:'+name,0,' hide')])
    instances.append(f'(symbol (lib_id "Coupon:{ref}") (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (uuid {uid(ref)}) {props} (instances (project "coupon" (path "/{uid("root")}" (reference "{ref}") (unit 1)))))')
    if net:
        wires.append(f'(wire (pts (xy {x+5.08} {y}) (xy {x+15.24} {y})) (stroke (width 0) (type default)) (uuid {uid(ref+"wire")}))')
        wires.append(f'(label "C{net}" (at {x+15.24} {y} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {uid(ref+"label")}))')
for y,s in [(20,'EFS contact experiment / four isolated paths'),(125,'J1-J4: loose Mill-Max 1001 sockets in printed holder.'),(135,'TP1-TP4: wire pads. No power or ground connection.'),(145,'C1-C4 are fixture labels, NOT Robotron bus contact numbers.'),(155,'Use loose sacrificial pins. Not a motherboard mating housing.')]:
    notes.append(f'(text "{s}" (at 35 {y} 0) (effects (font (size 1.5 1.5)) (justify left)) (uuid {uid(s)}))')
(OUT/'coupon.kicad_sch').write_text(f'(kicad_sch (version 20250114) (generator "pico1715") (uuid {uid("root")}) (paper "A4") (lib_symbols {"".join(libs)}) {"".join(instances+wires+notes)})\n')
(OUT/'Coupon.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "pico1715") '+''.join(libs).replace('"Coupon:', '"')+')\n')
(OUT/'sym-lib-table').write_text('(sym_lib_table (lib (name "Coupon") (type "KiCad") (uri "${KIPRJMOD}/Coupon.kicad_sym") (options "") (descr "Original coupon symbols")))\n')
print('Generated four routed isolated paths, schematic and local footprints')
