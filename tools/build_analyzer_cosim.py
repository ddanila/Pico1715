#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the passive cycle analyzer against unchanged DAC and the C card model."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--dac', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
dac, out = a.dac.resolve(), a.out.resolve()
out.mkdir(parents=True, exist_ok=True)
objects = []
for i, source in enumerate([ROOT/'tools/classic_probe.c', ROOT/'model/controller.c',
                           dac/'machines/robotron1715/pc1715.c', dac/'common/cpu/z80.c',
                           dac/'common/trace/trace.c']):
    obj = out/f'part{i}.o'
    objects.append(str(obj))
    subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-DP1715_ANALYZER', '-I', str(dac), '-c', str(source), '-o', str(obj)], check=True)
subprocess.run(['verilator', '--cc', '--exe', '--build', '-j', '2', '-O3', '-Wall',
                '--top-module', 'cycle_capture_top', '--Mdir', str(out/'rtl'),
                '-CFLAGS', f'-O2 -I{ROOT} -I{dac}',
                str(ROOT/'hardware/rtl/cycle_encoder.v'),
                str(ROOT/'hardware/rtl/cycle_capture_top.v'),
                str(ROOT/'tools/analyzer/bridge.cpp'), *objects,
                '-o', str(out/'classic-probe')], check=True)
