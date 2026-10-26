#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Qualify controller USB protocol, host CLI and simulated storage/bus contention."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
out = a.out.resolve()
out.mkdir(parents=True, exist_ok=False)
names = ('firmware/service.c', 'firmware/service.h', 'firmware/platform.h',
         'firmware/controller_usb.c', 'firmware/controller_usb.h', 'firmware/controller_usb_device.c',
         'firmware/main.c', 'firmware/CMakeLists.txt', 'firmware/store.c', 'firmware/store.h',
         'firmware/sd_crc.h', 'model/controller.c', 'model/controller.h',
         'tools/firmware_host/host_hal.c', 'tools/firmware_host/host_hal.h',
         'hardware/rtl/firmware_cosim_top.v', 'hardware/rtl/pico1715_top.v',
         'hardware/rtl/bus_frontend.v', 'hardware/rtl/irq_frontend.v',
         'tests/controller_usb_device_test.c', 'tests/usb_stub/tusb.h', 'tests/controller_usb_fixture.c', 'tests/test_controller_usb.py', 'tests/firmware_timing.cpp',
         'tools/build_firmware_faults.py', 'tools/controller_usb.py', 'tools/check_controller_usb.py')
def hashes(): return {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
sources = hashes()
with (out/'build.log').open('w') as log:
    subprocess.run([sys.executable, str(ROOT/'tools/build_firmware_faults.py'), '--suite', 'timing',
                    '--out', str(out/'build')], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                   check=True, timeout=180)
unit = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                       '-p', 'test_controller_usb.py', '-v'], cwd=ROOT, text=True,
                      capture_output=True, timeout=60)
(out/'protocol.txt').write_text(unit.stdout+unit.stderr)
assert unit.returncode == 0, unit.stdout+unit.stderr
count = int(re.search(r'Ran (\d+) tests', unit.stderr)[1])
result = subprocess.run([str(out/'build/firmware-timing'), '--control'], text=True,
                        capture_output=True, timeout=180)
(out/'contention.txt').write_text(result.stdout+result.stderr)
assert result.returncode == 0, result.stdout+result.stderr
cases = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
traffic = [dict(responses=int(n),worker_delay_us=int(d),eject=bool(int(e)))
           for n,d,e in re.findall(r'control responses=(\d+) worker_delay=(\d+) eject=(\d+)', result.stdout)]
assert len(cases) == len(traffic) == 4
for case, counters in zip(cases, traffic): case['traffic'] = counters
for c in (cases[0], cases[1], cases[3]):
    assert c['complete'] and c['equal'] and not any(c[k] for k in
        ('fault','overruns','underflows','tx_underruns','tx_overruns','storage_error','late_replies','reset_replies'))
assert cases[2]['fault'] and not cases[2]['complete']
assert cases[3]['shutdown'] == 2 and not cases[3]['dirty']
assert all(cases[i]['traffic']['responses']>10 for i in (0,1))
assert hashes() == sources
report = dict(schema=1, profile='controller-usb-control', hardware_executed=False,
              source_sha256=sources, protocol_tests=count, cases=cases,
              limitations='Shared handler/CLI with real firmware storage; scripted bus and injected costs. '
              'No USB enumeration, physical disconnect, interrupt load or measured RP2350 timing qualification. '
              'Snapshot cost and worker delay are hypothetical; TinyUSB itself is not simulated.')
(out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(f'{count} protocol/CLI tests and four contention cases passed; report: {out / "report.json"}')
