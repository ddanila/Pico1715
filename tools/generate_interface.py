#!/usr/bin/env python3
"""Generate original, pin-explicit KiCad bench adapter and connection manifest."""
import json
from pathlib import Path
import uuid
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'hardware/interface'
uid=lambda s:str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/interface/'+s))
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
haddr=['H_A'+str(i) for i in range(8)]; faddr=['F_A'+str(i) for i in range(8)]
hdata=['H_D'+str(i) for i in range(8)]; fin=['F_DI'+str(i) for i in range(8)]; fout=['F_DO'+str(i) for i in range(8)]
controls=['IORQ_N','M1_N','MREQ_N','RD_N','WR_N','IEI','RESET_N']
trans('U1','SN74LVC245ADWR',haddr,faddr,'V3P3','GND',90,85)
trans('U2','SN74LVC245ADWR',hdata,fin,'V3P3','GND',230,85)
trans('U3','SN74LVC245ADWR',['H_'+s for s in controls]+['UNUSED_RX'],['F_'+s for s in controls]+[None],'V3P3','GND',370,85)
trans('U4','SN74AHCT541DWR',fout,hdata,'V5_HOST','DATA_OE_N',510,85)
# Unidirectional driver: unlike a 245, A inputs have no output stage.
parts[-1]['pins']=[(n,('OE1_N' if n==1 else 'OE2_N' if n==19 else name),
    ('input' if 2<=n<=9 else 'tri_state' if 11<=n<=18 else typ),
    ('GND' if n==1 else net)) for n,name,typ,net in parts[-1]['pins']]
add('U5','SN74AHCT1G125DBVR',[(1,'OE_N','input','IEO_OE_N'),(2,'A','input','F_IEO'),(3,'GND','power_in','GND'),(4,'Y','tri_state','H_IEO'),(5,'VCC','power_in','V5_HOST')],650,85,'Package_TO_SOT_SMD:SOT-23-5','https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf')
def gates(ref,value,connections,x,y):
    p=[(7,'GND','power_in','GND'),(14,'VCC','power_in','V3P3')]
    for k,((a,b,o),(na,nb,no)) in enumerate(zip([(1,2,3),(4,5,6),(9,10,8),(12,13,11)],connections)):
        p += [(a,f'{k+1}A','input',na),(b,f'{k+1}B','input',nb),(o,f'{k+1}Y','output',no)]
    add(ref,value,p,x,y,so14,'https://www.ti.com/lit/ds/symlink/'+value.lower().removesuffix('dr')+'.pdf')
gates('U6','SN74LVC08ADR',[('PG3','PG5','POWER_GOOD'),('POWER_GOOD','CDONE','CONFIG_OK'),('CONFIG_OK','BACKEND_READY','BACKEND_OK'),('BACKEND_OK','F_RESET_N','RESET_OK')],90,185)
gates('U7','SN74LVC08ADR',[('RESET_OK','ARM','ARMED'),('GND','GND',None),('GND','GND',None),('GND','GND',None)],230,185)
gates('U8','SN74LVC00ADR',[('ARMED','F_HOST_OE','DATA_EN_N'),('ARMED','F_WAIT','WAIT_EN_N'),('ARMED','F_INT','INT_EN_N'),('ARMED','ARMED','IEO_EN_N')],370,185)
p=[(7,'GND','power_in','GND'),(14,'VCC','power_in','V3P3')]
for k,(a,o,na,no) in enumerate([(1,2,'DATA_EN_N','DATA_OE_N'),(3,4,'WAIT_EN_N','H_WAIT_N'),(5,6,'INT_EN_N','H_INT_N'),(9,8,'IEO_EN_N','IEO_OE_N'),(11,10,'V3P3',None),(13,12,'V3P3',None)]):p += [(a,f'{k+1}A','input',na),(o,f'{k+1}Y','open_collector',no)]
add('U9','SN74LVC07ADR',p,510,185,so14,'https://www.ti.com/lit/ds/symlink/sn74lvc07a.pdf')
for ref,val,rail,net,x in [('U10','TLV803EA30DBZR','V3P3','PG3',650),('U11','TLV803EA46DBZR','V5_HOST','PG5',760)]:
    add(ref,val,[(1,'GND','power_in','GND'),(2,'RESET_N','open_collector',net),(3,'VDD','power_in',rail)],x,185,'Package_TO_SOT_SMD:SOT-23','https://www.ti.com/lit/ds/symlink/tlv803e.pdf')
def connector(ref,name,nets,x,y,power=False):
    add(ref,name,[(i+1,n,'power_out' if power else 'passive',n) for i,n in enumerate(nets)],x,y)
connector('J1','HOST_ADDRESS',haddr+['GND'],80,290)
connector('J2','HOST_DATA',hdata+['GND'],210,290)
connector('J3','HOST_CONTROL',['H_'+s for s in controls]+['H_WAIT_N','H_INT_N','H_IEO','GND'],350,290)
connector('J4','FPGA_ADDRESS',faddr+['GND'],490,290)
connector('J5','FPGA_DATA_IN',fin+['GND'],630,290)
connector('J6','FPGA_DATA_OUT',fout+['GND'],760,290)
connector('J7','FPGA_CONTROL',['F_'+s for s in controls]+['F_HOST_OE','F_WAIT','F_INT','F_IEO','POWER_GOOD','GND'],90,390)
connector('J8','QUALIFIERS',['CDONE','BACKEND_READY','GND'],240,390)
connector('J9','EXTERNAL_RAILS',['V3P3','V5_HOST','GND'],370,390,True)
connector('JP1','ARM_SHUNT',['V3P3','ARM'],500,390)
connector('J10','SCOPE',['GND','ARMED','F_HOST_OE','DATA_OE_N','F_WAIT','H_WAIT_N','F_INT','H_INT_N','PG3','PG5'],650,390)
# Exact resistor connections, with values and labels visible on the page.
rs=[('2k2','V3P3','PG3'),('22k','PG3','GND'),('2k2','V5_HOST','PG5'),('22k','PG5','GND'),
    ('1k','V5_HOST','DATA_OE_N'),('1k','V5_HOST','IEO_OE_N'),('4k7','ARM','GND'),
    ('4k7','CDONE','GND'),('4k7','BACKEND_READY','GND'),('4k7','F_HOST_OE','GND'),
    ('4k7','F_WAIT','GND'),('4k7','F_INT','GND'),('4k7','F_IEO','GND'),('4k7','UNUSED_RX','GND')]
for i,(v,a,b) in enumerate(rs):
    add('R'+str(i+1),v,[(1,'1','passive',a),(2,'2','passive',b)],55+(i%7)*112,458+(i//7)*32,'Resistor_SMD:R_0805_2012Metric')
for i,rail in enumerate(['V3P3']*3+['V5_HOST']*2+['V3P3']*5+['V5_HOST']):
    add('C'+str(i+1),'100nF',[(1,'1','passive',rail),(2,'2','passive','GND')],55+(i%7)*112,525+(i//7)*28,'Capacitor_SMD:C_0805_2012Metric')
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
    instances.append(f'(symbol (lib_id "Pico1715:{sym}") (at {c["x"]} {c["y"]} 0) (unit 1) (in_bom yes) (on_board yes) (uuid {uid(ref)}) {props} (instances (project "bench-interface" (path "/{rootid}" (reference "{ref}") (unit 1)))))')
text=[]
for y,t in [(18,'Pico1715 buffered bench adapter — rev A / NOT MACHINE-QUALIFIED'),(25,'J1-J3 are LOGICAL BUS HEADERS, NOT X2 contact numbers. JP1 open = disarmed. No PCB footprint assigned to the host connector.'),(33,'V3P3 from FPGA board only; V5_HOST from host or isolated fixture supply. Common GND. Never parallel module regulator outputs.'),(42,'WAIT/INT pull-ups belong to the host/fixture. U9 is open-drain. C1-C11: one 100 nF per IC; place at supply pins.'),(437,'Pull-ups, fail-safe pull-downs and local decoupling. Pin-explicit boxes; resistor/capacitor values identify passive function.')]:
    text.append(f'(text {q(t)} (at 20 {y*0.7+(4 if y<50 else 0)} 0) (effects (font (size 1.5 1.5)) (justify left)) (uuid {uid(t)}))')
s=f'(kicad_sch (version 20250114) (generator "pico1715") (uuid {rootid}) (paper "A2") (lib_symbols '+''.join(libs)+') '+''.join(instances+wires+labels+ncs+text)+')\n'
OUT.mkdir(exist_ok=True)
(OUT/'bench-interface.kicad_sch').write_text(s)
(OUT/'Pico1715.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "pico1715") '+''.join(libs).replace('"Pico1715:', '"')+')\n')
(OUT/'sym-lib-table').write_text('(sym_lib_table (lib (name "Pico1715") (type "KiCad") (uri "${KIPRJMOD}/Pico1715.kicad_sym") (options "") (descr "Original pin-explicit adapter symbols")))\n')
flibs=sorted({c['footprint'].split(':')[0] for c in parts if c['footprint']})
(OUT/'fp-lib-table').write_text('(fp_lib_table '+''.join('(lib (name "'+n+'") (type "KiCad") (uri "${KICAD10_FOOTPRINT_DIR}/'+n+'.pretty") (options "") (descr ""))' for n in flibs)+')\n')
(OUT/'connections.json').write_text(json.dumps({'schema':1,'revision':'A','x2_contact_assignment_verified':False,'parts':parts},indent=2)+'\n')
# TSV is a connection list, not an order-ready production BOM.
(OUT/'bom.tsv').write_text('Reference\tValue\tFootprint\tDatasheet\n'+''.join('\t'.join((str(c[k]) or '-') for k in ['ref','value','footprint','datasheet'])+'\n' for c in parts))
print(f'Generated {len(parts)} parts; X2 contacts intentionally unassigned')
