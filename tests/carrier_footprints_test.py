#!/usr/bin/env python3
"""Reject pin renumbering, mirrored module pads and overlapping access allocations."""
import copy
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit',ROOT/'tools/check_carrier_footprints.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
b=ROOT/'hardware/carrier';parts=json.loads((b/'connections.json').read_text())['parts'];inv=json.loads((b/'footprint-inventory.json').read_text());plan=json.loads((b/'placement-study.json').read_text())
m.check(parts,inv,plan)
for kind in ('legacy-switch','mirrored-pico','missing-detect','overlap','fake-release'):
 p=copy.deepcopy(parts);i=copy.deepcopy(inv);z=copy.deepcopy(plan)
 if kind=='legacy-switch':
  for pad in i['Pico1715_Carrier:JS202011JCQN_VendorPins']['pads']:
   if int(pad['number'])>=5:pad['number']=str(int(pad['number'])-1)
 elif kind=='mirrored-pico':
  for pad in i['Pico1715_Carrier:PIM724_SocketPair']['pads']:pad['x']=-pad['x']
 elif kind=='missing-detect':
  key='Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5';i[key]['pads']=[x for x in i[key]['pads'] if x['number']!='9']
 elif kind=='overlap':z['zones'][1]['x']=5
 else:z['fabrication_ready']=True
 try:m.check(p,i,z)
 except AssertionError:pass
 else:raise AssertionError(kind)
print('Footprint mutation controls PASS: five unsafe changes rejected')
