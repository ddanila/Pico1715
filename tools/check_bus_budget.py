#!/usr/bin/env python3
"""Reproduce a conditional pre-layout X2 budget; never certify physical timing."""
import argparse
import hashlib
import json
import math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--timing', type=Path, default=ROOT/'build/hx8k/timing.json')
p.add_argument('--output', type=Path, default=ROOT/'reports/x2-desk-timing.json')
a = p.parse_args()
timing = json.loads(a.timing.read_text())
fit = json.loads(a.timing.with_name('report.json').read_text())
assert fit['top']=='pico1715_top', 'Use the production top, not the fixture'
for name,digest in fit['source_sha256'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest, f'Stale fit: {name}'
paths = [x for x in timing['critical_paths'] if x['from'] == '<async>' and x['to'] == '<async>']
assert paths, 'Need routed input-to-output timing, not clock Fmax alone'
worst = max(paths, key=lambda x: sum(s['delay'] for s in x['path']))
fpga_ns = sum(s['delay'] for s in worst['path'])
# Datasheet maxima at 3.3 +/-0.3 V, -40..85 C, specified test loads.
logic = {'SN74LVC245A': 6.3, 'SN74LVC00A': 4.3, 'SN74LVC07A': 3.6}
period = 1e9/2458000
report = dict(schema=1,hardware_executed=False,electrical_timing_qualified=False,
    source_sha256=fit['source_sha256'],cpu_hz=2458000,cpu_period_ns=period,fpga_period_ns=20,
    timing_sha256=hashlib.sha256(a.timing.read_bytes()).hexdigest(),
    routed_async_envelope_ns=fpga_ns,
    envelope_endpoints=[worst['path'][0]['from']['cell'],worst['path'][-1]['to']['cell']],
    translator_max_ns=logic,
    conditional_wait_assert_path_ns=sum(logic.values())+fpga_ns,
    wait_margin_ns=None,
    wait_pullup_ohms=3300,
    ideal_release_to_2V_ns={str(c): -3300*c*1e-3*math.log(1-2/5) for c in [50,100,200]},
    unresolved=['U880 clock-to-IORQ/RD/WR maximum and WAIT setup at actual grade',
                'Motherboard output buffer delay, routing and actual loading',
                'Routed WAIT endpoint constraint and hazards, not only worst async summary',
                'Data/OE/WAIT relative minimum and maximum delays including AHCT541',
                'IACK window and RETI fetch-data validity',
                'Power-ramp and analog signal integrity'])
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(f'Conditional assertion path: {report["conditional_wait_assert_path_ns"]:.3f} ns; CPU period {period:.3f} ns')
print('UNQUALIFIED: CPU deadline/load inputs missing; no timing margin asserted')
