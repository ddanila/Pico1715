#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile/run the real controller and opt-in DAC interrupt chain without ROMs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dac', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    dac, out = args.dac.resolve(), args.out.resolve()
    revision = subprocess.check_output(['git', '-C', str(dac), 'rev-parse', 'HEAD'], text=True).strip()
    pin = json.loads((ROOT/'docs/sources.json').read_text())['dac']['commit']
    if revision != pin:
        raise RuntimeError('unqualified DAC revision')
    for command in (['diff', '--quiet'], ['diff', '--cached', '--quiet']):
        subprocess.run(['git', '-C', str(dac), *command], check=True)
    out.mkdir(parents=True, exist_ok=False)
    files = [ROOT/'tests/motherboard_chain.c', ROOT/'model/controller.c',
             dac/'machines/robotron1715/pc1715.c', dac/'common/cpu/z80.c', dac/'common/trace/trace.c']
    binary = out/'motherboard-chain'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=undefined', '-fno-sanitize-recover=all', '-I', str(dac),
                    *map(str, files), '-o', str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    sources = files + [dac/'machines/robotron1715/peripherals.h', dac/'machines/robotron1715/pc1715.h',
                       ROOT/'model/controller.h', Path(__file__).resolve()]
    report = {'hardware_executed': False,
              'dac_commit': revision,
              'source_sha256': {('dac/' + str(p.relative_to(dac)) if p.is_relative_to(dac) else str(p.relative_to(ROOT))):
                                hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              'result': result.stdout.splitlines(),
              'limits': 'Register-level CTC/SIO subset; completed serial bytes and external levels injected. No electrical or full serial peripheral qualification.'}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(result.stdout, end='')

if __name__ == '__main__':
    main()
