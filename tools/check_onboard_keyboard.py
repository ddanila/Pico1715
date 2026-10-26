#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the real boot probe and run ROM-free SIO keyboard regressions."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--dac', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
dac, out = a.dac.resolve(), a.out.resolve()
revision = subprocess.check_output(['git', '-C', str(dac), 'rev-parse', 'HEAD'], text=True).strip()
if revision != json.loads((ROOT/'docs/sources.json').read_text())['dac']['commit']:
    raise RuntimeError('unqualified DAC revision')
for command in (['diff', '--quiet'], ['diff', '--cached', '--quiet']):
    subprocess.run(['git', '-C', str(dac), *command], check=True)
out.mkdir(parents=True, exist_ok=False)
sources = [ROOT/'tools/classic_probe.c', ROOT/'model/controller.c',
           dac/'machines/robotron1715/pc1715.c', dac/'common/cpu/z80.c', dac/'common/trace/trace.c']
binary = out/'classic-probe'
subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=undefined', '-fno-sanitize-recover=all', '-I', str(dac),
                *map(str, sources), '-o', str(binary)], check=True)
subprocess.run([sys.executable, str(ROOT/'tests/onboard_keyboard_smoke.py'), str(binary),
                str(out/'cases.json')], check=True)
report = {'dac_commit': revision, 'hardware_executed': False,
          'keyboard': 'completed E0/ASCII bytes to onboard SIO A; guest controls receiver',
          'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
                            for f in (ROOT/'tools/classic_probe.c', ROOT/'model/controller.c',
                                      ROOT/'tests/onboard_keyboard_smoke.py', Path(__file__).resolve())},
          'cases': json.loads((out/'cases.json').read_text())}
(out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
