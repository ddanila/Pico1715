#!/usr/bin/env python3
"""Generate the separate Rev A carrier contract. Never edits the two-layer baseline."""
import copy,hashlib,json,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'hardware/carrier-reva'
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/carrier-reva/'+s))
def contract():
 base=ROOT/'hardware/carrier/connections.json'
 parts=copy.deepcopy(json.loads(base.read_text())['parts'])
 host=next(p for p in parts if p['ref']=='X2');host['ref']='J6';host['value']='61206021621_HOST_HARNESS'
 mapping=[];pins=[]
 for contact,name,typ,net in host['pins']:
  pin=2*(int(contact[1:])-1)+(1 if contact[0]=='A' else 2)
  pins.append([pin,name,typ,net]);mapping.append(dict(contact=contact,pin=pin,net=net))
 host['pins']=sorted(pins)+[[59,'NC','passive',None],[60,'NC','passive',None]]
 host['footprint']='Connector_IDC:IDC-Header_2x30_P2.54mm_Vertical'
 host['datasheet']='https://www.we-online.com/components/products/datasheet/61206021621.pdf'
 i=len(parts)
 parts.append(dict(ref='J7',value='B3B-XH-A_RESERVE_POWER',pins=[[1,'GND','passive','GND'],[2,'RAW_5V','passive','V5_MODULE'],[3,'BACKED_VSYS','passive','P_VSYS']],x=round(round((80+i%10*110)/1.27)*1.27,4),y=round(round((100+i//10*90)/1.27)*1.27,4),footprint='Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical',datasheet='https://www.jst-mfg.com/product/index.php?series=277'))
 return dict(schema=1,revision='carrier-reva',fabrication_ready=False,physical_orientation_verified=False,baseline_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),parts=parts,host_harness=dict(header='61206021621',mate='61206023021',maximum_cable_mm=100,pins=sorted(mapping,key=lambda r:r['pin']),nc=[59,60]),reserve=dict(power_ref='J7',pins={'1':'GND','2':'V5_MODULE','3':'P_VSYS'},status_gpio={'SUPPLY_OK':32,'RESERVE_OK':33,'PRESENT_N':36},daughterboard_in_first_order=False),holds=['SD engineering drawing and footprint approval','Connector mechanical/mating drawing review','Four-layer routing and independent manufacturing review'])
def render(c):
 q=lambda s:json.dumps(str(s));font='(effects (font (size 1.27 1.27)))'
 libs=[];instances=[];labels=[];ncs=[];wires=[];rootid=uid('root')
 for part in c['parts']:
  ref=part['ref'];pins=part['pins'];half=(len(pins)+1)//2;height=max(2.54,half*2.54);width=15.24
  lib=f'(symbol "RevA:{ref}" (pin_names (offset 0.508)) (in_bom yes) (on_board yes) (property "Reference" "{ref}" (at 0 {height/2+5.08} 0) {font}) (property "Value" {q(part["value"])} (at 0 {height/2+2.54} 0) {font}) (symbol "{ref}_0_1" (rectangle (start {-width} {height/2}) (end {width} {-height/2}) (stroke (width 0.254) (type default)) (fill (type background)))) (symbol "{ref}_1_1" '
  for j,(num,name,typ,net) in enumerate(pins):
   left=j<half;k=j if left else j-half;px=-20.32 if left else 20.32;py=height/2-1.27-k*2.54
   lib+=f'(pin {typ} line (at {px} {py} {0 if left else 180}) (length 5.08) (name {q(name)} {font}) (number "{num}" {font})) '
   x=round(part['x']+px,4);y=round(part['y']-py,4);ex=round(x+(-5.08 if left else 5.08),4)
   if net is None:ncs.append(f'(no_connect (at {x} {y}) (uuid {uid(ref+str(num)+"nc")}))');continue
   wires.append(f'(wire (pts (xy {x} {y}) (xy {ex} {y})) (stroke (width 0) (type default)) (uuid {uid(ref+str(num)+"wire")}))')
   labels.append(f'(label {q(net)} (at {ex} {y} 0) (effects (font (size 1.05 1.05)) (justify {"right" if left else "left"} bottom)) (uuid {uid(ref+str(num)+"label")}))')
  libs.append(lib+'))');props=''
  for name,val,dy in [('Reference',ref,-height/2-5.08),('Value',part['value'],-height/2-2.54),('Footprint',part['footprint'],0),('Datasheet',part['datasheet'],0)]:
   props+=f'(property {q(name)} {q(val)} (at {part["x"]} {part["y"]+dy} 0) (effects (font (size 1.27 1.27))'+(' hide' if name in ['Footprint','Datasheet'] else '')+')) '
  instances.append(f'(symbol (lib_id "RevA:{ref}") (at {part["x"]} {part["y"]} 0) (unit 1) (in_bom yes) (on_board yes) (uuid {uid(ref)}) {props} (instances (project "carrier" (path "/{rootid}" (reference "{ref}") (unit 1)))))')
 notes=[]
 for y,t in [(18,'Pico1715 Rev A / FOUR-LAYER CANDIDATE / NOT FOR FABRICATION'),(28,'J6: straight-through 60-pin host harness; A=odd, B=even; 59/60 NC. Separate unqualified EFS58 adapter.'),(38,'J7 reserve POWER only: 1 GND, 2 raw module 5V, 3 backed VSYS. Keep D1 fitted; optional daughter not included.'),(48,'SD and connector drawing approval remain open. RESET2 input only. Power off before mode or cable changes.')]:
  notes.append(f'(text {q(t)} (at 20 {y*0.7+4} 0) (effects (font (size 1.5 1.5)) (justify left)) (uuid {uid(t)}))')
 (OUT/'carrier.kicad_sch').write_text(f'(kicad_sch (version 20250114) (generator "pico1715") (uuid {rootid}) (paper "A0") (lib_symbols '+''.join(libs)+') '+''.join(instances+wires+labels+ncs+notes)+')\n')
 (OUT/'RevA.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "pico1715") '+''.join(libs).replace('"RevA:','"')+')\n')
 (OUT/'sym-lib-table').write_text('(sym_lib_table (lib (name "RevA") (type "KiCad") (uri "${KIPRJMOD}/RevA.kicad_sym") (options "") (descr "Original Rev A symbols")))\n')
 flibs=sorted({p['footprint'].split(':')[0] for p in c['parts']})
 (OUT/'fp-lib-table').write_text('(fp_lib_table '+''.join('(lib (name "'+n+'") (type "KiCad") (uri "'+('${KIPRJMOD}/../carrier/Pico1715_Carrier.pretty' if n=='Pico1715_Carrier' else '${KICAD10_FOOTPRINT_DIR}/'+n+'.pretty')+'") (options "") (descr ""))' for n in flibs)+')\n')
def main():
 OUT.mkdir(exist_ok=True);c=contract();render(c)
 (OUT/"carrier.kicad_pro").write_bytes((ROOT/"hardware/carrier/carrier.kicad_pro").read_bytes())
 (OUT/'connections.json').write_text(json.dumps(c,indent=2)+'\n')
 (OUT/'bom.tsv').write_text('Reference\tValue\tFootprint\tDatasheet\n'+''.join('\t'.join(str(p[k]) or '-' for k in ['ref','value','footprint','datasheet'])+'\n' for p in c['parts']))
 print('Rev A schematic:',len(c['parts']),'parts; J6 host and J7 reserve power; baseline unchanged')
if __name__=='__main__':main()
