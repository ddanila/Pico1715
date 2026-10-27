#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Scripted native capture through the same ABI/RTL as the interactive browser."""
import argparse, ctypes as C, hashlib, json
from pathlib import Path
p=argparse.ArgumentParser()
for n in ('module','rom','disk','out'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--backend',choices=['model','firmware'],required=True);p.add_argument('--clocks',type=int,default=40000000);p.add_argument('--start-clock',type=int,default=0);p.add_argument('--mib',type=int,default=16);p.add_argument('--full',action='store_true');p.add_argument('--writable',action='store_true');p.add_argument('--command',default='');a=p.parse_args()
if not 0<=a.start_clock<a.clocks<=294960000 or not 1<=a.mib<=64:p.error('Invalid capture bounds (maximum 120 simulated seconds / 64 MiB)')
sha=lambda b:hashlib.sha256(b).hexdigest()
a.out.mkdir(parents=True,exist_ok=False);rom=a.rom.read_bytes();disk=a.disk.read_bytes();m=C.CDLL(str(a.module.resolve()))
for n in ('screen','disk','capture_data'):getattr(m,'p1715_'+n).restype=C.c_void_p
m.p1715_stat.restype=C.c_double
assert m.p1715_version()==2 and m.p1715_init(rom,len(rom),disk,len(disk),a.writable)==0
meta={'schema':1,'backend':a.backend,'build':{'module_sha256':sha(a.module.read_bytes())},'rom_sha256':sha(rom),'disk_sha256':sha(disk),'clock_hz':2458000,'start_clock':a.start_clock,'filter':'full' if a.full else 'io','observations':[],'timing':'four illustrative samples per CPU T-state; deferred transaction WAIT; not physical timing'}
clock=0;started=False;sent=False;last_screen=None;next_screen=0
while clock<a.clocks:
 if clock==a.start_clock:
  assert m.p1715_capture_start(a.mib*1048576,0x3fe if a.full else 0x170,a.clocks-a.start_clock)==0;started=True;meta['writes_at_start']=m.p1715_stat(4)
 if clock>=30000000 and not sent:
  for ch in a.command:assert m.p1715_key(ord(ch))==0
  sent=True
 if started and m.p1715_capture_status(0)==1 and clock>=next_screen:
  screen=''.join(chr(v) if 32<=v<127 else ' ' for v in C.string_at(m.p1715_screen(),1920))
  if screen!=last_screen and len(meta['observations'])<10000:meta['observations'].append({'kind':'screen','clock':clock,'detail':screen});last_screen=screen
  next_screen=clock+100000
 n=min(1024,a.clocks-clock,a.start_clock-clock if not started else 1024);used=m.p1715_run(n);assert used>0;clock+=used
m.p1715_capture_stop();assert m.p1715_capture_status(0)==2
blob=C.string_at(m.p1715_capture_data(),m.p1715_capture_status(2));meta.update(end_clock=a.start_clock+m.p1715_capture_status(4),capture_sha256=sha(blob),stop_reason=['','manual','size','time','fault'][m.p1715_capture_status(1)],complete=True)
(a.out/'capture.p1715').write_bytes(blob);(a.out/'capture.metadata.json').write_text(json.dumps(meta,indent=2)+'\n');(a.out/'screen.txt').write_text(C.string_at(m.p1715_screen(),1920).decode('ascii','replace'))
for _ in range(1000000):
 result=m.p1715_export()
 if result:break
assert result==1
(a.out/'disk.img').write_bytes(C.string_at(m.p1715_disk(),819200));m.p1715_capture_release()
print('Capture complete:',len(blob),'bytes;',meta['stop_reason'])
