#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build original analyzer examples, Python oracle results, and browser test seams."""
import argparse, base64, hashlib, io, json, shutil, struct, subprocess
from pathlib import Path
from cycle_trace import Header, Cycle, export_csv
from analyzer_1715 import scan, compare, crc16
import analyzer_trace as raw
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,default=ROOT/'build/analyzer-workbench')
p.add_argument('--dac',type=Path,default=ROOT.parent/'dac-emulation')
p.add_argument('--emcc',default=str(ROOT/'local/emsdk/upstream/emscripten/emcc'))
p.add_argument('--cosim',type=Path,help='Existing check_cycle_analyzer output; only its original synthetic examples are copied')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);out=a.out.resolve()
rows=[]
def put(port,data,kind=5,flags=0,wait=0,duration=4):
 i=len(rows);rows.append(Cycle(kind,flags,data,port,wait,duration,i*100,i))
def field(data):
 b=bytes([161]*3+data);return b+crc16(b).to_bytes(2,'big')
put(0,0,8);put(0x20,0);put(4,255);put(6,4);put(7,207);put(7,18);put(7,18);put(7,183);put(7,207);put(0,18,6)
for b in field([254,0,0,1,0])+field([251]+list(range(128))):put(2,b,4)
put(4,254)
for b in field([254,0,0,1,0]):put(0,b)
put(4,255);put(6,34,4);put(0x100,0,1);put(0x101,0x76,1)
def save(name,rs,**kw):
 path=out/(name+'.p1715');path.write_bytes(Header(50000000,len(rs),**kw).encode()+b''.join(r.encode() for r in rs));return path
normal=save('controller',rows)
bad=list(rows);r=bad[20];bad[20]=Cycle(r.kind,r.flags,r.data^1,r.address,r.wait_samples,r.duration,r.tick,r.sequence);failed=save('crc-failure',bad)
slow=[Cycle(r.kind,r.flags,r.data,r.address,60,80,r.tick,r.sequence) if r.kind==4 else r for r in rows];save('wait-heavy',slow)
save('loss', [rows[0],*rows[3:]],dropped=2)
save('filtered', [rows[0],*rows[3:]],filtered=2)
save('uncertain',[Cycle(r.kind,1 if i==12 else r.flags,r.data,r.address,r.wait_samples,r.duration,r.tick,r.sequence) for i,r in enumerate(rows)])
save('trigger',[*rows[7:12]],filtered=7,trigger=(1,64,0,0,2,2,1,2,9,7,2,1))
save('wrap',[Cycle(5,0,207,7,0,2,0xfffffffc,0),Cycle(5,0,18,7,2,4,4,1)])
save('saturated',[Cycle(4,4,0,6,65535,65535,0,0)])
save('empty',[])
save('manual-history',rows[3:6],filtered=3,trigger=(1,64,0,0,8,5,0,0xffffffff,0xffffffff,3,0,2))
save('early-trigger',[rows[9]],filtered=9,trigger=(1,64,0,0,8,0,1,0,9,9,0,1))
matrix=[]
for port in [0,2,4,5,6,7,0x20,0x23,0xff]:
 for value in range(256):
  i=len(matrix);matrix.append(Cycle(4 if i%3==0 else 5,0,value,port,0,4,i*8,i))
save('decoder-matrix',matrix)
samples=[]
for i in range(256):
 s=(0x1200+i//8)|((i//4&255)<<16)|(((1<<14)-1)<<24)
 if i%8<4:s&=~((1<<24)|(1<<26)|(1<<28))
 if i%2==0:s&=~(1<<30)
 if i==100:s&=~(1<<32)
 samples.append(((0xfffffff0+i)&0xffffffff,s))
rc=raw.Capture(50000000,128,127,128,False,samples)
(out/'raw.p1715').write_bytes(rc.encode())
f=io.StringIO(newline='');raw.export_csv(rc,f);(out/'raw.csv').write_bytes(f.getvalue().encode());f=io.StringIO();raw.export_vcd(rc,f);(out/'raw.vcd').write_text(f.getvalue())
if a.cosim:
 expected=bytes.fromhex('f3 21 00 80 36 5a 7e d3 04 db 04 76 18 fd').ljust(2048,b'\0')
 if (a.cosim/'smoke.rom').read_bytes()!=expected:raise ValueError('Not the original public synthetic ROM')
 report=json.loads((a.cosim/'report.json').read_text())
 (out/'rtl-provenance.json').write_text(json.dumps({k:report[k] for k in ['dac_commit','source_sha256','tools','samples_per_cpu_tick','sample_hz']},indent=2)+'\n')
 for kind in ['all','io-only']:
  src=a.cosim/f'synthetic-{kind}'/'cycles.p1715'
  shutil.copyfile(src,out/f'rtl-{kind}.p1715')
oracle={}
for path in sorted(out.glob('*.p1715')):
 if path.stem=='raw':continue
 f=io.StringIO();report=scan(path,context=10000,output=f);oracle[path.stem]=report
 (out/(path.stem+'.jsonl')).write_text(f.getvalue())
 with path.open('rb') as source:
  from cycle_trace import read_header
  h=read_header(source);f=io.StringIO(newline='');export_csv(source,h,f);(out/(path.stem+'.csv')).write_bytes(f.getvalue().encode())
# Differential validation corpus: both accepted changes and malformed inputs.
validation=[]
for name in ['controller','trigger','raw','wrap']:
 blob=(out/(name+'.p1715')).read_bytes()
 candidates=[blob[:n] for n in [0,8,31,len(blob)-1]]+[blob+b'X']
 for offset in range(min(len(blob),112)):
  b=bytearray(blob);b[offset]^=0xff;candidates.append(bytes(b))
 for b in candidates:
  try:
   if name=='raw':raw.decode(b)
   else:
    from cycle_trace import decode
    decode(b)
   valid=True
  except (ValueError,struct.error):valid=False
  validation.append({'source':name,'bytes':base64.b64encode(b).decode(),'valid':valid})
(out/'validation.json').write_text(json.dumps(validation)+'\n')
oracle['comparison']=compare(normal,failed);(out/'oracle.json').write_text(json.dumps(oracle,indent=2)+'\n')
flags=['-O2','--no-entry','-sMODULARIZE=1','-sEXPORT_ES6=1','-sENVIRONMENT=web,worker,node','-sALLOW_MEMORY_GROWTH=1','-sEXPORTED_RUNTIME_METHODS=HEAPU8']
exports=['init','feed','read','disconnect','complete','stopping','error','frame','reset_enable','advance','poll','step','reset_active','reset_calls','reset_fail']
subprocess.run([a.emcc,str(ROOT/'tests/analyzer_usb_fixture.c'),str(ROOT/'firmware/analyzer_usb.c'),str(ROOT/'firmware/analyzer.c'),*flags,'-sEXPORTED_FUNCTIONS='+json.dumps(['_malloc','_free']+['_fixture_'+n for n in exports]),'-o',str(out/'usb-fixture.mjs')],check=True)
subprocess.run([a.emcc,str(ROOT/'tools/browser/analyzer_disasm.c'),'-I'+str(a.dac.resolve()),*flags,'-sEXPORTED_FUNCTIONS='+json.dumps(['_malloc','_free','_disassemble','_dis_text','_dis_count']),'-o',str(out/'disasm.mjs')],check=True)
shutil.copyfile(a.dac/'third_party/cpu/chips/LICENSE',out/'chips-LICENSE');shutil.copyfile(ROOT/'LICENSE',out/'LICENSE')
rev=lambda p:subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
manifest={'schema':1,'pico':rev(ROOT),'dac':rev(a.dac),'dirty':bool(subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'],text=True)),'origin':'Original directed decoder vectors; raw sampled test pattern; rtl-* (when present) from existing native RTL co-simulation. No historical ROM data.','source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['tools/build_analyzer_workbench.py','tools/analyzer_trace.py','tools/cycle_trace.py','tools/analyzer_1715.py','tools/browser/analyzer_disasm.c','tests/analyzer_usb_fixture.c','firmware/analyzer_usb.c','firmware/analyzer.c']},'compiler':subprocess.check_output([a.emcc,'--version'],text=True).splitlines()[0],'sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.iterdir()) if f.is_file() and f.name!='manifest.json'}}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(out)
