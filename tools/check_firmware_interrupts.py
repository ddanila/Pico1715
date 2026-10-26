#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Qualify bounded receive elasticity across index/mark interrupt phases."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
out = a.out.resolve()
out.mkdir(parents=True, exist_ok=False)
names = ('firmware/controller_usb.c', 'firmware/controller_usb.h', 'firmware/service.c', 'firmware/service.h', 'firmware/platform.h',
         'firmware/store.c', 'firmware/store.h', 'model/controller.c', 'model/controller.h',
         'tools/firmware_host/host_hal.c', 'tools/firmware_host/host_hal.h',
         'hardware/rtl/firmware_cosim_top.v', 'hardware/rtl/pico1715_top.v',
         'hardware/rtl/bus_frontend.v', 'hardware/rtl/irq_frontend.v',
         'tests/firmware_interrupts.cpp', 'tools/build_firmware_faults.py',
         'tools/check_firmware_interrupts.py')

def hashes():
    return {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}

sources = hashes()
with (out/'build.log').open('w') as log:
    subprocess.run([sys.executable, str(ROOT/'tools/build_firmware_faults.py'),
                    '--suite', 'interrupts', '--out', str(out/'build')],
                   stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
result = subprocess.run([str(out/'build/firmware-interrupts')], text=True,
                        capture_output=True, timeout=180)
(out/'stdout.txt').write_text(result.stdout)
(out/'stderr.txt').write_text(result.stderr)
assert result.returncode == 0, result.stderr
cases = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
assert len(cases) == 263 and hashes() == sources
sweep = [c for c in cases if c['length'] == 10 and c['index_service_us'] == 28]
assert len(sweep) == 258
for production in (False, True):
    subset = [c for c in sweep if c['production'] == production]
    assert sorted(c['phase_us'] for c in subset) == list(range(-64, 65))
    assert all(c['capacity'] == (2 if production else 1) for c in subset)
    assert all(c['mark_acks'] == 1 and c['index_acks'] <= 1 for c in subset)
for phase in range(-64, 65):
    pair = [c for c in sweep if c['phase_us'] == phase]
    assert len({(c['index_acks'], c['mark_acks'], c['index_minus_mark_ticks']) for c in pair}) == 1
reference_losses = [c for c in sweep if not c['production'] and c['overruns']]
assert reference_losses and all(not c['equal'] and c['index_acks'] == 1 for c in reference_losses)
normal = [c for c in cases if c['production'] and c['index_service_us'] == 28 and not c['read_pause_us']]
assert len(normal) == 132 and all(c['equal'] and c['overruns'] == 0 for c in normal)
assert sorted(c['phase_us'] for c in normal if c['length'] == 1030) == [-32, 0, 32]
negative = [c for c in cases if c['index_service_us'] == 160 or c['read_pause_us']]
assert len(negative) == 2 and all(c['production'] and c['capacity'] == 2 and
                                c['overruns'] > 0 and not c['equal'] for c in negative)
report = {'schema': 1, 'profile': 'firmware-rtl-interrupt-elasticity',
          'hardware_executed': False, 'source_sha256': sources,
          'reference_loss_phases': len(reference_losses), 'clean_production_cases': len(normal),
          'negative_controls': len(negative), 'cases': cases,
          'limitations': 'Scripted bus with bounded handler delays, not CPU instructions or physical timing. '
                         'Independent synthetic index/field scheduling; no rotating-track model. '
                         'Two-byte firmware queue intentionally differs from the one-byte PIO reference. '
                         'Index edges during in-service are suppressed by the existing controller model.'}
(out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(f'263 interrupt cases passed: {len(reference_losses)} one-byte loss phases, '
      f'{len(normal)} clean production cases, two detected overloads; report: {out / "report.json"}')
