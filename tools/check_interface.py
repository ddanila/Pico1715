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
nets={}
for net in r.findall('nets/net'):
    for node in net.findall('node'):
        nets[(node.attrib['ref'],int(node.attrib['pin']))]=net.attrib['name'].lstrip('/')
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
print('interface PASS: exported pin connectivity, rail/direction contract, 512 gating combinations')
