#!/usr/bin/env python3
"""Check exported carrier connectivity, shared pin profiles and physical interlocks."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]

def check(tree,manifest,designs=None):
    nets={}
    for n in tree.findall('nets/net'):
        for p in n.findall('node'):nets[p.attrib['ref'],p.attrib['pin']]=n.attrib['name'].lstrip('/')
    def net(ref,pin):return nets.get((ref,str(pin)))
    def nc(ref,pin):return net(ref,pin) is None or net(ref,pin).startswith('unconnected-')
    def pins(ref,ps,expected):assert [net(ref,p) for p in ps]==expected,(ref,ps,expected)
    parts={p['ref']:p for p in manifest['parts']}
    for c in parts.values():
        for num,_,_,n in c['pins']:
            if n is not None:assert net(c['ref'],num)==n,(c['ref'],num,n)
    # Independent source contact contract, not generator-derived.
    expected={p:'GND' for p in ('A1','A2','B1','B2')}
    expected.update(A29='V5_HOST',B29='V5_HOST',A10='H_PRIORITY_OUT',B10='H_PRIORITY')
    for i,p in enumerate(['A19','B19','A18','B18','A17','B17','A16','B16','A14','B14','A13','B13','A12','B12','A11','B11']):expected[p]=f'H_A{i}'
    for i,p in enumerate(['B7','A7','B6','A6','B5','A5','B4','A4']):expected[p]=f'H_D{i}'
    for p,n in {'A9':'MREQ_N','B24':'IORQ_N','B8':'RD_N','A8':'WR_N','A26':'M1_N','A25':'RFSH_N','A21':'CLK','A20':'RESET_N','A24':'WAIT_N','B23':'INT_N','B20':'BUSRQ_N','A27':'BAO_N'}.items():expected[p]='H_'+n
    for row in 'AB':
        for i in range(1,30):
            p=f'{row}{i}'
            assert net('X2',p)==expected[p] if p in expected else nc('X2',p),(p,net('X2',p))
    inputs=[f'A{i}' for i in range(16)]+[f'D{i}' for i in range(8)]+['MREQ_N','IORQ_N','RD_N','WR_N','M1_N','RFSH_N','CLK','RESET_N','WAIT_N','INT_N','BUSRQ_N','BAO_N','PRIORITY']
    for i in range(40):
        ref=f'RX{1+i//8}';ch=i%8
        assert parts[ref]['value']=='SN74LVC541ADWR'
        pins(ref,[1,19,20,10],['GND','GND','V3P3','GND'])
        if i<37:pins(ref,[2+ch,18-ch],['H_'+inputs[i],'F_'+inputs[i]])
        else:assert net(ref,2+ch)=='GND' and nc(ref,18-ch)
    # Enumerate every permitted host-facing active pin. No hidden FPGA drive path.
    allowed={('U4',str(18-i)):f'H_D{i}' for i in range(8)}
    allowed.update({('U9','4'):'H_WAIT_N',('U9','6'):'H_INT_N'})
    for n in tree.findall('nets/net'):
        name=n.attrib['name'].lstrip('/')
        if not name.startswith('H_'):continue
        for p in n.findall('node'):
            if p.attrib.get('pintype') not in ('input','passive'):
                assert allowed.get((p.attrib['ref'],p.attrib['pin']))==name,(name,p.attrib)
    pins('U4',[1,19,20,10],['GND','DATA_OE_N','V5_HOST','GND'])
    for i in range(8):pins('U4',[2+i,18-i],[f'F_DO{i}',f'H_D{i}'])
    pins('U5',[1,2,3,4,5],['IEO_OE_N','F_IEO','GND','DRIVEN_IEO','V5_HOST'])
    pins('SW1',[1,2,3,5,6,7],['GND','MODE_CTL','V3P3','H_PRIORITY','H_PRIORITY_OUT','DRIVEN_IEO'])
    pins('U9',[1,2,3,4,5,6,9,8],['DATA_EN_N','DATA_OE_N','WAIT_EN_N','H_WAIT_N','INT_EN_N','H_INT_N','IEO_EN_N','IEO_OE_N'])
    for ref,rail,pg in [('U10','V3P3','PG3'),('U11','V5_HOST','PG5'),('U12','P3V3','PGP')]:
        pins(ref,[1,2,3],['GND',pg,rail])
    def resistor(value,a,b):
        assert any(c['value']==value and [net(c['ref'],i) for i in (1,2)]==[a,b] for c in parts.values()),(value,a,b)
    for rail,pg in [('V3P3','PG3'),('V5_HOST','PG5'),('P3V3','PGP')]:
        resistor('2k2',rail,pg);resistor('22k',pg,'GND')
    for signal in ('MODE_CTL','PERSONALITY_CTL','L_GP21','F_HOST_OE','F_WAIT','F_INT','F_IEO'):resistor('4k7',signal,'GND')
    resistor('100k','CDONE','GND')
    resistor('4k7','V3P3','LINK_OE_N')
    for n in ('DATA_OE_N','IEO_OE_N'):resistor('1k','V5_HOST',n)
    # Evaluate the actual exported gate graph across every qualifier/request combination.
    qualifiers=['PG3','PG5','PGP','CDONE','PERSONALITY_CTL','L_GP21','F_RESET_N','MODE_CTL']
    requests=['F_HOST_OE','F_WAIT','F_INT']
    for bits in itertools.product((0,1),repeat=len(qualifiers+requests)):
        v=dict(zip(qualifiers+requests,bits));v.update(GND=0,V3P3=1)
        for ref in ('U6','U7','U8','U13'):
            assert parts[ref]['value']==('SN74LVC08ADR' if ref in ('U6','U7') else 'SN74LVC00ADR')
            pins(ref,[7,14],['GND','V3P3'])
            for a,b,o in [(1,2,3),(4,5,6),(9,10,8),(12,13,11)]:
                if nc(ref,o):continue
                val=v[net(ref,a)] & v[net(ref,b)]
                v[net(ref,o)]=val if ref in ('U6','U7') else 1-val
        armed=int(all(v[q] for q in qualifiers))
        assert v['ARMED']==armed
        for output,req in zip(['DATA_EN_N','WAIT_EN_N','INT_EN_N'],requests):assert v[output]==1-(armed & v[req])
        assert v['IEO_EN_N']==1-armed
        assert v['LINK_OE_N']==1-(v['PG3'] & v['PGP'] & v['CDONE'])
    # Complete Pico mailbox including GP15 through power-off isolation.
    for gp in range(22):
        ref=f'ISO{1+gp//8}';ch=gp%8
        assert parts[ref]['value']=='SN74CB3Q3245PWR'
        pins(ref,[19,20,10],['LINK_OE_N','V3P3','GND'])
        pins(ref,[2+ch,18-ch],['F_RESET_N' if gp==15 else f'L_GP{gp}',f'P_GP{gp}'])
    for ref in ['ISO1','ISO2','ISO3']:assert nc(ref,1)
    for gp in (22,23):assert nc('ISO3',2+gp%8) and nc('ISO3',18-gp%8)
    physical={1:0,2:1,4:2,5:3,6:4,7:5,9:6,10:7,11:8,12:9,14:10,15:11,16:12,17:13,19:14,20:15,21:16,22:17,24:18,25:19,26:20,27:21,29:22,31:26,32:27,34:28}
    for p,gp in physical.items():assert net('J2',p)==f'P_GP{gp}'
    pins('J2',[36,39],['P3V3','P_VSYS']);assert nc('J2',40) and nc('J2',37)
    pins('J3',[2,3,4,5,6,7],['P_GP22','P_GP27','P3V3','P_GP26','GND','P_GP28'])
    assert nc('J3',9) and nc('J3',10) and net('J3','SH')=='GND'
    pins('D1',[1,2],['P_VSYS','V5_MODULE'])
    pins('EXT1',[1,3],['V5_MODULE','V3P3']);pins('J4',[1,2],['V5_MODULE','GND'])
    assert len({net('X2','A29'),net('J2',36),net('EXT1',3),net('J4',1)})==4
    pins('J1',[5],['CDONE'])
    for h in ('EXT1','EXT2','EXT3'):
        pins(h,[2,4,8],['GND']*3)
        assert nc(h,5) and nc(h,6)
        if h!='EXT1':assert nc(h,1) and nc(h,3)
    bindings={}
    for mode in ('controller','analyzer'):
        prefix=ROOT/f'hardware/boards/hx8k-carrier-{mode}'
        rows=json.loads(prefix.with_suffix('.json').read_text())['signals']
        pcf=dict(re.findall(r'^set_io (\S+) (\S+)$',prefix.with_suffix('.pcf').read_text(),re.M))
        assert len(pcf)==len(rows)==len(set(pcf.values()))
        for r in rows:
            assert pcf[r['signal']]==r['package_pin']
            if not r['header']:continue
            assert net(*r['header'])==r['adapter_net'],r
            previous=bindings.setdefault(r['package_pin'],r['adapter_net'])
            assert previous==r['adapter_net'],r
        if mode=='analyzer':
            for i,n in enumerate(inputs):assert next(r for r in rows if r['signal']==f'bus_sample[{i}]')['adapter_net']=='F_'+n
        if designs:
            ports=designs[mode]['modules']['carrier_'+mode]['ports']
            assert ports['personality_controller']['bits']==['1' if mode=='controller' else '0']
            if mode=='analyzer':
                assert ports['bus_sample']['direction']=='input'
                assert {p for p,v in ports.items() if v['direction']=='output'}=={'pico_data','pico_index','pico_request','personality_controller'}
    return {'qualification':'desk only; physical, analog and power-transition qualification pending',
            'gating_combinations':2048,'host_receiver_channels':37,'pico_isolation_channels':22,
            'shared_pin_profiles_verified':True,'synthesized_ports_checked':bool(designs)}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--netlist',type=Path,required=True)
    p.add_argument('--controller-design',type=Path);p.add_argument('--analyzer-design',type=Path);p.add_argument('--out',type=Path)
    a=p.parse_args()
    if bool(a.controller_design)!=bool(a.analyzer_design):p.error('provide both synthesized designs')
    designs={m:json.loads(getattr(a,m+'_design').read_text()) for m in ('controller','analyzer')} if a.controller_design else None
    report=check(ET.parse(a.netlist).getroot(),json.loads((ROOT/'hardware/carrier/connections.json').read_text()),designs)
    report['netlist_sha256']=hashlib.sha256(a.netlist.read_bytes()).hexdigest()
    if a.out:a.out.write_text(json.dumps(report,indent=2)+'\n')
    print('carrier PASS: 58 contacts, 37 receivers, 22 isolated GPIOs, 2048 gating cases, compatible pin profiles')
if __name__=='__main__':main()
