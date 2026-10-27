#!/usr/bin/env python3
"""Compare native sessions to their WASM build using identical clocks and inputs."""
import argparse,ctypes as C,json,os,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--backend',choices=['model','firmware'],required=True);p.add_argument('--rom',type=Path,required=True);p.add_argument('--disk',type=Path,required=True);p.add_argument('--cycles',type=int,default=40000000);p.add_argument('--command',default='DIR\r');p.add_argument('--out',type=Path,required=True);p.add_argument('--node',default='node');p.add_argument('--native-only',action='store_true');a=p.parse_args()
a.out.parent.mkdir(parents=True,exist_ok=True)
m=C.CDLL(str(Path('build/browser-native/pico1715-'+a.backend+'.so').resolve()))
for name in ['screen','ram','disk']:getattr(m,'p1715_'+name).restype=C.c_void_p
m.p1715_stat.restype=C.c_double;m.p1715_reg.restype=C.c_uint
rom=a.rom.read_bytes();disk=a.disk.read_bytes();assert m.p1715_init(rom,len(rom),disk,len(disk),1)==0
start=time.monotonic();tick=0;sent=False
while tick<a.cycles:
 if tick>=20000000 and not sent:
  for ch in a.command:assert m.p1715_key(ord(ch))==0
  sent=True
 n=min(1024,a.cycles-tick,20000000-tick if tick<20000000 else 1024);tick+=m.p1715_run(n)
while True:
 r=m.p1715_export()
 if r:break
assert r==1
m.p1715_run(8192)
if os.environ.get('PICO1715_TEST_RESET'):m.p1715_reset();m.p1715_run(8192)
while True:
 r=m.p1715_export()
 if r:break
assert r==1
native={'registers':[m.p1715_reg(i) for i in range(23)],'stats':[m.p1715_stat(i) for i in range(25)]}
for suffix,ptr,size in [('ram',m.p1715_ram(),65536),('img',m.p1715_disk(),819200)]:Path(str(a.out)+'.native.'+suffix).write_bytes(C.string_at(ptr,size))
Path(str(a.out)+'.native.json').write_text(json.dumps(native))
if a.native_only:sys.exit(0)
elapsed=time.monotonic()-start;start=time.monotonic()
subprocess.run([a.node,'tools/browser/run.mjs','build/browser/pico1715-'+a.backend+'.mjs',str(a.rom),str(a.disk),str(a.out),str(a.cycles),a.command],check=True,stdout=subprocess.DEVNULL)
for suffix in ['ram','img']:assert Path(str(a.out)+'.'+suffix).read_bytes()==Path(str(a.out)+'.native.'+suffix).read_bytes(),suffix
assert json.loads(Path(str(a.out)+'.json').read_text())==native,'registers/stats'
print(json.dumps({'backend':a.backend,'cycles':a.cycles,'native_seconds':elapsed,'wasm_seconds':time.monotonic()-start,'parity':'passed'}),flush=True)
