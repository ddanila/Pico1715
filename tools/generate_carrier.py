#!/usr/bin/env python3
"""Generate original combined-carrier schematic and both physical pin profiles.

The older bench adapters remain independent, unchanged targets.
"""
import json
from pathlib import Path
import uuid
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'hardware/carrier'
uid=lambda s:str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/carrier/'+s))
q=lambda s:json.dumps(str(s))
font='(effects (font (size 1.27 1.27)))'
parts=[]
def add(ref,value,pins,x=0,y=0,footprint='',datasheet=''):
    # Automatic spacious grid on A0; full pin numbering, never inferred aliases.
    i=len(parts); x=round(round((80+(i%10)*110)/1.27)*1.27,4); y=round(round((100+(i//10)*90)/1.27)*1.27,4)
    ref={'PGM':'J1','PICO':'J2','SD':'J3','POWER':'J4','TP':'J5'}.get(ref,ref)
    parts.append(dict(ref=ref,value=value,pins=pins,x=x,y=y,footprint=footprint,datasheet=datasheet))
so20='Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm'
so14='Package_SO:SOIC-14_3.9x8.7mm_P1.27mm'
base=json.loads((ROOT/'hardware/boards/hx8k-pins.json').read_text())
oldana=json.loads((ROOT/'hardware/boards/hx8k-analyzer-pins.json').read_text())
cnets={}
for r in base['signals']:
    s=r['signal'];net=None;gp=None
    for prefix,target in [('host_addr','F_A'),('host_din','F_D'),('host_dout','F_DO')]:
        if s.startswith(prefix+'['):net=target+s.split('[')[1][:-1]
    if s.startswith('pico_data['):gp=int(s.split('[')[1][:-1])
    if s.startswith('pico_reg['):gp=8+int(s.split('[')[1][:-1])
    gpio={'pico_write':12,'pico_request':13,'pico_ack':14,'pico_index':16,'pico_mark':17,'ack_toggle':18,'reti_toggle':19,'ack_index':20,'backend_ready':21}
    gp=gpio.get(s,gp)
    if gp is not None:net='L_GP'+str(gp)
    net={'iorq_n':'F_IORQ_N','m1_n':'F_M1_N','mreq_n':'F_MREQ_N','rd_n':'F_RD_N','wr_n':'F_WR_N','iei':'F_PRIORITY','host_reset_n':'F_RESET_N','power_good':'POWER_GOOD','host_oe':'F_HOST_OE','wait_pull_low':'F_WAIT','int_pull_low':'F_INT','ieo':'F_IEO','fault':'F_FAULT'}.get(s,net)
    r.update(adapter_net=net,pico_gpio=gp)
    if net:cnets[net]=r
# New receive-only contacts never share a physical FPGA pin with a host driver.
extra=[('F_A'+str(i)) for i in range(8,16)]+['F_RFSH_N','F_CLK','F_WAIT_N','F_INT_N','F_BUSRQ_N','F_BAO_N','PERSONALITY_CTL']
balls=['D6','A5','B5','E6','B4','A2','D5','A1','C5','C4','B3','D4','E5','D3','C3']
headers=[15,17,19,21,23,25,27,29,31,33,35,37,39,40,38]
for i,(net,ball,pin) in enumerate(zip(extra,balls,headers)):
    cnets[net]=dict(signal='personality_controller' if net=='PERSONALITY_CTL' else '',board_net='/PIO0_'+str(37+i),package_pin=ball,header=['EXT2',str(pin)],adapter_net=net,pico_gpio=None)
cnets['LINK_OK']=dict(signal='',board_net='/PIO1_25',package_pin='J16',header=['EXT3','29'],adapter_net='LINK_OK',pico_gpio=None)
base['signals'].append(cnets['PERSONALITY_CTL'])
base['personality']='combined carrier controller A'
ana={k:v for k,v in oldana.items() if k!='signals'};ana['signals']=[]
for r in oldana['signals']:
    s=r['signal'];net=r['adapter_net']
    if s=='clk100':row=dict(base['signals'][0])
    else:
        if s=='card_power_good':net='LINK_OK'
        if r['pico_gpio'] is not None:net='L_GP'+str(r['pico_gpio'])
        row=dict(cnets[net])
        row['signal']=s
    ana['signals'].append(row)
ana['signals'].append(dict(cnets['PERSONALITY_CTL']))
ana['personality']='combined carrier passive analyzer A'
for name,mp in [('controller',base),('analyzer',ana)]:
    path=ROOT/f'hardware/boards/hx8k-carrier-{name}'
    path.with_suffix('.json').write_text(json.dumps(mp,indent=2)+'\n')
    path.with_suffix('.pcf').write_text('# Combined carrier A ONLY; power off before changing mode.\n'+''.join(f"set_io {r['signal']} {r['package_pin']}\n" for r in mp['signals']))

# Host connector: independent A/D receive paths, switched priority return.
x2=json.loads((ROOT/'hardware/boards/x2-contacts.json').read_text())
contacts={c['contact']:None for c in x2['contacts']}
for c in x2['contacts']:
    if c['net'] in ('GND','V5_HOST'):contacts[c['contact']]=c['net']
    elif c['source_signal'].startswith('AB'):contacts[c['contact']]='H_A'+c['source_signal'][2:]
    elif c['source_signal'].startswith('DB'):contacts[c['contact']]='H_D'+c['source_signal'][2:]
controls={'A9':'MREQ_N','B24':'IORQ_N','B8':'RD_N','A8':'WR_N','A26':'M1_N','A25':'RFSH_N','A21':'CLK','A20':'RESET_N','A24':'WAIT_N','B23':'INT_N','B20':'BUSRQ_N','A27':'BAO_N','B10':'PRIORITY','A10':'PRIORITY_OUT'}
for pin,name in controls.items():contacts[pin]='H_'+name
add('X2','PC1715_X2',[(c['contact'],c['source_signal'].split(' (')[0],'power_out' if c['contact']=='A29' else 'passive',contacts[c['contact']]) for c in x2['contacts']])
inputs=[r['adapter_net'] for r in oldana['signals'] if r['signal'].startswith('bus_sample')]
for group in range(5):
    ns=inputs[group*8:group*8+8]
    pins=[(1,'OE1_N','input','GND'),(19,'OE2_N','input','GND'),(20,'VCC','power_in','V3P3'),(10,'GND','power_in','GND')]
    pins += [(2+i,'A'+str(i),'input','H_'+ns[i][2:] if i<len(ns) else 'GND') for i in range(8)]
    pins += [(18-i,'Y'+str(i),'tri_state',ns[i] if i<len(ns) else None) for i in range(8)]
    add('RX'+str(group+1),'SN74LVC541ADWR',pins,footprint=so20,datasheet='https://www.ti.com/lit/ds/symlink/sn74lvc541a.pdf')
add('U4','SN74AHCT541DWR',[(1,'OE1_N','input','GND'),(19,'OE2_N','input','DATA_OE_N'),(20,'VCC','power_in','V5_HOST'),(10,'GND','power_in','GND')]+[(i+2,'A'+str(i),'input',f'F_DO{i}') for i in range(8)]+[(18-i,'Y'+str(i),'tri_state',f'H_D{i}') for i in range(8)],footprint=so20,datasheet='https://www.ti.com/lit/ds/symlink/sn74ahct541.pdf')
add('U5','SN74AHCT1G125DBVR',[(1,'OE_N','input','IEO_OE_N'),(2,'A','input','F_IEO'),(3,'GND','power_in','GND'),(4,'Y','tri_state','DRIVEN_IEO'),(5,'VCC','power_in','V5_HOST')],footprint='Package_TO_SOT_SMD:SOT-23-5',datasheet='https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf')
def gates(ref,value,connections):
    p=[(7,'GND','power_in','GND'),(14,'VCC','power_in','V3P3')]
    for k,((a,b,o),(na,nb,no)) in enumerate(zip([(1,2,3),(4,5,6),(9,10,8),(12,13,11)],connections)):
        p += [(a,f'{k+1}A','input',na),(b,f'{k+1}B','input',nb),(o,f'{k+1}Y','output',no)]
    add(ref,value,p,footprint=so14,datasheet='https://www.ti.com/lit/ds/symlink/'+value.lower().removesuffix('dr')+'.pdf')
gates('U6','SN74LVC08ADR',[('PG3','PG5','POWER_GOOD'),('PG3','PGP','RAILS_OK'),('RAILS_OK','CDONE','LINK_OK'),('POWER_GOOD','LINK_OK','POWERED')])
gates('U7','SN74LVC08ADR',[('POWERED','PERSONALITY_CTL','QUALIFIED'),('QUALIFIED','L_GP21','BACKEND_OK'),('BACKEND_OK','F_RESET_N','RESET_OK'),('RESET_OK','MODE_CTL','ARMED')])
gates('U8','SN74LVC00ADR',[('ARMED','F_HOST_OE','DATA_EN_N'),('ARMED','F_WAIT','WAIT_EN_N'),('ARMED','F_INT','INT_EN_N'),('ARMED','ARMED','IEO_EN_N')])
gates('U13','SN74LVC00ADR',[('LINK_OK','LINK_OK','LINK_OE_N')]+[('GND','GND',None)]*3)
p=[(7,'GND','power_in','GND'),(14,'VCC','power_in','V3P3')]
for k,(a,o,na,no) in enumerate([(1,2,'DATA_EN_N','DATA_OE_N'),(3,4,'WAIT_EN_N','H_WAIT_N'),(5,6,'INT_EN_N','H_INT_N'),(9,8,'IEO_EN_N','IEO_OE_N'),(11,10,'V3P3',None),(13,12,'V3P3',None)]):p += [(a,f'{k+1}A','input',na),(o,f'{k+1}Y','open_collector',no)]
add('U9','SN74LVC07ADR',p,footprint=so14,datasheet='https://www.ti.com/lit/ds/symlink/sn74lvc07a.pdf')
for ref,val,rail,net in [('U10','TLV803EA30DBZR','V3P3','PG3'),('U11','TLV803EA46DBZR','V5_HOST','PG5'),('U12','TLV803EA30DBZR','P3V3','PGP')]:
    add(ref,val,[(1,'GND','power_in','GND'),(2,'RESET_N','open_collector',net),(3,'VDD','power_in',rail)],footprint='Package_TO_SOT_SMD:SOT-23',datasheet='https://www.ti.com/lit/ds/symlink/tlv803e.pdf')
# Physical selector: logical harness pin numbering, footprint intentionally unresolved.
add('SW1','DPDT_MODE_LOGICAL',[(1,'PASSIVE_GND','passive','GND'),(2,'COMMON_MODE','passive','MODE_CTL'),(3,'CONTROLLER_3V3','passive','V3P3'),(4,'PASSIVE_IEI','passive','H_PRIORITY'),(5,'COMMON_IEO','passive','H_PRIORITY_OUT'),(6,'CONTROLLER_IEO','passive','DRIVEN_IEO')])
# Independently powered Pico: bidirectional Ioff bus switches, no direction guessing.
for group in range(3):
    pins=[(1,'NC','no_connect',None),(19,'OE_N','input','LINK_OE_N'),(20,'VCC','power_in','V3P3'),(10,'GND','power_in','GND')]
    for i in range(8):
        gp=group*8+i
        link='F_RESET_N' if gp==15 else 'L_GP'+str(gp)
        pins += [(2+i,'A'+str(i),'bidirectional',link if gp<22 else None),(18-i,'B'+str(i),'bidirectional','P_GP'+str(gp) if gp<22 else None)]
    add('ISO'+str(group+1),'SN74CB3Q3245PWR',pins,footprint='Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm',datasheet='https://www.ti.com/lit/ds/symlink/sn74cb3q3245.pdf')
# Full physical module headers, all unused contacts explicitly NC.
for header in ('EXT1','EXT2','EXT3'):
    assigned={int(r['header'][1]):r['adapter_net'] for r in cnets.values() if r['header'] and r['header'][0]==header}
    for g in (2,4,8):assigned[g]='GND'
    if header=='EXT1':assigned.update({1:'V5_MODULE',3:'V3P3'})
    add(header,'OLIMEX_'+header,[(i,assigned.get(i,'NC'),'power_out' if header=='EXT1' and i==3 else 'passive',assigned.get(i)) for i in range(1,41)])
add('PGM','OLIMEX_PGM1_TAP',[(5,'CDONE','passive','CDONE')])
pico_pins={1:0,2:1,4:2,5:3,6:4,7:5,9:6,10:7,11:8,12:9,14:10,15:11,16:12,17:13,19:14,20:15,21:16,22:17,24:18,25:19,26:20,27:21,29:22,31:26,32:27,34:28}
pins=[]
for n in range(1,41):
    net='P_GP'+str(pico_pins[n]) if n in pico_pins else {3:'GND',8:'GND',13:'GND',18:'GND',23:'GND',28:'GND',33:'GND',38:'GND',36:'P3V3',39:'P_VSYS'}.get(n)
    pins.append((n,net or 'NC','power_out' if n==36 else 'passive',net))
add('PICO','PIM724_PICO_PLUS2',pins,datasheet='https://shop.pimoroni.com/products/pimoroni-pico-plus-2')
add('SD','MICROSD_SPI',[(1,'DAT2','passive','SD_DAT2'),(2,'DAT3_CS','input','P_GP22'),(3,'CMD_MOSI','input','P_GP27'),(4,'VDD','power_in','P3V3'),(5,'CLK','input','P_GP26'),(6,'VSS','power_in','GND'),(7,'DAT0_MISO','tri_state','P_GP28'),(8,'DAT1','passive','SD_DAT1'),('SH','SHIELD','passive','GND')])
add('POWER','REGULATED_5V_INPUT',[(1,'5V','power_out','V5_MODULE'),(2,'GND','power_out','GND')])
add('D1','SS14',[(1,'K','passive','P_VSYS'),(2,'A','passive','V5_MODULE')],footprint='Diode_SMD:D_SMA',datasheet='https://www.vishay.com/docs/88746/ss12.pdf')
add('TP','BRINGUP_PROBES',[(i+1,n,'passive',n) for i,n in enumerate(['GND','PG3','PG5','PGP','CDONE','MODE_CTL','PERSONALITY_CTL','LINK_OK','ARMED','DATA_OE_N','H_WAIT_N','H_INT_N','F_FAULT','P3V3','V3P3'])])
# Reserve capacitor/charger design stays outside this draft. No bare capacitor socket.
def resistor(value,a,b):
    ref='R'+str(1+sum(c['ref'].startswith('R') and c['ref'][1:].isdigit() for c in parts))
    add(ref,value,[(1,'1','passive',a),(2,'2','passive',b)],footprint='Resistor_SMD:R_0805_2012Metric')
for rail,net in [('V3P3','PG3'),('V5_HOST','PG5'),('P3V3','PGP')]:
    resistor('2k2',rail,net);resistor('22k',net,'GND')
for net in ['MODE_CTL','PERSONALITY_CTL','L_GP21','F_HOST_OE','F_WAIT','F_INT','F_IEO']:
    resistor('4k7',net,'GND')
for net in ['DATA_OE_N','IEO_OE_N']:resistor('1k','V5_HOST',net)
resistor('100k','CDONE','GND')
resistor('4k7','V3P3','LINK_OE_N')
resistor('10k','V5_HOST','H_PRIORITY')
for gp in [14,16]:resistor('4k7','L_GP'+str(gp),'GND')
# Clear HIGH during disconnected/startup; mark is masked until backend ready.
resistor('4k7','L_GP17','V3P3')
for net in ['P_GP22','SD_DAT1','SD_DAT2']:resistor('47k','P3V3',net)
for i,rail in enumerate(['V3P3']*5+['V5_HOST']*2+['V3P3']*5+['V3P3','V5_HOST','P3V3']+['V3P3']*3+['P3V3']):
    add('C'+str(i+1),'100nF',[(1,'1','passive',rail),(2,'2','passive','GND')],footprint='Capacitor_SMD:C_0805_2012Metric')
for i,rail in enumerate(['V3P3','P3V3','V5_MODULE'],20):
    add('C'+str(i),'10uF_10V',[(1,'1','passive',rail),(2,'2','passive','GND')],footprint='Capacitor_SMD:C_0805_2012Metric')
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
    instances.append(f'(symbol (lib_id "Pico1715:{sym}") (at {c["x"]} {c["y"]} 0) (unit 1) (in_bom yes) (on_board yes) (uuid {uid(ref)}) {props} (instances (project "carrier" (path "/{rootid}" (reference "{ref}") (unit 1)))))')
text=[]
for y,t in [(18,'Pico1715 combined carrier / draft A / NOT FOR PCB ORDER'),(28,'PASSIVE: mode switch grounds MODE_CTL and physically bypasses priority. Change mode only with all power off.'),(38,'External regulated 5V powers modules; X2 5V powers host-side drivers only. Never parallel 3V3 regulators.'),(48,'USB status/eject plus PIM724 onboard GP45 hold-to-eject / GP25 SAFE LED. Module/switch/host footprints pending.')]:
    text.append(f'(text {q(t)} (at 20 {y*0.7+4} 0) (effects (font (size 1.5 1.5)) (justify left)) (uuid {uid(t)}))')
s=f'(kicad_sch (version 20250114) (generator "pico1715") (uuid {rootid}) (paper "A0") (lib_symbols '+''.join(libs)+') '+''.join(instances+wires+labels+ncs+text)+')\n'
OUT.mkdir(exist_ok=True)
(OUT/'carrier.kicad_sch').write_text(s)
(OUT/'Pico1715.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "pico1715") '+''.join(libs).replace('"Pico1715:', '"')+')\n')
(OUT/'sym-lib-table').write_text('(sym_lib_table (lib (name "Pico1715") (type "KiCad") (uri "${KIPRJMOD}/Pico1715.kicad_sym") (options "") (descr "Original pin-explicit adapter symbols")))\n')
flibs=sorted({c['footprint'].split(':')[0] for c in parts if c['footprint']})
(OUT/'fp-lib-table').write_text('(fp_lib_table '+''.join('(lib (name "'+n+'") (type "KiCad") (uri "${KICAD10_FOOTPRINT_DIR}/'+n+'.pretty") (options "") (descr ""))' for n in flibs)+')\n')
(OUT/'connections.json').write_text(json.dumps({'schema':1,'revision':'carrier-A','physical_orientation_verified':False,'parts':parts},indent=2)+'\n')
(OUT/'bom.tsv').write_text('Reference\tValue\tFootprint\tDatasheet\n'+''.join('\t'.join((str(c[k]) or '-') for k in ['ref','value','footprint','datasheet'])+'\n' for c in parts))
(OUT/'carrier.kicad_pro').write_text('{}\n')
print(f'Generated {len(parts)} combined carrier parts')
