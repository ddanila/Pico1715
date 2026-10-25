#!/usr/bin/env python3
"""Check exported KiCad connectivity against the adapter contract and gating truth table."""
import argparse
import itertools
import json
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--netlist',type=Path,required=True)
a=p.parse_args()
r=ET.parse(a.netlist).getroot()
class PinNets(dict):
    def __getitem__(self,key):
        return super().__getitem__((key[0],str(key[1])))
    def get(self,key,default=None):
        return super().get((key[0],str(key[1])),default)
nets=PinNets()
for net in r.findall('nets/net'):
    for node in net.findall('node'):
        nets[(node.attrib['ref'],node.attrib['pin'])]=net.attrib['name'].lstrip('/')
m=json.loads((ROOT/'hardware/interface/connections.json').read_text())
for c in m['parts']:
    for number,name,kind,net in c['pins']:
        if net is not None:
            assert nets[(c['ref'],number)]==net,(c['ref'],number,net)
# Independent, datasheet-numbered directional and power assertions.
for u in ['U1','U2','U3']:
    assert nets[(u,1)]==nets[(u,20)]=='V3P3'
    assert nets[(u,19)]==nets[(u,10)]=='GND'
for i in range(8):
    assert nets[('U2',i+2)]==nets[('U4',18-i)]==f'H_D{i}'
    assert nets[('U2',18-i)]==f'F_DI{i}'
    assert nets[('U4',i+2)]==f'F_DO{i}'
assert nets[('U4',1)]=='GND' and nets[('U4',20)]=='V5_HOST'
assert nets[('U4',19)]==nets[('U9',2)]=='DATA_OE_N'
assert nets[('U5',1)]==nets[('U9',8)]=='IEO_OE_N'
assert nets[('U9',4)]=='H_WAIT_N' and nets[('U9',6)]=='H_INT_N'
for u,rail,pg in [('U10','V3P3','PG3'),('U11','V5_HOST','PG5')]:
    assert [nets[(u,i)] for i in (1,2,3)]==['GND',pg,rail]
x2=next(c for c in m['parts'] if c['ref']=='X2')
assert len(x2['pins'])==58
assert {p[0] for p in x2['pins']}=={f'{r}{i}' for r in 'AB' for i in range(1,30)}
# Independent contact assertions from service manual p44, not the generator JSON.
expected = {'A1':'GND','A2':'GND','B1':'GND','B2':'GND',
            'A29':'V5_HOST','B29':'V5_HOST','A8':'H_WR_N','B8':'H_RD_N',
            'A9':'H_MREQ_N','A20':'H_RESET_N','B23':'H_INT_N',
            'A24':'H_WAIT_N','B24':'H_IORQ_N','A26':'H_M1_N',
            'A10':'X2_A10_CONTACT','B10':'X2_B10_CONTACT'}
for i,pin in enumerate(['B7','A7','B6','A6','B5','A5','B4','A4']):
    expected[pin]=f'H_D{i}'
for i,pin in enumerate(['A19','B19','A18','B18','A17','B17','A16','B16']):
    expected[pin]=f'H_A{i}'
for pin,net in expected.items():
    assert nets[('X2',pin)]==net, (pin,net)
for row in 'AB':
    for i in range(1,30):
        pin=f'{row}{i}'
        if pin not in expected:
            # KiCad may export singleton unconnected nets.
            n=nets.get(('X2',pin))
            assert n is None or n.startswith('unconnected-'), (pin,n)
for i,net in enumerate(['X2_A10_CONTACT','X2_B10_CONTACT','H_IEI','H_IEO'],1):
    assert nets[('J11',i)]==net
for pin in ['A10','B10']:
    members={ref for (ref,num),net in nets.items() if net==nets[('X2',pin)]}
    assert members=={'X2','J11'}, (pin,members)
assert nets[('R15',1)]=='V5_HOST' and nets[('R15',2)]=='H_IEI'
# Evaluate the NETLIST gates, not a hardcoded copy of the gating formula.
qualifiers=['PG3','PG5','CDONE','BACKEND_READY','F_RESET_N','ARM']
requests=['F_HOST_OE','F_WAIT','F_INT']
for bits in itertools.product((0,1),repeat=9):
    v=dict(zip(qualifiers+requests,bits));v.update(GND=0,V3P3=1)
    for u in ['U6','U7','U8']:
        for x,y,z in [(1,2,3),(4,5,6),(9,10,8),(12,13,11)]:
            key=nets.get((u,z))
            if key is not None:
                value=v[nets[(u,x)]] & v[nets[(u,y)]]
                v[key]=1-value if u=='U8' else value
    armed=int(all(v[k] for k in qualifiers))
    assert v['ARMED']==armed
    for enable,request in zip(['DATA_EN_N','WAIT_EN_N','INT_EN_N'],requests):
        assert v[enable]==1-(armed & v[request])
    assert v['IEO_EN_N']==1-armed
print('interface PASS: exported pin connectivity, rail/direction contract, 58 X2 contacts and isolated IRQ patch, 512 gating combinations')
