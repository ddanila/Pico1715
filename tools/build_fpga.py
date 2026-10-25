#!/usr/bin/env python3
"""Build the fully pinned HX8K bench target; never programs a device."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--yosys', default='yosys')
p.add_argument('--nextpnr', default='nextpnr-ice40')
p.add_argument('--icepack', default='icepack')
p.add_argument('--out', type=Path, default=ROOT / 'build/hx8k')
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
out = a.out.resolve()
sources = ['hardware/rtl/bus_frontend.v', 'hardware/rtl/irq_frontend.v',
           'hardware/rtl/pico1715_top.v']
commands = [
    [a.yosys, '-Q', '-T', '-p', 'read_verilog -sv ' + ' '.join(sources) +
     '; synth_ice40 -top pico1715_top -json "' + str(out / 'design.json') +
     '"; check -assert; stat'],
    [a.nextpnr, '--hx8k', '--package', 'ct256', '--json', str(out / 'design.json'),
     '--pcf', 'hardware/boards/hx8k.pcf', '--asc', str(out / 'design.asc'),
     '--freq', '100', '--report', str(out / 'timing.json')],
    [a.icepack, str(out / 'design.asc'), str(out / 'design.bin')],
]
for name, command in zip(('synth', 'route', 'pack'), commands):
    with (out / (name + '.log')).open('w') as log:
        subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
timing = json.loads((out / 'timing.json').read_text())
assert timing['fmax'] and all(v['achieved'] >= v['constraint'] for v in timing['fmax'].values())
files = sources + ['hardware/boards/hx8k.pcf', 'hardware/boards/hx8k-pins.json']
report = dict(schema=1, target='Olimex iCE40HX8K-EVB Rev B1',
              internal_timing_passed=True, electrical_timing_qualified=False,
              fmax=timing['fmax'], utilization=timing['utilization'],
              source_sha256={s: hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in files},
              bitstream_sha256=hashlib.sha256((out/'design.bin').read_bytes()).hexdigest(),
              commands=commands,
              tool_versions={exe: subprocess.run([exe, flag], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                                  check=True).stdout.strip()
                             for exe, flag in [(a.yosys, '-V'), (a.nextpnr, '--version')]})
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'Built {out / "design.bin"}; internal timing passed; external timing unqualified')
