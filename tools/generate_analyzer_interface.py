#!/usr/bin/env python3
"""Generate original, pin-explicit KiCad bench adapter and connection manifest."""
import json
from pathlib import Path
import uuid
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'hardware/analyzer-interface'
uid=lambda s:str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/analyzer-interface/'+s))
q=lambda s:json.dumps(str(s))
font='(effects (font (size 1.27 1.27)))'
parts=[]
def add(ref,value,pins,x,y,footprint='',datasheet=''):
    # Pins: number, displayed name, electrical type, net (None = explicit NC).
    x=round(round((x*0.7+7.62)/1.27)*1.27,4);y=round(round(y*0.7/1.27)*1.27,4)
    parts.append(dict(ref=ref,value=value,pins=pins,x=x,y=y,footprint=footprint,datasheet=datasheet))
so20='Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm'
so14='Package_SO:SOIC-14_3.9x8.7mm_P1.27mm'
def trans(ref,value,a,b,rail,oe,x,y):
    pins=[(1,'DIR','input',rail),(19,'OE_N','input',oe),(20,'VCC','power_in',rail),(10,'GND','power_in','GND')]
    pins += [(i+2,'A'+str(i),'bidirectional',n) for i,n in enumerate(a)]
    pins += [(18-i,'B'+str(i),'bidirectional',n) for i,n in enumerate(b)]
    add(ref,value,pins,x,y,so20,'https://www.ti.com/lit/ds/symlink/'+value.lower().replace('dwr','')+'.pdf')

# Pin-explicit receive-only adapter. No FPGA/Pico signal reaches a host output.
mapping=json.loads((ROOT/'hardware/boards/hx8k-analyzer-pins.json').read_text())
x2=json.loads((ROOT/'hardware/boards/x2-contacts.json').read_text())
contacts={c['contact']:None for c in x2['contacts']}
for c in x2['contacts']:
    if c['net'] in ('GND','V5_HOST'):contacts[c['contact']]=c['net']
    elif c['source_signal'].startswith('AB'):contacts[c['contact']]='H_A'+c['source_signal'][2:]
    elif c['source_signal'].startswith('DB'):contacts[c['contact']]='H_D'+c['source_signal'][2:]
controls={'A9':'MREQ_N','B24':'IORQ_N','B8':'RD_N','A8':'WR_N','A26':'M1_N',
          'A25':'RFSH_N','A21':'CLK','A20':'RESET_N','A24':'WAIT_N','B23':'INT_N',
          'B20':'BUSRQ_N','A27':'BAO_N','B10':'PRIORITY'}
for pin,name in controls.items():contacts[pin]='H_'+name
contacts['A10']='H_PRIORITY_OUT'
add('X2','PC1715_X2_ANALYZER',[(c['contact'],c['source_signal'].split(' (')[0],'passive',contacts[c['contact']]) for c in x2['contacts']],760,115)
inputs=[r['adapter_net'] for r in mapping['signals'] if r['signal'].startswith('bus_sample')]
for group in range(5):
    nets=inputs[group*8:group*8+8]
    pins=[(1,'OE1_N','input','GND'),(19,'OE2_N','input','GND'),(20,'VCC','power_in','V3P3'),(10,'GND','power_in','GND')]
    pins += [(2+i,'A'+str(i+1),'input','H_'+nets[i][2:] if i<len(nets) else 'GND') for i in range(8)]
    pins += [(18-i,'Y'+str(i+1),'tri_state',nets[i] if i<len(nets) else None) for i in range(8)]
    add('U'+str(group+1),'SN74LVC541ADWR',pins,90+140*group,85,so20,'https://www.ti.com/lit/ds/symlink/sn74lvc541a.pdf')
add('U6','TLV803EA30DBZR',[(1,'GND','power_in','GND'),(2,'RESET_N','open_collector','CARD_PG'),(3,'VDD','power_in','V3P3')],90,185,'Package_TO_SOT_SMD:SOT-23','https://www.ti.com/lit/ds/symlink/tlv803e.pdf')
def passive(ref,value,a,b,x,y):
    add(ref,value,[(1,'1','passive',a),(2,'2','passive',b)],x,y,'Resistor_SMD:R_0805_2012Metric')
passive('R1','0R','H_PRIORITY','H_PRIORITY_OUT',230,185)
passive('R2','10k','V5_HOST','H_PRIORITY',370,185)
passive('R3','2k2','V3P3','CARD_PG',510,185)
passive('R4','22k','CARD_PG','GND',650,185)
# The clear input defaults HIGH; all other Pico controls default LOW.
for i,(net,rail) in enumerate([('CAPTURE_CLEAR','V3P3'),('CAPTURE_ENABLE','GND'),('LINK_SYNC_N','GND'),('PICO_ACK','GND')]):
    passive('R'+str(i+5),'4k7',net,rail,90+140*i,245)
for i in range(6):
    add('C'+str(i+1),'100nF',[(1,'1','passive','V3P3'),(2,'2','passive','GND')],90+120*i,430,'Capacitor_SMD:C_0805_2012Metric')
for header,x in [('EXT1',390),('EXT2',570),('EXT3',750)]:
    assigned={int(r['header'][1]):r['adapter_net'] for r in mapping['signals'] if r['header'] and r['header'][0]==header}
    # Official Rev B1 headers: pin 2 GND; power pins deliberately not paralleled.
    for ground in (2,4,8):assigned[ground]='GND'
    add(header,'OLIMEX_'+header,[(i,assigned.get(i,'NC') or 'NC','passive',assigned.get(i)) for i in range(1,41)],x,330)
pico=[r for r in mapping['signals'] if r['pico_gpio'] is not None]
add('J1','PICO_GPIO_LOGICAL',[('GP'+str(r['pico_gpio']),'GP'+str(r['pico_gpio']),'passive',r['adapter_net']) for r in pico]+[('GND','GND','passive','GND')],90,330)
add('J2','FPGA_3V3_POWER',[(1,'V3P3','power_out','V3P3'),(2,'GND','power_out','GND')],230,330)
# Host +5 supplies ONLY the priority pull-up, not card logic or USB power.
# One symbol per component: unambiguous pin numbers, no inherited library aliases.
libs=[];instances=[];labels=[];ncs=[];wires=[]
rootid=uid('root')
for c in parts:
    ref=c['ref'];sym=ref; pins=c['pins']; half=(len(pins)+1)//2
    height=max(2.54,half*2.54); width=15.24
    lib=f'(symbol "Pico1715:{sym}" (pin_names (offset 0.508)) (in_bom yes) (on_board yes) '
    lib+=f'(property "Reference" "{ref}" (at 0 {height/2+5.08} 0) {font}) (property "Value" {q(c["value"])} (at 0 {height/2+2.54} 0) {font}) '
    lib+=f'(symbol "{sym}_0_1" (rectangle (start {-width} {height/2}) (end {width} {-height/2}) (stroke (width 0.254) (type default)) (fill (type background)))) '
    lib+=f'(symbol "{sym}_1_1" '
    for j,(num,name,typ,net) in enumerate(pins):
        left=j<half; k=j if left else j-half;px=-20.32 if left else 20.32;py=height/2-1.27-k*2.54
        lib+=f'(pin {typ} line (at {px} {py} {0 if left else 180}) (length 5.08) (name {q(name)} {font}) (number "{num}" {font})) '
        x=round(c['x']+px,4);y=round(c['y']-py,4);ex=round(x+(-5.08 if left else 5.08),4)
        if net is None:ncs.append(f'(no_connect (at {x} {y}) (uuid {uid(ref+str(num)+"nc")}))');continue
        wires.append(f'(wire (pts (xy {x} {y}) (xy {ex} {y})) (stroke (width 0) (type default)) (uuid {uid(ref+str(num)+"wire")}))')
        # Text extends away from symbol; electrical attachment at wire end.
        labels.append(f'(label {q(net)} (at {ex} {y} 0) (effects (font (size 1.05 1.05)) (justify {"right" if left else "left"} bottom)) (uuid {uid(ref+str(num)+"label")}))')
    libs.append(lib+'))')
    props=''
    for name,val,dy in [('Reference',ref,-height/2-5.08),('Value',c['value'],-height/2-2.54),('Footprint',c['footprint'],0),('Datasheet',c['datasheet'],0)]:
        props+=f'(property {q(name)} {q(val)} (at {c["x"]} {c["y"]+dy} 0) (effects (font (size 1.27 1.27))'+(' hide' if name in ['Footprint','Datasheet'] else '')+')) '
    instances.append(f'(symbol (lib_id "Pico1715:{sym}") (at {c["x"]} {c["y"]} 0) (unit 1) (in_bom yes) (on_board yes) (uuid {uid(ref)}) {props} (instances (project "analyzer-interface" (path "/{rootid}" (reference "{ref}") (unit 1)))))')
text=[]
for y,t in [(18,'Pico1715 passive analyzer adapter / draft A / NOT MACHINE-QUALIFIED'),(28,'Input-only LVC541 receivers. R1 physically bypasses X2 B10 to A10. No host output stage.'),(38,'Different harness from controller adapter. J1 labels are GPIO identifiers, not Pico header positions.'),(48,'FPGA supplies V3P3; host 5V feeds only R2. Common ground. Module power sequencing remains a bench gate.')]:
    text.append(f'(text {q(t)} (at 20 {y*0.7+4} 0) (effects (font (size 1.5 1.5)) (justify left)) (uuid {uid(t)}))')
s=f'(kicad_sch (version 20250114) (generator "pico1715") (uuid {rootid}) (paper "A2") (lib_symbols '+''.join(libs)+') '+''.join(instances+wires+labels+ncs+text)+')\n'
OUT.mkdir(exist_ok=True)
(OUT/'analyzer-interface.kicad_sch').write_text(s)
(OUT/'Pico1715.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "pico1715") '+''.join(libs).replace('"Pico1715:', '"')+')\n')
(OUT/'sym-lib-table').write_text('(sym_lib_table (lib (name "Pico1715") (type "KiCad") (uri "${KIPRJMOD}/Pico1715.kicad_sym") (options "") (descr "Original pin-explicit adapter symbols")))\n')
flibs=sorted({c['footprint'].split(':')[0] for c in parts if c['footprint']})
(OUT/'fp-lib-table').write_text('(fp_lib_table '+''.join('(lib (name "'+n+'") (type "KiCad") (uri "${KICAD10_FOOTPRINT_DIR}/'+n+'.pretty") (options "") (descr ""))' for n in flibs)+')\n')
(OUT/'connections.json').write_text(json.dumps({'schema':1,'revision':'analyzer-A','physical_orientation_verified':False,'parts':parts},indent=2)+'\n')
(OUT/'bom.tsv').write_text('Reference\tValue\tFootprint\tDatasheet\n'+''.join('\t'.join((str(c[k]) or '-') for k in ['ref','value','footprint','datasheet'])+'\n' for c in parts))
(OUT/'analyzer-interface.kicad_pro').write_text('{}\n')
print(f'Generated {len(parts)} passive analyzer adapter parts')

lines=['# HX8K passive analyzer harness', '', 'Generated from hx8k-analyzer-pins.json. Rev B1 only; this is NOT the controller harness.', '', '| FPGA signal | Adapter net | Header / pin | FPGA ball | Pico GPIO |', '| --- | --- | --- | --- | --- |']
for r in mapping['signals']:
    header=' / '.join(r['header']) if r['header'] else 'Onboard oscillator'
    gpio='GP'+str(r['pico_gpio']) if r['pico_gpio'] is not None else '—'
    lines.append(f"| `{r['signal']}` | {r['adapter_net'] or '—'} | {header} | {r['package_pin']} | {gpio} |")
lines += ['', 'EXT1/EXT2/EXT3 ground contacts 2, 4 and 8 connect to common GND.',
          'J1 uses GPIO identifiers, not Pico physical header numbers. J2 supplies V3P3 from the FPGA rail.',
          'Leave GP15, GP18–20 and SD pins disconnected from this analyzer harness.',
          'Host /RESET2 is sampled; it is not connected to card reset or Pico GP15.',
          'All module signal wiring is 3.3 V. Never connect X2 directly to FPGA or Pico.']
(ROOT/'hardware/boards/hx8k-analyzer-wiring.md').write_text('\n'.join(lines)+'\n')
