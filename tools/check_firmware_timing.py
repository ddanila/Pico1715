#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure deterministic firmware service-cost limits; no private ROM required."""
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
         'firmware/store.c', 'firmware/store.h', 'firmware/sd_spi.h', 'firmware/sd_crc.h',
         'model/controller.c', 'model/controller.h',
         'tools/firmware_host/host_hal.c', 'tools/firmware_host/host_hal.h',
         'hardware/rtl/firmware_cosim_top.v', 'hardware/rtl/pico1715_top.v',
         'hardware/rtl/bus_frontend.v', 'hardware/rtl/irq_frontend.v',
         'tests/firmware_timing.cpp', 'tools/build_firmware_faults.py',
         'tools/check_firmware_timing.py')
def hashes():
    return {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}

def clean(c):
    return c['complete'] and c['equal'] and not any(c[k] for k in
        ('fault', 'overruns', 'underflows', 'tx_underruns', 'tx_overruns', 'storage_error'))

sources = hashes()
with (out/'build.log').open('w') as log:
    subprocess.run([sys.executable, str(ROOT/'tools/build_firmware_faults.py'),
                    '--suite', 'timing', '--out', str(out/'build')],
                   stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
result = subprocess.run([str(out/'build/firmware-timing')], capture_output=True,
                        text=True, timeout=300)
(out/'stdout.txt').write_text(result.stdout)
(out/'stderr.txt').write_text(result.stderr)
assert result.returncode == 0, result.stderr
cases = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
assert len(cases) == 153 and hashes() == sources
assert not any(c['late_replies'] or c['reset_replies'] or c['storage_error'] for c in cases)
# Preserve the demonstrated minimum envelope; overloads must still be visible.
families = {'read-cost': (2, 27), 'poll-cost': (0, 15), 'write-cost': (3, 26),
            'field-build-cost': (1, 80), 'snapshot-lock-cost': (5, 64), 'commit-cost': (4, 80)}
limits = {}
for name, (kind, minimum_clean) in families.items():
    rows = sorted((c for c in cases if c['case'] == name), key=lambda c: c['delay_us'])
    expected = list(range(41)) if name in ('read-cost', 'poll-cost', 'write-cost') else [0,16,32,48,64,80,96,128]
    assert [c['delay_us'] for c in rows] == expected
    assert all(clean(c) for c in rows if c['delay_us'] <= minimum_clean), name
    assert rows[0]['sd_waits'] > 0, name
    # Long lock waits can expire the request before the operation is reached;
    # at least the baseline must exercise the charged site.
    assert rows[0]['cost_calls'][kind] > 0, name
    failures = [c for c in rows if not clean(c)]
    assert failures, name
    first = failures[0]
    previous = max(c['delay_us'] for c in rows if clean(c) and c['delay_us'] < first['delay_us'])
    limits[name] = {'last_clean_before_first_failure_us': previous,
                   'first_failure_us': first['delay_us'],
                   'failure_signals': {k: first[k] for k in ('fault','overruns','underflows','tx_underruns','tx_overruns') if first[k]},
                   'max_request_us_at_failure': first['max_request_us']}
by_name = {c['case']: c for c in cases if c['case'] not in families}
assert set(by_name) == {'watchdog-held-read', 'watchdog-late-commit', 'watchdog-lock-contention',
                       'watchdog-reset-recovery', 'reset-during-read', 'eject-during-contended-writeback'}
for name in ('watchdog-held-read','watchdog-late-commit','watchdog-lock-contention'):
    c = by_name[name]
    assert c['fault'] and not c['complete'] and 81 <= c['fault_release_us'] <= 84
assert by_name['watchdog-lock-contention']['lock_wait_us'] >= 128
for name in ('watchdog-reset-recovery','reset-during-read','eject-during-contended-writeback'):
    assert clean(by_name[name]), name
assert by_name['reset-during-read']['cost_calls'][2] > 0
c = by_name['eject-during-contended-writeback']
assert c['shutdown'] == 2 and not c['dirty'] and c['lock_wait_us'] and c['sd_waits'] == 8
report = {'schema': 1, 'profile': 'firmware-rtl-service-cost', 'hardware_executed': False,
          'source_sha256': sources, 'limits': limits, 'cases': cases,
          'timing': {'scheduler_step_us': 1, 'sd_write_delay_us': 5000, 'receive_capacity': 2},
          'tools': {tool: subprocess.check_output([tool, '--version'], text=True).splitlines()[0]
                    for tool in ('cc', 'verilator')},
          'limitations': 'Injected costs, not measured execution times. Scripted host bus and cooperative cores, '
                         'not ARM instructions, Z80 instruction timing, real caches, QMI/SPI waveforms, or physical CDC. '
                         'One cost varied at a time; budgets are not additive. Controller catches up on service ticks. '
                         'Reset is held through the stalled operation; short reset pulses are not qualified.'}
(out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(f'153 firmware cost/fault cases passed; report: {out / "report.json"}')
for name, limit in limits.items():
    print(f'{name}: clean {limit["last_clean_before_first_failure_us"]} us; first sampled failure {limit["first_failure_us"]} us')
