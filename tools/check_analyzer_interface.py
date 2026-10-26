#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent connectivity checks for the receive-only analyzer adapter."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--netlist',type=Path,required=True)
p.add_argument('--design',type=Path,help='Yosys analyzer synthesis JSON')
p.add_argument('--out',type=Path)
a=p.parse_args()
r=ET.parse(a.netlist).getroot()
nets={(n.attrib['ref'],n.attrib['pin']):net.attrib['name'].lstrip('/')
      for net in r.findall('nets/net') for n in net.findall('node')}
def net(ref,pin):return nets.get((ref,str(pin)))
m=json.loads((ROOT/'hardware/analyzer-interface/connections.json').read_text())
for part in m['parts']:
    for pin,name,typ,expected in part['pins']:
        actual=net(part['ref'],pin)
        assert actual==expected if expected is not None else actual is None or actual.startswith('unconnected-'),(part['ref'],pin,actual,expected)
expected={pin:'GND' for pin in ('A1','A2','B1','B2')}
expected.update(A29='V5_HOST',B29='V5_HOST',A10='H_PRIORITY_OUT',B10='H_PRIORITY')
for i,pin in enumerate(['A19','B19','A18','B18','A17','B17','A16','B16','A14','B14','A13','B13','A12','B12','A11','B11']):expected[pin]=f'H_A{i}'
for i,pin in enumerate(['B7','A7','B6','A6','B5','A5','B4','A4']):expected[pin]=f'H_D{i}'
for pin,name in {'A9':'MREQ_N','B24':'IORQ_N','B8':'RD_N','A8':'WR_N','A26':'M1_N','A25':'RFSH_N','A21':'CLK','A20':'RESET_N','A24':'WAIT_N','B23':'INT_N','B20':'BUSRQ_N','A27':'BAO_N'}.items():expected[pin]='H_'+name
for row in 'AB':
    for i in range(1,30):
        pin=f'{row}{i}';actual=net('X2',pin)
        assert actual==expected[pin] if pin in expected else actual is None or actual.startswith('unconnected-'),(pin,actual)
inputs=[f'A{i}' for i in range(16)]+[f'D{i}' for i in range(8)]+['MREQ_N','IORQ_N','RD_N','WR_N','M1_N','RFSH_N','CLK','RESET_N','WAIT_N','INT_N','BUSRQ_N','BAO_N','PRIORITY']
for i in range(40):
    u=f'U{1+i//8}';channel=i%8
    assert net(u,1)==net(u,19)==net(u,10)=='GND'
    assert net(u,20)=='V3P3'
    if i<len(inputs):
        assert net(u,2+channel)=='H_'+inputs[i]
        assert net(u,18-channel)=='F_'+inputs[i]
    else:
        assert net(u,2+channel)=='GND'
        assert net(u,18-channel) is None or net(u,18-channel).startswith('unconnected-')
# Check direction from component pin types in the exported netlist, not just labels.
for bus in {v for v in expected.values() if v.startswith('H_')}:
    attached=[n for n in r.findall('nets/net') if n.attrib['name'].lstrip('/')==bus][0]
    for n in attached.findall('node'):
        assert n.attrib.get('pintype') in ('input','passive'),(bus,n.attrib)
# Hard bypass does not depend on power, FPGA configuration, software or ARM state.
assert net('R1',1)=='H_PRIORITY' and net('R1',2)=='H_PRIORITY_OUT'
assert next(c['value'] for c in m['parts'] if c['ref']=='R1')=='0R'
assert net('R2',1)=='V5_HOST' and net('R2',2)=='H_PRIORITY'
assert [net('U6',i) for i in (1,2,3)]==['GND','CARD_PG','V3P3']
for ref,signal,rail in [('R5','CAPTURE_CLEAR','V3P3'),('R6','CAPTURE_ENABLE','GND'),('R7','LINK_SYNC_N','GND'),('R8','PICO_ACK','GND')]:
    assert [net(ref,i) for i in (1,2)]==[signal,rail]
    assert next(c['value'] for c in m['parts'] if c['ref']==ref)=='4k7'
pins=json.loads((ROOT/'hardware/boards/hx8k-analyzer-pins.json').read_text())['signals']
pcf=dict(re.findall(r'^set_io (\S+) (\S+)$',(ROOT/'hardware/boards/hx8k-analyzer.pcf').read_text(),re.M))
assert len(pcf)==len(pins)==57 and len(set(pcf.values()))==57
for pin in pins:
    assert pcf[pin['signal']]==pin['package_pin']
    if pin['header']:assert net(*pin['header'])==pin['adapter_net'],pin
    if pin['pico_gpio'] is not None:assert net('J1','GP'+str(pin['pico_gpio']))==pin['adapter_net']
for i,name in enumerate(inputs):
    assert next(p for p in pins if p['signal']==f'bus_sample[{i}]')['adapter_net']=='F_'+name
for header in ('EXT1','EXT2','EXT3'):
    for ground in (2,4,8):assert net(header,ground)=='GND'
if a.design:
    ports=json.loads(a.design.read_text())['modules']['analyzer_hx8k']['ports']
    assert ports['bus_sample']['direction']=='input' and len(ports['bus_sample']['bits'])==37
    assert {n for n,v in ports.items() if v['direction']=='output'}=={'pico_data','pico_index','pico_request'}
    assert sum(len(v['bits']) for v in ports.values())==57
report={'qualification':'desk connectivity only; no analog or physical qualification',
        'checks':['58 X2 contacts including 16 address bits','37 input-only receiver channels',
                  'fixed physical priority bypass','power/default pin contract','57 PCF/header/Pico bindings'],
        'netlist_sha256':hashlib.sha256(a.netlist.read_bytes()).hexdigest(),
        'sources':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in
                   [ROOT/'tools/check_analyzer_interface.py',ROOT/'tools/generate_analyzer_interface.py',
                    ROOT/'hardware/boards/hx8k-analyzer-pins.json',ROOT/'hardware/boards/hx8k-analyzer.pcf',
                    ROOT/'hardware/analyzer-interface/connections.json',ROOT/'hardware/analyzer-interface/analyzer-interface.kicad_sch']}}
if a.design:report['checks'].append('synthesized board top exposes no host-output ports')
if a.out:a.out.write_text(json.dumps(report,indent=2)+'\n')
print('analyzer interface PASS: X2 contacts, input-only topology, chain bypass, defaults, FPGA/Pico harness')
