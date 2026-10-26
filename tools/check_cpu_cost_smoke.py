#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and qualify the ROM-free Z80/firmware cost scheduler regression."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from check_classic import digest, require

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--dac', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
dac,out = a.dac.resolve(),a.out.resolve()
pin = json.loads((ROOT/'docs/sources.json').read_text())['dac']['commit']
require(subprocess.check_output(['git','-C',str(dac),'rev-parse','HEAD'],text=True).strip()==pin,'unqualified DAC revision')
for command in (['diff','--quiet'],['diff','--cached','--quiet']):
    subprocess.run(['git','-C',str(dac),*command],check=True)
out.mkdir(parents=True,exist_ok=False)
names = ('tests/stress/combined.json','tests/stress/overload.json','tools/check_cpu_cost_smoke.py','tests/cpu_cost_smoke.py','tools/firmware_costs.py',
         'tools/classic_probe.c','tools/build_cosim.py','tools/cosim/bridge.h',
         'tools/firmware_host/bridge.cpp','tools/firmware_host/host_hal.c','tools/firmware_host/host_hal.h',
         'firmware/service.c','firmware/service.h','firmware/platform.h','firmware/store.c','firmware/store.h',
         'model/controller.c','model/controller.h','hardware/rtl/firmware_cosim_top.v',
         'hardware/rtl/pico1715_top.v','hardware/rtl/bus_frontend.v','hardware/rtl/irq_frontend.v')
def hashes(): return {name:digest(ROOT/name) for name in names}
sources = hashes()
with (out/'build.log').open('w') as log:
    subprocess.run([sys.executable,str(ROOT/'tools/build_cosim.py'),'--firmware','--dac',str(dac),
                    '--out',str(out/'build')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
subprocess.run([sys.executable,str(ROOT/'tests/cpu_cost_smoke.py'),str(out/'build/classic-probe'),
                str(out/'cases.json')],check=True,timeout=120)
require(hashes()==sources,'sources changed while running')
report={'schema':1,'profile':'rom-free-z80-firmware-costs','dac_commit':pin,'hardware_executed':False,
        'source_sha256':sources,'cases':json.loads((out/'cases.json').read_text()),
        'limitations':'Original synthetic ROM, actual Z80 core and firmware/RTL; injected aggregate costs, '
                       'not measured hardware timing. Reset held until firmware observes it; end-of-run storage is drained.'}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
