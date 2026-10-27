#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the shared capture ABI in isolated native sessions; emit parity fixtures."""
import argparse, ctypes as c, hashlib, io, json, subprocess, sys
from pathlib import Path
from cycle_trace import read_header, records
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--case');a=p.parse_args()
if not a.case:
 a.out.mkdir(parents=True,exist_ok=False)
 for backend in ('model','firmware'):
  for case in ('off','full','io','size','time','reset','empty'):
   subprocess.run([sys.executable,__file__,'--build',str(a.build),'--out',str(a.out),'--case',backend+':'+case],check=True)
  reports={n:json.loads((a.out/f'{backend}-{n}.json').read_text()) for n in ('off','full','io','size','time')}
  assert len({json.dumps(r['guest'],sort_keys=True) for r in reports.values()})==1,'capture changed guest state'
 print('session capture PASS');sys.exit()
backend,case=a.case.split(':');lib=c.CDLL(str((a.build/f'pico1715-{backend}.so').resolve()))
lib.p1715_capture_data.restype=c.c_void_p;lib.p1715_ram.restype=c.c_void_p
rom=bytes.fromhex('3150fe3e55d340db40c30300').ljust(2048,b'\0');disk=bytes(819200)
assert lib.p1715_version()==2
assert lib.p1715_init(rom,len(rom),disk,len(disk),0)==0
assert lib.p1715_capture_start(1,0x170,0)<0
if case!='off':
 assert lib.p1715_capture_start(8192 if case=='size' else 1024*1024,0x170 if case=='io' else 0x3fe,400 if case=='time' else 0)==0
 assert lib.p1715_capture_start(8192,0x170,0)<0
if case=='reset':lib.p1715_reset()
lib.p1715_run(0 if case=='empty' else 10000)
lib.p1715_capture_stop();lib.p1715_capture_stop()
report={'backend':backend,'case':case,'guest':{'regs':[lib.p1715_reg(i) for i in range(23)],'ram':hashlib.sha256(c.string_at(lib.p1715_ram(),65536)).hexdigest()}}
if case!='off':
 assert lib.p1715_capture_status(0)==2
 blob=c.string_at(lib.p1715_capture_data(),lib.p1715_capture_status(2));stream=io.BytesIO(blob);h=read_header(stream);rs=[r for r,_ in records(stream,h)]
 assert not h.dropped
 assert lib.p1715_capture_status(1)==({'size':2,'time':3}.get(case,1))
 if case=='io':assert rs and all(r.kind in (4,5,6,8) for r in rs)
 if case=='full':assert {1,2,4,5,7}<=set(r.kind for r in rs)
 (a.out/f'{backend}-{case}.p1715').write_bytes(blob)
 report['capture_sha256']=hashlib.sha256(blob).hexdigest();report['records']=h.count
lib.p1715_capture_release();assert lib.p1715_capture_status(0)==0
(a.out/f'{backend}-{case}.json').write_text(json.dumps(report,indent=2)+'\n')
