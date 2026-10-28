#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Derive combined pin bindings from the audited carrier receiver/controller maps."""
import argparse
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'hardware/boards'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
analyzer=json.loads((root/'hx8k-carrier-analyzer.json').read_text())
controller=json.loads((root/'hx8k-carrier-controller.json').read_text())
rows=[r for r in analyzer['signals'] if r['signal'].startswith('bus_sample[')]
used={r['package_pin'] for r in rows}
rows += [r for r in controller['signals'] if r['package_pin'] not in used]
assert len({r['package_pin'] for r in rows})==len(rows)
analyzer['signals']=rows;analyzer['personality']='combined experimental'
files={'hx8k-carrier-combined.json':json.dumps(analyzer,indent=2)+'\n',
       'hx8k-carrier-combined.pcf':'# Carrier combined experimental; host electrical qualification pending\n'+''.join('set_io '+r['signal']+' '+r['package_pin']+'\n' for r in rows)}
for name,text in files.items():
 if a.check:assert (root/name).read_text()==text,name
 else:(root/name).write_text(text)
