#!/usr/bin/env python3
"""Build deterministic storage or interrupt tests around production firmware and RTL."""
import argparse
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--suite', choices=('faults', 'interrupts', 'timing'), default='faults')
a = p.parse_args()
out = a.out.resolve()
out.mkdir(parents=True, exist_ok=True)
objects = []
for i, source in enumerate(('firmware/service.c', 'firmware/store.c', 'firmware/controller_usb.c',
                            'model/controller.c', 'tools/firmware_host/host_hal.c')):
    obj = out / f'part{i}.o'
    objects.append(str(obj))
    subprocess.run(['cc', '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
                    '-DP1715_HOST_SIM', '-I', str(ROOT / 'tools/firmware_host'),
                    '-c', str(ROOT / source), '-o', str(obj)], check=True)
subprocess.run(['verilator', '--cc', '--exe', '--build', '-j', '2', '-O3', '-Wall',
                '--top-module', 'firmware_cosim_top', '--Mdir', str(out / 'rtl'),
                '-CFLAGS', f'-O2 -I{ROOT}',
                *[str(ROOT / f'hardware/rtl/{s}.v') for s in
                  ('firmware_cosim_top', 'pico1715_top', 'bus_frontend', 'irq_frontend')],
                str(ROOT / f'tests/firmware_{a.suite}.cpp'), *objects,
                '-o', str(out / f'firmware-{a.suite}')], check=True)
