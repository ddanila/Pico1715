#!/usr/bin/env python3
"""Build the Verilated frontend + unchanged DAC CPU + C controller co-simulator."""
import argparse
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--dac',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--firmware',action='store_true')
p.add_argument('--combined',action='store_true')
a=p.parse_args(); a.firmware=a.firmware or a.combined; dac=a.dac.resolve(); out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
objects=[]
sources=[ROOT/'tools/classic_probe.c',ROOT/'model/controller.c',
                           dac/'machines/robotron1715/pc1715.c',dac/'common/cpu/z80.c',dac/'common/trace/trace.c']
if a.firmware:
 sources += [ROOT/'firmware/service.c',ROOT/'firmware/store.c',ROOT/'tools/firmware_host/host_hal.c']
if a.combined:sources += [ROOT/'firmware/combined.c',ROOT/'firmware/analyzer.c']
for i,source in enumerate(sources):
 obj=out/f'part{i}.o';objects.append(str(obj))
 subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-DPICO1715_COSIM',
                 *(['-DP1715_HOST_SIM','-DP1715_FIRMWARE_COSIM','-I',str(ROOT/'tools/firmware_host')] if a.firmware else []),
                 *(['-DP1715_COMBINED=1'] if a.combined else []),'-I',str(dac),'-c',str(source),'-o',str(obj)],check=True)
top='firmware_cosim_top' if a.firmware else 'cosim_top'
subprocess.run(['verilator','--cc','--exe','--build','-j','2','-O3','-Wall',
 *(['-DP1715_COMBINED'] if a.combined else []),'--top-module',top,'--Mdir',str(out/'rtl'),
 '-CFLAGS',f'-O2 -I{ROOT} -I{dac}'+(' -DP1715_COMBINED=1' if a.combined else ''),str(ROOT/f'hardware/rtl/{top}.v'),
 *([str(ROOT/'hardware/rtl/pico1715_top.v')] if a.firmware else []),
 *([str(ROOT/f'hardware/rtl/{n}.v') for n in ('combined_mailbox','carrier_combined','cycle_encoder','analyzer_record_fifo','cycle_capture_top','analyzer_link','analyzer_transport_top')] if a.combined else []),
 str(ROOT/'hardware/rtl/bus_frontend.v'),str(ROOT/'hardware/rtl/irq_frontend.v'),
 str(ROOT/('tools/firmware_host/bridge.cpp' if a.firmware else 'tools/cosim/bridge.cpp')),*objects,'-o',str(out/'classic-probe')],check=True)
# Verilator places the externally compiled C objects in linker flags, not in
# the generated target prerequisites. Force the final link after rebuilding
# them, even when the RTL and C++ bridge themselves have not changed.
subprocess.run(['make', '-C', str(out/'rtl'), '-f', f'V{top}.mk', '-W', f'V{top}__ALL.a',
                str(out/'classic-probe')], check=True)
