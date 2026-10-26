#!/usr/bin/env python3
"""Mutation controls: coordinated manifest/netlist edits must still be rejected."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('carrier',ROOT/'tools/check_carrier.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
tree=ET.parse(sys.argv[1]).getroot()
manifest=json.loads((ROOT/'hardware/carrier/connections.json').read_text())
mod.check(tree,manifest)
mutations=[('SW1','1','V3P3'),('SW1','5','DRIVEN_IEO'),('U7','13','V3P3'),
 ('U4','19','GND'),('U9','3','GND'),('ISO1','19','GND'),('ISO3','17','L_GP17'),
 ('J2','36','V3P3'),('EXT2','15','F_DO0'),('X2','A20','H_CLK'),('RX1','2','H_D0'),
 ('U12','3','V3P3'),('D1','2','P_VSYS'),('R5','1','V3P3')]
for ref,pin,wrong in mutations:
    t=copy.deepcopy(tree);m=copy.deepcopy(manifest);found=None
    for n in t.findall('nets/net'):
        for node in list(n.findall('node')):
            if (node.attrib['ref'],node.attrib['pin'])==(ref,pin):found=node;n.remove(node)
    assert found is not None
    target=next(n for n in t.findall('nets/net') if n.attrib['name'].lstrip('/')==wrong);target.append(found)
    for c in m['parts']:
        if c['ref']==ref:
            for p in c['pins']:
                if str(p[0])==pin:p[3]=wrong
    try:mod.check(t,m)
    except (AssertionError,KeyError):pass
    else:raise AssertionError(('mutation escaped',ref,pin,wrong))
print(f'carrier mutation controls PASS: {len(mutations)} unsafe coordinated edits rejected')
