#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import argparse
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description='Build shared analyzer firmware against Verilated FIFO/link')
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
obj=out/'analyzer.o'
subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-c',str(ROOT/'firmware/analyzer.c'),'-o',str(obj)],check=True)
subprocess.run(['verilator','--cc','--exe','--build','-j','2','-O3','-Wall',
 '--top-module','analyzer_transport_fixture','--Mdir',str(out/'rtl'),'-CFLAGS',f'-O2 -I{ROOT}',
 *[str(ROOT/'hardware/rtl'/s) for s in ('analyzer_transport_fixture.v','analyzer_record_fifo.v','analyzer_link.v')],
 str(ROOT/'tests/analyzer_transport.cpp'),str(obj),'-o',str(out/'transport-test')],check=True)
