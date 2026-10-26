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
for kind in ('wrong-net','missing-pad','missing-part','wrong-path','lost-keepout','false-release'):
 d=copy.deepcopy(board);p=copy.deepcopy(plan)
 fp=m.children(d,'footprint')[0]
 if kind=='wrong-net':m.one(m.children(fp,'pad')[0],'net')[-1]='/WRONG'
 elif kind=='missing-pad':fp.remove(m.children(fp,'pad')[0])
 elif kind=='missing-part':d.remove(fp)
 elif kind=='wrong-path':m.one(fp,'path')[1]='/wrong'
 elif kind=='lost-keepout':d.remove(m.one(d,'zone'))
 else:p['fabrication_ready']=True
 try:m.check(d,parts,xml,p)
 except AssertionError:pass
 else:raise AssertionError(kind)
print('PCB mutation controls PASS: six unsafe changes rejected')
