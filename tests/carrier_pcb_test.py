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
       'lost-track','wrong-track-net','lost-via','wrong-ground-plane','lost-back-hold','far-bypass','lost-supervisor-supply','lost-supervisor-sense',
       'lost-supervisor-divider','lost-resistor-return',
       'lost-fpga-rail','lost-pico-rail','lost-host-rail','lost-control','lost-bridge-via',
       'lost-pg3','lost-pg5','lost-pgp','lost-qualified','lost-armed-branch','lost-signal-via',
       'lost-iso1-enable','lost-iso2-enable','lost-iso3-enable','lost-disable-pullup',
       'lost-link-input','lost-link-header-via','lost-cdone-input','lost-personality-input',
       'lost-address','lost-data','lost-backend','lost-reset-path','lost-mode-path',
       'lost-priority','lost-power-good','lost-priority-via','lost-front-plane')
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
 elif kind in ['lost-bridge-via','lost-signal-via','lost-link-header-via']:
  tag={'lost-bridge-via':'host5/logic-crossing/a',
       'lost-signal-via':'interlock/pgp-input-crossing/a',
       'lost-link-header-via':'link-ok/header'}[kind]
  v=next(v for v in p['vias'] if v['tag']==tag)
  actual=next(t for t in m.children(d,'via') if list(map(float,m.one(t,'at')[1:]))==v['at'])
  d.remove(actual);p['vias'].remove(v)
 elif kind in ['lost-address','lost-data','lost-backend','lost-reset-path','lost-mode-path','lost-priority','lost-power-good']:
  net={'lost-address':'F_A0','lost-data':'F_DO3','lost-backend':'L_GP12',
       'lost-reset-path':'F_RESET_N','lost-mode-path':'MODE_CTL',
       'lost-priority':'H_PRIORITY','lost-power-good':'POWER_GOOD'}[kind]
  # Keep manifest and PCB consistent while opening a completed signal net.
  p['routes']=[t for t in p['routes'] if t['net']!=net]
  d[:]=[t for t in d if not(isinstance(t,list) and t and t[0]=='segment' and m.one(t,'net')[-1]=='/'+net)]
 elif kind=='lost-priority-via':
  v=next(v for v in p['vias'] if v['net']=='H_PRIORITY' and v['at']==[154.8,116.1])
  actual=next(t for t in m.children(d,'via') if list(map(float,m.one(t,'at')[1:]))==v['at'])
  d.remove(actual);p['vias'].remove(v)
 elif kind=='lost-front-plane':
  d.remove(next(z for z in m.children(d,'zone') if not m.children(z,'keepout') and m.one(z,'layer')[1]=='F.Cu'))
 elif kind.startswith('lost-supervisor-') or kind in ['lost-resistor-return','lost-fpga-rail','lost-pico-rail','lost-host-rail','lost-control','lost-pg3','lost-pg5','lost-pgp','lost-qualified','lost-armed-branch','lost-iso1-enable','lost-iso2-enable','lost-iso3-enable','lost-disable-pullup','lost-link-input','lost-cdone-input','lost-personality-input']:
  tag={'lost-supervisor-supply':'U10/pullup-supply',
       'lost-supervisor-sense':'U11/sense',
       'lost-supervisor-divider':'U12/divider',
       'lost-resistor-return':'R19/ground',
       'lost-fpga-rail':'3v3/C8','lost-pico-rail':'p3v3/probe-pad',
       'lost-host-rail':'host5/U5','lost-control':'control/mode-pulldown',
       'lost-pg3':'interlock/pg3-input','lost-pg5':'interlock/pg5-source',
       'lost-pgp':'interlock/pgp-source','lost-qualified':'interlock/qualified',
       'lost-armed-branch':'interlock/armed-12',
       'lost-iso1-enable':'link-enable/north','lost-iso2-enable':'link-enable/ISO2',
       'lost-iso3-enable':'link-enable/ISO3','lost-disable-pullup':'link-enable/south',
       'lost-link-input':'link-ok/gate-b','lost-cdone-input':'cdone/input',
       'lost-personality-input':'personality/input'}[kind]
  route=next(t for t in p['routes'] if t['tag']==tag)
  # Remove from both copper and inventory: connectivity must catch this even
  # when generator and manifest agree on the same missing connection.
  segment=next(t for t in m.children(d,'segment')
               if m.one(t,'net')[-1]=='/'+route['net']
               and list(map(float,m.one(t,'start')[1:]))==route['start']
               and list(map(float,m.one(t,'end')[1:]))==route['end'])
  d.remove(segment);p['routes'].remove(route)
 try:m.check(d,parts,xml,p)
 except AssertionError:pass
 else:raise AssertionError(kind)
print(f'PCB mutation controls PASS: {len(cases)} unsafe changes rejected')

# A held socket must not hide ordinary airwires or geometric violations.
held=next(f for f in m.children(board,'footprint') if any(q[1:3]==['Reference','J3'] for q in m.children(f,'property')))
held_id=m.one(m.children(held,'pad')[0],'uuid')[1]
allowed={'violations':[],'unconnected_items':[{'items':[{'uuid':held_id},{'uuid':'ordinary'}]}]}
assert m.check_drc(board,allowed)['drc_nonheld_unconnected_items']==0
for drc in [
 {'violations':[{'type':'clearance'}],'unconnected_items':[]},
 {'violations':[],'unconnected_items':[{'items':[{'uuid':'ground-zone-a'},{'uuid':'ground-zone-b'}]}]},
 {'violations':[],'unconnected_items':[{'items':[{'uuid':'signal-pad'},{'uuid':'signal-track'}]}]},
]:
 try:m.check_drc(board,drc)
 except AssertionError:pass
 else:raise AssertionError('DRC accepted non-held fault')
print('DRC hold controls PASS: held socket accepted; 3 unrelated failures rejected')
