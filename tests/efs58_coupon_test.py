#!/usr/bin/env python3
"""Portable checks of released mesh topology, stack, connectivity and freshness."""
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from check_carrier_pcb import parse, children, one
BASE=ROOT/'hardware/efs58-coupon'
P=json.loads((BASE/'parameters.json').read_text())

def connectivity(board):
    pads={}
    for fp in children(board,'footprint'):
        ref=next(x[2] for x in children(fp,'property') if x[1]=='Reference')
        if ref.startswith('H'): continue
        pad=one(fp,'pad'); net=one(pad,'net')[1]
        pos=tuple(map(float,one(fp,'at')[1:3])); pads[ref]=(net,pos)
    assert set(pads)=={f'{prefix}{i}' for prefix in ['J','TP'] for i in range(1,5)}
    graph=defaultdict(lambda:defaultdict(set))
    for tr in children(board,'segment'):
        net=one(tr,'net')[1]; a=tuple(map(float,one(tr,'start')[1:])); z=tuple(map(float,one(tr,'end')[1:]))
        graph[net][a].add(z); graph[net][z].add(a)
    assert len({pads[f'J{i}'][0] for i in range(1,5)})==4
    for i,(x,y) in enumerate(P['centres'],1):
        net,start=pads[f'J{i}']; target_net,target=pads[f'TP{i}']
        assert start==(P['pcb_origin'][0]+x,P['pcb_origin'][1]+y)
        assert net==target_net
        seen=set(); todo=[start]
        while todo:
            a=todo.pop()
            if a in seen: continue
            seen.add(a); todo.extend(graph[net][a]-seen)
        assert target in seen and len(seen)==len(graph[net])

class CouponTests(unittest.TestCase):
    def test_evidence_current(self):
        r=json.loads((BASE/'validation.json').read_text())
        self.assertEqual(r['physical_fit'],'not tested')
        for name,sha in r['sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),sha,name)
        for name,sha in json.loads((BASE/'cad-inputs.json').read_text()).items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),sha,name)

    def test_meshes(self):
        report=json.loads((BASE/'cad-checks.json').read_text())
        for name,r in report.items():
            raw=(BASE/(name+'.stl')).read_bytes(); n=struct.unpack_from('<I',raw,80)[0]
            self.assertEqual(len(raw),84+50*n); self.assertEqual(n,r['triangles'])
            edges=Counter(); vertices=[]; vol=0
            for i in range(n):
                vals=struct.unpack_from('<12fH',raw,84+50*i)
                pts=[tuple(round(v,5) for v in vals[j:j+3]) for j in (3,6,9)]
                vertices.extend(pts)
                for a,b in zip(pts,pts[1:]+pts[:1]): edges[tuple(sorted((a,b)))]+=1
                a,b,c=pts
                vol+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
            self.assertTrue(all(v==2 for v in edges.values()),name)
            self.assertAlmostEqual(min(v[2] for v in vertices),0,places=5)
            for axis,size in enumerate(r['bounds_mm']):
                self.assertAlmostEqual(max(v[axis] for v in vertices)-min(v[axis] for v in vertices),size,places=4)
            self.assertAlmostEqual(abs(vol),r['volume_mm3'],delta=0.1)

    def test_stack(self):
        c=P['contact']; self.assertFalse(P['host_qualified']); self.assertIsNone(c['efs_blade_compatible'])
        self.assertEqual(P['pitch'],2.5)
        shortest=P['front_thickness']+c['body_length']+c['tail_length']-2*c['length_tolerance']
        self.assertGreater(shortest-P['pcb_front_z']-P['pcb_thickness'],0.5)
        self.assertGreater(P['body_back_z']-P['front_thickness']-c['body_length']-c['length_tolerance'],0)
        self.assertGreater(P['flange_pocket_depth']-c['flange_height']-c['length_tolerance'],0)
        self.assertGreater(P['pitch']-c['flange_diameter']-max(P['diametral_clearance_variants']),0.3)
        self.assertGreater(c['flange_diameter']-c['diameter_tolerance']-P['entry_diameter'],0.5)

    def test_routes(self): connectivity(parse((BASE/'coupon.kicad_pcb').read_text()))

    def test_route_faults_rejected(self):
        board=parse((BASE/'coupon.kicad_pcb').read_text())
        broken=copy.deepcopy(board); broken.remove(children(broken,'segment')[0])
        with self.assertRaises(AssertionError): connectivity(broken)
        wrong=copy.deepcopy(board)
        fps=children(wrong,'footprint')
        fp=next(fp for fp in fps if children(one(fp,'pad'),'net'))
        one(one(fp,'pad'),'net')[1]='999'
        with self.assertRaises(AssertionError): connectivity(wrong)

if __name__=='__main__': unittest.main()
