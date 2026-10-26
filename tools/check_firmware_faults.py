#!/usr/bin/env python3
"""Run reproducible firmware/RTL storage fault tests without external ROMs."""
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
names = ('firmware/controller_usb.c', 'firmware/controller_usb.h', 'firmware/service.c', 'firmware/service.h', 'firmware/platform.h',
         'firmware/store.c', 'firmware/store.h', 'firmware/sd_spi.h',
         'model/controller.c', 'model/controller.h',
         'tools/firmware_host/host_hal.c', 'tools/firmware_host/host_hal.h',
         'hardware/rtl/firmware_cosim_top.v', 'hardware/rtl/pico1715_top.v',
         'hardware/rtl/bus_frontend.v', 'hardware/rtl/irq_frontend.v',
         'tests/firmware_faults.cpp', 'tools/build_firmware_faults.py',
         'tools/check_firmware_faults.py')
def hashes():
    return {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}
sources = hashes()
with (out / 'build.log').open('w') as log:
    subprocess.run([sys.executable, str(ROOT / 'tools/build_firmware_faults.py'),
                    '--out', str(out / 'build')], stdout=log, stderr=subprocess.STDOUT,
                   check=True, timeout=180)
result = subprocess.run([str(out / 'build/firmware-faults')], capture_output=True,
                        text=True, timeout=180)
(out / 'stdout.txt').write_text(result.stdout)
(out / 'stderr.txt').write_text(result.stderr)
if result.returncode:
    raise RuntimeError(f'fault tests failed ({result.returncode}): {result.stderr}')
cases = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
expected = {
    'sd-delay-us': [0, 100, 5000, 50000],
    'reset-held-read': [0], 'reset-partial-sector': [100],
    'host-reset-during-writeback': list(range(1, 9)),
    'newer-write-during-snapshot': [1], 'sd-write-failure': list(range(1, 9)),
    'power-loss-before-sd-operation': list(range(1, 9)),
    'recovery-io-failure': [0, 1], 'torn-sd-write': list(range(1, 5)),
    'startup-read-delay-us': [100], 'startup-read-failure': [1, 2, 3, 1602],
}
assert len(cases) == 42
assert {(c['case'], c['parameter']) for c in cases} == {
    (name, value) for name, values in expected.items() for value in values}
summary = re.search(r'firmware fault suite PASS: 42 cases, (\d+) mailbox replies', result.stdout)
assert summary and hashes() == sources
assert sum(c["requests"] for c in cases) == int(summary.group(1))
report = {
    'schema': 1, 'profile': 'firmware-rtl-storage-faults', 'hardware_executed': False,
    'host_cpu': 'scripted bus transactions, not a Z80 program',
    'source_sha256': sources,
    'tools': {cmd: subprocess.check_output([cmd, '--version'], text=True).splitlines()[0]
              for cmd in ('cc', 'verilator')},
    'mailbox_replies': int(summary.group(1)), 'cases': cases,
    'limitations': ('Deterministic interleaving at SD block operations; not instruction-level '
                    'multicore contention, analog SD behavior or physical timing. Journal '
                    'recovery is per 512-byte block, not atomic across a 1024-byte sector '
                    'or filesystem operation. Unflushed RAM can be lost on power failure.'),
}
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'42 firmware/RTL fault cases passed; report: {out / "report.json"}')
