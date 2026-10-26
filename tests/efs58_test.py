#!/usr/bin/env python3
"""Protect the independently reviewed TGL reference pattern and its release hold."""
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from check_carrier_pcb import parse, children, one
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'hardware/carrier/efs58'

def check(f,g):
    ps=children(f,'pad');electrical=[p for p in ps if p[1]]
    assert len(electrical)==58
    by={p[1]:p for p in electrical}
    assert set(by)=={f'{row}{i}' for row in 'AB' for i in range(1,30)}
    for row,y in [('A',0),('B',5)]:
        for i in range(1,30):
            p=by[f'{row}{i}']
            assert tuple(map(float,one(p,'at')[1:]))==((i-1)*2.5,y)
            assert p[2]=='thru_hole' and float(one(p,'drill')[1])==1.0
            assert tuple(map(float,one(p,'size')[1:]))==(1.8,1.8)
    ms=[p for p in ps if not p[1]]
    assert len(ms)==2
    assert {tuple(map(float,one(p,'at')[1:])) for p in ms}=={(-7.5,-5),(77.5,-5)}
    assert all(p[2]=='np_thru_hole' and float(one(p,'drill')[1])==2.7 for p in ms)
    line=one(f,'fp_line')
    assert tuple(map(float,one(line,'start')[1:]))==(-11,-6.5)
    assert tuple(map(float,one(line,'end')[1:]))==(81,-6.5)
    assert g['board_edge_y']==-6.5 and not g['fabrication_ready']
    assert g['mounting_form']==7 and g['mounting_centres']==85
    assert g['pads']==[dict(number=p[1],x=float(one(p,'at')[1]),y=float(one(p,'at')[2])) for p in electrical]
    parts=json.loads((ROOT/'hardware/carrier/connections.json').read_text())['parts']
    assert not next(p for p in parts if p['ref']=='X2')['footprint'], 'Promoting reference requires reviewing this hold'

class ReferenceTest(unittest.TestCase):
    def setUp(self):
        self.f=parse((BASE/'EFS58_202-58_Form7_Reference.kicad_mod').read_text())
        self.g=json.loads((BASE/'geometry.json').read_text())
    def test_reference(self): check(self.f,self.g)
    def test_mutations(self):
        for kind in ['pitch','row_spacing','mirror_numbers','swap_rows','mount_form','edge_datum','release']:
            with self.subTest(kind=kind):
                f=copy.deepcopy(self.f);g=copy.deepcopy(self.g)
                ps=children(f,'pad')
                if kind=='pitch': one(ps[28],'at')[1]='71.12'
                if kind=='row_spacing': one(ps[29],'at')[2]='2.5'
                if kind=='mirror_numbers': ps[0][1],ps[28][1]=ps[28][1],ps[0][1]
                if kind=='swap_rows': ps[0][1],ps[29][1]=ps[29][1],ps[0][1]
                if kind=='mount_form': one(ps[-1],'at')[1]='76.25'
                if kind=='edge_datum': one(one(f,'fp_line'),'start')[2]='-11.5'
                if kind=='release': g['fabrication_ready']=True
                with self.assertRaises(AssertionError): check(f,g)

if __name__=='__main__': unittest.main()
