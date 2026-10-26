#!/usr/bin/env python3
"""Validate our pin choices against the external manufacturer's Rev B1 netlist."""
import argparse
import hashlib
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--netlist',type=Path,required=True);p.add_argument('--mapping',type=Path,default=ROOT/'hardware/boards/hx8k-pins.json');a=p.parse_args()
s=a.netlist.read_text();nets={}
for net in re.split(r'\(net \(code \d+\)',s)[1:]:
 name=re.search(r'\(name ([^\n]+)\)',net).group(1)
 nodes=re.findall(r'\(node \(ref ([^)]+)\) \(pin ([^)]+)\)',net)
 nets[name]=nodes
mapping=json.loads(a.mapping.read_text())
assert hashlib.sha256(a.netlist.read_bytes()).hexdigest()==mapping['netlist_sha256']
used=set()
for row in mapping['signals']:
 assert row['package_pin'] not in used;used.add(row['package_pin'])
 nodes=nets[row['board_net']]
 assert ('U4',row['package_pin']) in nodes
 if row['header']:
  assert tuple(row['header']) in nodes
  assert all(ref=='U4' or ref.startswith('EXT') for ref,pin in nodes),row
if mapping.get('personality','').startswith('passive analyzer'):
 for header in ('EXT1','EXT2','EXT3'):
  for ground in ('2','4','8'):assert (header,ground) in nets['GND']
print(f'{len(used)} package pins match the pinned Rev B1 netlist; header signals unshared')
