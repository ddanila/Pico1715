#!/usr/bin/env python3
"""Pin/pad coverage and allocation checks; no DRC or physical qualification claim."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'hardware/carrier'
def pads(text):
    result=[]
    for m in re.finditer(r'\(pad\s+"([^\"]*)"\s+\S+\s+\S+\s*\(at\s+([-\d.]+)\s+([-\d.]+)',text):
        if m[1]:result.append({'number':m[1],'x':float(m[2]),'y':float(m[3])})
    return result

def check(parts,inventory,plan):
    assigned=0;unresolved=[]
    for c in parts:
        fp=c['footprint']
        if not fp:unresolved.append(c['ref']);continue
        assigned+=1
        physical={p['number'] for p in inventory[fp]['pads']}
        schematic={str(p[0]) for p in c['pins']}
        assert schematic==physical,(c['ref'],schematic-physical,physical-schematic)
    assert set(unresolved)=={'X2'},unresolved
    c={p['ref']:p for p in parts}
    sw=inventory[c['SW1']['footprint']]['pads'];by={p['number']:(p['x'],p['y']) for p in sw}
    assert by=={'1':(-2.5,1.2),'2':(0,1.2),'3':(2.5,1.2),'5':(-2.5,-1.2),'6':(0,-1.2),'7':(2.5,-1.2)}
    assert {str(p[0]):p[3] for p in c['SW1']['pins']}=={'1':'GND','2':'MODE_CTL','3':'V3P3','5':'H_PRIORITY','6':'H_PRIORITY_OUT','7':'DRIVEN_IEO'}
    pp={p['number']:(p['x'],p['y']) for p in inventory[c['J2']['footprint']]['pads']}
    for i in range(1,21):
        assert pp[str(i)]==(-8.89,round(-24.13+(i-1)*2.54,3))
        assert pp[str(41-i)]==(8.89,round(-24.13+(i-1)*2.54,3))
    sd=c['J3'];sn={str(p[0]):p[3] for p in sd['pins']}
    assert sn['9'] is None and sn['10'] is None and sn['SH']=='GND'
    assert sum(p['number']=='SH' for p in inventory[sd['footprint']]['pads'])==4
    assert not plan['fabrication_ready'] and plan['hx8k_header_contact_pitch']==1.27
    assert plan['hx8k_smd_tail_row_spacing']==4.064
    for a,b in itertools.combinations(plan['zones'],2):
        assert a['x']+a['w']<=b['x'] or b['x']+b['w']<=a['x'] or a['y']+a['h']<=b['y'] or b['y']+b['h']<=a['y'],(a['name'],b['name'])
    return {'assigned_parts':assigned,'unresolved_parts':unresolved,'allocation_zone_overlaps':0,'fabrication_ready':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library-root',type=Path,help='also verify against installed KiCad footprint files')
    p.add_argument('--refresh',action='store_true',help='record pad facts/hashes from installed libraries')
    a=p.parse_args()
    parts=json.loads((BASE/'connections.json').read_text())['parts'];path=BASE/'footprint-inventory.json'
    inv=json.loads(path.read_text()) if path.exists() else {}
    if a.refresh and not a.library_root:p.error('--refresh requires --library-root')
    if a.library_root:
        actual={}
        for name in sorted({c['footprint'] for c in parts if c['footprint']}):
            lib,fp=name.split(':');base=BASE if lib=='Pico1715_Carrier' else a.library_root
            f=base/(lib+'.pretty')/(fp+'.kicad_mod');data=f.read_bytes()
            actual[name]={'sha256':hashlib.sha256(data).hexdigest(),'pads':pads(data.decode())}
        if a.refresh:inv=actual;path.write_text(json.dumps(inv,indent=2)+'\n')
        else:assert actual==inv,'Library geometry changed; review before refreshing the inventory'
    # Project-owned geometry is always checked, also on portable CI.
    for name,item in inv.items():
        if name.startswith('Pico1715_Carrier:'):
            fp=BASE/'Pico1715_Carrier.pretty'/(name.split(':')[1]+'.kicad_mod')
            assert hashlib.sha256(fp.read_bytes()).hexdigest()==item['sha256']
    report=check(parts,inv,json.loads((BASE/'placement-study.json').read_text()))
    print(json.dumps(report))
if __name__=='__main__':main()
