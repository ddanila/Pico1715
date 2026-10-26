#!/usr/bin/env python3
"""Reject disconnected/misassigned pads and missing review-board safeguards."""
import copy
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pcb',ROOT/'tools/check_carrier_pcb.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
b=ROOT/'hardware/carrier';board=m.parse((b/'carrier.kicad_pcb').read_text());parts=json.loads((b/'connections.json').read_text())['parts'];xml=ET.parse(b/'carrier.net.xml');plan=json.loads((b/'pcb-placement.json').read_text())
m.check(board,parts,xml,plan)
cases=('wrong-net','missing-pad','missing-part','wrong-path','lost-keepout','false-release',
       'lost-track','wrong-track-net','lost-via','wrong-ground-plane','lost-back-hold','far-bypass')
for kind in cases:
 d=copy.deepcopy(board);p=copy.deepcopy(plan)
 fp=m.children(d,'footprint')[0]
 if kind=='wrong-net':m.one(m.children(fp,'pad')[0],'net')[-1]='/WRONG'
 elif kind=='missing-pad':fp.remove(m.children(fp,'pad')[0])
 elif kind=='missing-part':d.remove(fp)
 elif kind=='wrong-path':m.one(fp,'path')[1]='/wrong'
 elif kind=='lost-keepout':d.remove(next(z for z in m.children(d,'zone') if m.children(z,'keepout')))
 elif kind=='false-release':p['fabrication_ready']=True
 elif kind=='lost-track':d.remove(m.children(d,'segment')[0])
 elif kind=='wrong-track-net':m.one(next(t for t in m.children(d,'segment') if m.one(t,'net')[-1]!='/GND'),'net')[-1]='/GND'
 elif kind=='lost-via':d.remove(m.children(d,'via')[0])
 elif kind=='wrong-ground-plane':m.one(next(z for z in m.children(d,'zone') if m.children(z,'net')),'net')[-1]='/V3P3'
 elif kind=='lost-back-hold':m.one(next(z for z in m.children(d,'zone') if m.children(z,'keepout')),'layers').remove('B.Cu')
 elif kind=='far-bypass':
  c=next(f for f in m.children(d,'footprint') if any(q[1:3]==['Reference','C1'] for q in m.children(f,'property')))
  m.one(c,'at')[1]=str(float(m.one(c,'at')[1])+10)
  p['placements']['C1'][0]+=10
 try:m.check(d,parts,xml,p)
 except AssertionError:pass
 else:raise AssertionError(kind)
print(f'PCB mutation controls PASS: {len(cases)} unsafe changes rejected')
