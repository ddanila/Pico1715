#!/usr/bin/env python3
"""Provisional passive 58-contact breakout. Requires system pcbnew."""
import hashlib,json,shutil,uuid
from pathlib import Path
import pcbnew as k
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'hardware/x2-adapter'; OUT.mkdir(exist_ok=True)
lib=OUT/'Adapter.pretty'; lib.mkdir(exist_ok=True)
name='EFS58_202-58_Form7_Reference'
shutil.copyfile(ROOT/'hardware/carrier/efs58'/(name+'.kicad_mod'),lib/(name+'.kicad_mod'))
header='PinHeader_2x30_P2.54mm_Vertical'
shutil.copyfile(Path('/usr/share/kicad/footprints/Connector_PinHeader_2.54mm.pretty')/(header+'.kicad_mod'),lib/(header+'.kicad_mod'))
uid=lambda s:str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/x2-adapter/'+s))
vec=lambda x,y:k.VECTOR2I(k.FromMM(x),k.FromMM(y))
def stable(o,s):o.SetUuid(k.KIID(uid(s)))
b=k.BOARD(); b.GetDesignSettings().SetBoardThickness(k.FromMM(1.6))
nets={}
for row in 'AB':
 for i in range(1,30):
  contact=f'{row}{i}'; n=k.NETINFO_ITEM(b,'/X2_'+contact);b.Add(n);nets[contact]=n
unused={}
for number in (59,60):
 n=k.NETINFO_ITEM(b,f"unconnected-(J1-Pad{number})");b.Add(n);unused[str(number)]=n
parts={}
for ref,fpname,at,angle in [('X2',name,(35,31.5),0),('J1',header,(34,52),90)]:
 fp=k.FootprintLoad(str(lib),fpname);fp.SetFPID(k.LIB_ID('Adapter',fpname));fp.SetReference(ref);fp.SetValue(fpname)
 fp.SetPosition(vec(*at));fp.SetOrientationDegrees(angle);fp.SetPath(k.KIID_PATH('/'+uid('root')+'/'+uid(ref)));stable(fp,ref)
 for i,f in enumerate(fp.GetFields()):stable(f,ref+'/field/'+str(i))
 for i,g in enumerate(fp.GraphicalItems()):stable(g,ref+'/graphic/'+str(i))
 for i,p in enumerate(fp.Pads()):
  stable(p,ref+'/pad/'+str(i)); num=p.GetNumber()
  if not num:continue
  contact=num if ref=='X2' else ('A' if int(num)%2 else 'B')+str((int(num)+1)//2)
  if contact in nets:p.SetNet(nets[contact])
  elif ref=='J1':p.SetNet(unused[num])
 b.Add(fp);parts[ref]=fp
mapping=[]
for i in range(29):
 x=35+i*2.5;gx=34+i*2.54
 for row,points,layer in [('A',[(x,31.5),(x+1.25,32.75),(x+1.25,44),(gx+1.27,46),(gx+1.27,50.73),(gx,52)],k.B_Cu),('B',[(x,36.5),(x,42),(gx,45),(gx,49.46)],k.F_Cu)]:
  contact=f'{row}{i+1}';pin=2*i+(1 if row=='A' else 2)
  for j,(start,end) in enumerate(zip(points,points[1:])):
   t=k.PCB_TRACK(b);t.SetStart(vec(*start));t.SetEnd(vec(*end));t.SetWidth(k.FromMM(.25));t.SetLayer(layer);t.SetNet(nets[contact]);stable(t,contact+'/'+str(j));b.Add(t)
  mapping.append({'contact':contact,'header_pin':pin,'net':'X2_'+contact,'source_xy_mm':[x,31.5 if row=='A' else 36.5],'header_xy_mm':[gx,52 if row=='A' else 49.46]})
for i,(s,e) in enumerate(zip([(20,25),(120,25),(120,58),(20,58)],[(120,25),(120,58),(20,58),(20,25)])):
 t=k.PCB_SHAPE();t.SetShape(k.SHAPE_T_SEGMENT);t.SetStart(vec(*s));t.SetEnd(vec(*e));t.SetWidth(k.FromMM(.05));t.SetLayer(k.Edge_Cuts);stable(t,'edge'+str(i));b.Add(t)
for s,x,y in [('PROVISIONAL / VERIFY A-B',70,56),('A1',30,31.5),('B1',30,36.5),('1',31,52),('2',31,49.46)]:
 t=k.PCB_TEXT(b);t.SetText(s);t.SetPosition(vec(x,y));t.SetTextSize(vec(.9,.9));t.SetTextThickness(k.FromMM(.13));t.SetLayer(k.F_SilkS);stable(t,s);b.Add(t)
k.SaveBoard(str(OUT/'adapter.kicad_pcb'),b)
(OUT/'adapter.kicad_pro').write_text('{}\n')
(OUT/'fp-lib-table').write_text('(fp_lib_table (lib (name "Adapter") (type "KiCad") (uri "${KIPRJMOD}/Adapter.pretty") (options "") (descr "Provisional breakout footprints")))\n')
# Pin-explicit passive schematic with one separate net per contact.
font='(effects (font (size 1.27 1.27)))';libs=[];instances=[];connections=[]
for ref,fpname,x in [('X2',name,60.96),('J1',header,177.8)]:
 pins=[]
 numbers=[f'{r}{i}' for i in range(1,30) for r in 'AB'] if ref=='X2' else list(map(str,range(1,61)))
 for index,num in enumerate(numbers):
  py=round(76.2-index*2.54,4);y=round(101.6-py,4)
  pins.append(f'(pin passive line (at 5.08 {py} 180) (length 5.08) (name "{num}" {font}) (number "{num}" {font}))')
  contact=num if ref=='X2' else ('A' if int(num)%2 else 'B')+str((int(num)+1)//2)
  if contact in nets:
   connections.append(f'(wire (pts (xy {x+5.08:.4f} {y}) (xy {x+15.24:.4f} {y})) (stroke (width 0) (type default)) (uuid {uid(ref+num+"wire")}))')
   connections.append(f'(label "X2_{contact}" (at {x+15.24:.4f} {y} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {uid(ref+num+"label")}))')
  else:connections.append(f'(no_connect (at {x+5.08:.4f} {y}) (uuid {uid(ref+num+"nc")}))')
 libs.append(f'(symbol "Adapter:{ref}" (pin_names (offset 0.5)) (in_bom yes) (on_board yes) (property "Reference" "{ref}" (at 0 80 0) {font}) (property "Value" "{fpname}" (at 0 83 0) {font}) (symbol "{ref}_0_1" (rectangle (start -5 78) (end 0 -76) (stroke (width 0.2) (type default)) (fill (type none)))) (symbol "{ref}_1_1" {"".join(pins)}))')
 props=''.join(f'(property "{key}" "{value}" (at {x} {y} 0) (effects (font (size 1.27 1.27)){hide}))' for key,value,y,hide in [('Reference',ref,20,''),('Value',fpname,15,''),('Footprint','Adapter:'+fpname,101.6,' hide')])
 instances.append(f'(symbol (lib_id "Adapter:{ref}") (at {x} 101.6 0) (unit 1) (in_bom yes) (on_board yes) (uuid {uid(ref)}) {props} (instances (project "adapter" (path "/{uid("root")}" (reference "{ref}") (unit 1)))))')
(OUT/'adapter.kicad_sch').write_text(f'(kicad_sch (version 20250114) (generator "pico1715") (uuid {uid("root")}) (paper "A4") (lib_symbols {"".join(libs)}) {"".join(instances+connections)})\n')
(OUT/'Adapter.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "pico1715") '+''.join(libs).replace('"Adapter:','"')+')\n')
(OUT/'sym-lib-table').write_text('(sym_lib_table (lib (name "Adapter") (type "KiCad") (uri "${KIPRJMOD}/Adapter.kicad_sym") (options "") (descr "Original passive adapter symbols")))\n')
manifest={'schema':1,'fabrication_ready':False,'status':'provisional; physical orientation, mating and installation pending','size_mm':[100,33],'origin_mm':[20,25],'unused_header_pins':[59,60],'mapping':mapping,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'hardware/carrier/efs58/geometry.json',Path(__file__)]}}
(OUT/'mapping.json').write_text(json.dumps(manifest,indent=2)+'\n')
# 1:1 drill/orientation drawing; explicit units and scale bar.
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="120mm" height="60mm" viewBox="10 15 120 60"><rect x="20" y="25" width="100" height="33" fill="white" stroke="black" stroke-width="0.2"/>']
for ref,fp in parts.items():
 for p in fp.Pads():
  x,y=k.ToMM(p.GetPosition().x),k.ToMM(p.GetPosition().y);r=k.ToMM(p.GetDrillSize().x)/2
  svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="black" stroke-width="0.1"/>')
for s,x,y in [('X2 A1',27,30),('X2 B1',27,39),('J1 pin 1',27,55),('Provisional component side / print 100%',25,20),('10 mm',80,69)]:svg.append(f'<text x="{x}" y="{y}" font-size="2">{s}</text>')
svg.append('<path d="M80 65h10m-10 -1v2m10 -2v2" fill="none" stroke="black" stroke-width="0.2"/></svg>')
(OUT/'drilling-template.svg').write_text(''.join(svg)+'\n')
print('Generated 58 isolated routed connections; provisional geometry')

source=json.loads((ROOT/'hardware/carrier/connections.json').read_text())
pins=next(p['pins'] for p in source['parts'] if p['ref']=='X2');bypin={p[0]:p for p in pins}
lines=['# Provisional X2 harness map','','Component-side numbering is derived from the reference drawing; confirm A/B and both cable ends by continuity before host use. Header pins 59/60 are unconnected. Every breakout trace is isolated, including contacts that join GND on the host. This is a contact map, not a qualified high-speed ribbon-cable design.','','| X2 | J1 pin | Host signal | Carrier net |','|---|---:|---|---|']
for r in sorted(mapping,key=lambda r:r['header_pin']):
 p=bypin[r['contact']];lines.append(f"| {r['contact']} | {r['header_pin']} | {p[1]} | {p[3] or 'NC on carrier'} |")
(OUT/'harness.md').write_text('\n'.join(lines)+'\n')
