#!/usr/bin/env python3
"""Generate a separate optional reserve schematic; no carrier pin assignment."""
import json,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'hardware/backup-power'
uid=lambda s:str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/backup/'+s));q=lambda s:json.dumps(str(s));font='(effects (font (size 1.27 1.27)))'
parts=[]
def add(ref,value,pins,footprint='',datasheet=''):
 i=len(parts);parts.append(dict(ref=ref,value=value,pins=pins,x=round(63.5+(i%5)*106.68,4),y=round(63.5+(i//5)*43.18,4),footprint=footprint,datasheet=datasheet))
def two(ref,value,a,b,names=('1','2')):add(ref,value,[(1,names[0],'passive',a),(2,names[1],'passive',b)])
add('J1','RAW_5V_INPUT',[(1,'5V','power_out','V5_MODULE'),(2,'GND','power_out','GND')])
add('J2','PICO_VSYS_OUTPUT',[(1,'VSYS','passive','P_VSYS'),(2,'GND','passive','GND')])
add('J3','STATUS_INTERFACE_NO_GPIO_ASSIGNED',[(1,'P3V3_FROM_PICO','power_out','P3V3'),(2,'GND','passive','GND'),(3,'SUPPLY_OK','passive','SUPPLY_OK'),(4,'RESERVE_OK','passive','RESERVE_OK')])
# Diode pin 1=K, 2=A. D1 represents the EXISTING carrier feed, not a parallel second feed.
two('D1','SS14_EXISTING_CARRIER','P_VSYS','V5_MODULE',('K','A'))
two('D2','SS14_CHARGE_BLOCK','CHARGE_IN','V5_MODULE',('K','A'))
two('R1','100R_1W_1pct','CHARGE_IN','CAP_TOP')
two('C1','TV1030-3R0106-R_10F_3V','CAP_TOP','CAP_MID',('+','-'))
two('C2','TV1030-3R0106-R_10F_3V','CAP_MID','GND',('+','-'))
two('R2','10k_1pct','CAP_TOP','CAP_MID');two('R3','10k_1pct','CAP_MID','GND')
for ref,hi,lo in [('U1','CAP_TOP','CAP_MID'),('U2','CAP_MID','GND')]:
 add(ref,'TL431AIDBZR_2V495_CLAMP',[(1,'K','passive',hi),(2,'REF','input',hi),(3,'A','passive',lo)],'Package_TO_SOT_SMD:SOT-23','https://www.ti.com/lit/ds/symlink/tl431.pdf')
two('F1','0.75A_FUSE_CANDIDATE','CAP_TOP','CAP_FUSED')
two('D3','SS14_DISCHARGE','P_VSYS','CAP_FUSED',('K','A'))
for idx,rail,upper,output in [(3,'V5_MODULE','267k','SUPPLY_OK'),(4,'CAP_TOP','280k','RESERVE_OK')]:
 sense='SENSE'+str(idx);ref='REF'+str(idx)
 add('U'+str(idx),'TLV3011BIDBVR',[(1,'OUT','open_collector',output),(2,'GND','power_in','GND'),(3,'IN_PLUS','input',sense),(4,'IN_MINUS','input',ref),(5,'REF','output',ref),(6,'VCC','power_in','P3V3')],'Package_TO_SOT_SMD:SOT-23-6','https://www.ti.com/lit/ds/symlink/tlv3011.pdf')
 two('R'+str(idx*3-5),upper+'_1pct',rail,sense)
 two('R'+str(idx*3-4),'100k_1pct',sense,'GND')
 two('R'+str(idx*3-3),'10k', 'P3V3',output)
 two('C'+str(idx),'100nF','P3V3','GND')
assert len({p['ref'] for p in parts})==len(parts)
libs=[];instances=[];labels=[];wires=[];rootid=uid('root')
for c in parts:
 ref=c['ref'];pins=c['pins'];half=(len(pins)+1)//2;height=max(2.54,half*2.54);width=15.24
 lib=f'(symbol "Backup:{ref}" (pin_names (offset 0.508)) (in_bom yes) (on_board yes) (property "Reference" "{ref}" (at 0 {height/2+5.08} 0) {font}) (property "Value" {q(c["value"])} (at 0 {height/2+2.54} 0) {font}) (symbol "{ref}_0_1" (rectangle (start {-width} {height/2}) (end {width} {-height/2}) (stroke (width 0.254) (type default)) (fill (type background)))) (symbol "{ref}_1_1" '
 for j,(num,name,typ,net) in enumerate(pins):
  left=j<half;k=j if left else j-half;px=-20.32 if left else 20.32;py=height/2-1.27-k*2.54
  lib+=f'(pin {typ} line (at {px} {py} {0 if left else 180}) (length 5.08) (name {q(name)} {font}) (number "{num}" {font})) '
  x=round(c['x']+px,4);y=round(c['y']-py,4);ex=round(x+(-5.08 if left else 5.08),4)
  wires.append(f'(wire (pts (xy {x} {y}) (xy {ex} {y})) (stroke (width 0) (type default)) (uuid {uid(ref+str(num)+"wire")}))')
  labels.append(f'(label {q(net)} (at {ex} {y} 0) (effects (font (size 1.05 1.05)) (justify {"right" if left else "left"} bottom)) (uuid {uid(ref+str(num)+"label")}))')
 libs.append(lib+'))');props=''
 for name,val,dy in [('Reference',ref,-height/2-5.08),('Value',c['value'],-height/2-2.54),('Footprint',c['footprint'],0),('Datasheet',c['datasheet'],0)]:
  props+=f'(property {q(name)} {q(val)} (at {c["x"]} {c["y"]+dy} 0) (effects (font (size 1.27 1.27))'+(' hide' if name in ['Footprint','Datasheet'] else '')+')) '
 instances.append(f'(symbol (lib_id "Backup:{ref}") (at {c["x"]} {c["y"]} 0) (unit 1) (in_bom yes) (on_board yes) (uuid {uid(ref)}) {props} (instances (project "backup" (path "/{rootid}" (reference "{ref}") (unit 1)))))')
notes=[]
for y,text in [(15,'Pico1715 optional reserve / electrical draft / NOT FOR FABRICATION'),(23,'D1 is the existing carrier diode. Omit the entire reserve branch for normal operation.'),(31,'J3 status pins have NO carrier GPIO allocation. Protected mode remains disabled pending integration and bench evidence.'),(350,'Pico + PSRAM + SD are backed up. FPGA and host rails are NOT backed up. Verify off-state isolation of every crossing.'),(358,'C1/C2: candidate 3 V EDLCs; U1/U2 shunt-clamp each cell near 2.495 V. Verify transient balance and clamp stability.'),(366,'Use current-limited charging through R1; discharge bypasses R1 through F1/D3. Fuse and thermal selection are provisional.')]:
 notes.append(f'(text {q(text)} (at 20 {y} 0) (effects (font (size 1.5 1.5)) (justify left)) (uuid {uid(text)}))')
OUT.mkdir(exist_ok=True)
(OUT/'backup.kicad_sch').write_text(f'(kicad_sch (version 20250114) (generator "pico1715") (uuid {rootid}) (paper "A2") (lib_symbols '+''.join(libs)+') '+''.join(instances+wires+labels+notes)+')\n')
(OUT/'Backup.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "pico1715") '+''.join(libs).replace('"Backup:','"')+')\n')
(OUT/'sym-lib-table').write_text('(sym_lib_table (lib (name "Backup") (type "KiCad") (uri "${KIPRJMOD}/Backup.kicad_sym") (options "") (descr "Original backup draft symbols")))\n')
(OUT/'backup.kicad_pro').write_text('{}\n')
(OUT/'fp-lib-table').write_text('(fp_lib_table (lib (name "Package_TO_SOT_SMD") (type "KiCad") (uri "${KICAD10_FOOTPRINT_DIR}/Package_TO_SOT_SMD.pretty") (options "") (descr "")))\n')
(OUT/'connections.json').write_text(json.dumps(dict(schema=1,fabrication_ready=False,carrier_integrated=False,parts=parts),indent=2)+'\n')
print('Generated',len(parts),'draft components')
