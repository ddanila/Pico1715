#!/usr/bin/env python3
"""Build deterministic storage or interrupt tests around production firmware and RTL."""
import argparse
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--combined', action='store_true')
p.add_argument('--suite', choices=('faults', 'interrupts', 'timing'), default='faults')
a = p.parse_args()
out = a.out.resolve()
out.mkdir(parents=True, exist_ok=True)
objects = []
sources = ['firmware/service.c', 'firmware/store.c', 'firmware/controller_usb.c',
                            'model/controller.c', 'tools/firmware_host/host_hal.c']
if a.combined:sources += ['firmware/combined.c','firmware/analyzer.c']
for i, source in enumerate(sources):
    obj = out / f'part{i}.o'
    objects.append(str(obj))
    subprocess.run(['cc', '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
                    '-DP1715_HOST_SIM', *(['-DP1715_COMBINED=1'] if a.combined else []), '-I', str(ROOT / 'tools/firmware_host'),
                    '-c', str(ROOT / source), '-o', str(obj)], check=True)
rtl_sources=['firmware_cosim_top','pico1715_top','bus_frontend','irq_frontend']
if a.combined:rtl_sources += ['combined_mailbox','carrier_combined','cycle_encoder','analyzer_record_fifo','cycle_capture_top','analyzer_link','analyzer_transport_top']
subprocess.run(['verilator', '--cc', '--exe', '--build', '-j', '2', '-O3', '-Wall',
                *(['-DP1715_COMBINED'] if a.combined else []), '--top-module', 'firmware_cosim_top', '--Mdir', str(out / 'rtl'),
                '-CFLAGS', f'-O2 -I{ROOT}'+(' -DP1715_COMBINED=1' if a.combined else ''),
                *[str(ROOT / f'hardware/rtl/{s}.v') for s in
                  rtl_sources],
                str(ROOT / f'tests/firmware_{a.suite}.cpp'), *objects,
                '-o', str(out / f'firmware-{a.suite}')], check=True)

# External C objects are linker flags rather than generated make prerequisites.
subprocess.run(['make', '-C', str(out/'rtl'), '-f', 'Vfirmware_cosim_top.mk',
                '-W', 'Vfirmware_cosim_top__ALL.a', str(out/f'firmware-{a.suite}')], check=True)
