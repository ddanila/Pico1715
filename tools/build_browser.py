#!/usr/bin/env python3
"""Build both classic sessions from the same sources for native or WebAssembly hosts."""
import argparse, hashlib, json, os, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--dac',type=Path,default=ROOT.parent/'dac-emulation')
p.add_argument('--out',type=Path,default=ROOT/'build/browser')
p.add_argument('--backend',choices=['model','firmware','all'],default='all')
p.add_argument('--native',action='store_true')
p.add_argument('--probes',action='store_true',help='also build Node CLI qualification probes')
p.add_argument('--emcc',default=os.environ.get('EMCC',str(ROOT/'local/emsdk/upstream/emscripten/emcc')))
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True);dac=a.dac.resolve()
exports=['result','version','init','run','key','cancel','reset','break','hit','step','screen','ram','disk','peek','map','reg','disassemble','text','export','stat','capture_start','capture_stop','capture_release','capture_status','capture_data']
for backend in (['model','firmware'] if a.backend=='all' else [a.backend]):
 work=out/backend;work.mkdir(exist_ok=True)
 cc='cc' if a.native else a.emcc
 cxx='c++' if a.native else str(Path(a.emcc).with_name('em++'))
 flags=['-O2','-DVL_IGNORE_UNKNOWN_ARCH','-DP1715_CAPTURE','-I'+str(dac),'-I'+str(ROOT)]
 if a.native:flags+=['-fPIC']
 if backend=='firmware':flags+=['-DPICO1715_COSIM','-DP1715_FIRMWARE_COSIM','-DP1715_HOST_SIM','-I'+str(ROOT/'tools/firmware_host')]
 sources=[ROOT/'tools/browser/session.c',ROOT/'model/controller.c',dac/'machines/robotron1715/pc1715.c',dac/'common/cpu/z80.c',dac/'common/trace/trace.c']
 if backend=='firmware':sources += [ROOT/'firmware/service.c',ROOT/'firmware/store.c',ROOT/'tools/firmware_host/host_hal.c']
 objects=[]
 for i,src in enumerate(sources):
  obj=work/f'part{i}.o';subprocess.run([cc,*flags,'-std=c11','-Wall','-Wextra','-Werror','-c',str(src),'-o',str(obj)],check=True);objects.append(str(obj))
 if backend=='firmware':
  rtl=work/'rtl';subprocess.run(['verilator','--cc','-O3','-Wall','--top-module','firmware_cosim_top','--Mdir',str(rtl),*[str(ROOT/'hardware/rtl'/f'{n}.v') for n in ['firmware_cosim_top','pico1715_top','bus_frontend','irq_frontend']]],check=True)
  vr=Path('/usr/share/verilator/include')
  cpp=[ROOT/'tools/firmware_host/bridge.cpp',*sorted(rtl.glob('*.cpp')),vr/'verilated.cpp',vr/'verilated_threads.cpp']
  for i,src in enumerate(cpp):
   obj=work/f'cpp{i}.o';subprocess.run([cxx,*flags,'-std=c++17','-I'+str(rtl),'-I'+str(vr),'-I'+str(vr/'vltstd'),'-c',str(src),'-o',str(obj)],check=True);objects.append(str(obj))
 rtl=work/'capture-rtl';subprocess.run(['verilator','--cc','-O3','-Wall','--top-module','cycle_capture_top','--Mdir',str(rtl),*[str(ROOT/'hardware/rtl'/f'{n}.v') for n in ['cycle_encoder','analyzer_record_fifo','cycle_capture_top']]],check=True)
 vr=Path('/usr/share/verilator/include')
 cpp=[ROOT/'tools/analyzer/session_capture.cpp',*sorted(rtl.glob('*.cpp'))]
 if backend!='firmware':cpp += [vr/'verilated.cpp',vr/'verilated_threads.cpp']
 for i,src in enumerate(cpp):
  obj=work/f'capture{i}.o';subprocess.run([cxx,*flags,'-std=c++17','-I'+str(rtl),'-I'+str(vr),'-I'+str(vr/'vltstd'),'-c',str(src),'-o',str(obj)],check=True);objects.append(str(obj))
 name=out/f'pico1715-{backend}{".so" if a.native else ".mjs"}'
 link=['-shared'] if a.native else ['--no-entry','-sMODULARIZE=1','-sEXPORT_ES6=1','-sENVIRONMENT=web,worker,node','-sALLOW_MEMORY_GROWTH=1','-sSTACK_SIZE=1048576','-sEXPORTED_RUNTIME_METHODS=HEAPU8,ENV','-sEXPORTED_FUNCTIONS='+json.dumps(['_malloc','_free']+['_p1715_'+n for n in exports])]
 if not a.native and backend=='firmware':link+=['-sASYNCIFY=1','-sASYNCIFY_STACK_SIZE=131072']
 subprocess.run([cxx,'-O2',*objects,*link,'-o',str(name)],check=True)
 if a.probes and not a.native:
  obj=work/'probe.o'
  subprocess.run([cc,*flags,'-std=c11','-c',str(ROOT/'tools/classic_probe.c'),'-o',str(obj)],check=True)
  probe_flags=['-sEXIT_RUNTIME=1','-sNODERAWFS=1','-sENVIRONMENT=node','-sALLOW_MEMORY_GROWTH=1','-sSTACK_SIZE=1048576','--pre-js',str(ROOT/'tools/browser/probe-env.js')]
  if backend=='firmware':probe_flags+=['-sASYNCIFY=1','-sASYNCIFY_STACK_SIZE=131072']
  subprocess.run([cxx,'-O2',str(obj),*objects[1:],*probe_flags,'-o',str(work/'probe.cjs')],check=True)

if not a.native:
 shutil.copyfile(ROOT/'tools/browser/experiment.mjs',out/'experiment.mjs')
 def rev(path):return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
 for name,path in {'LICENSE':ROOT/'LICENSE','chips-LICENSE':dac/'third_party/cpu/chips/LICENSE','verilator-LICENSE':Path('/usr/share/doc/verilator/copyright')}.items():shutil.copyfile(path,out/name)
 files=[p for p in out.iterdir() if p.is_file() and p.name!='manifest.json']
 manifest={'schema':1,'abi':2,'pico':rev(ROOT),'dac':rev(dac),'dirty':any(subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True) for repo in (ROOT,dac)),'compiler':subprocess.check_output([a.emcc,'--version'],text=True).splitlines()[0],'verilator':subprocess.check_output(['verilator','--version'],text=True).strip(),'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
else:
 def rev(path):return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
 manifest={'schema':1,'abi':2,'pico':rev(ROOT),'dac':rev(dac),'dirty':any(subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True) for repo in (ROOT,dac)),'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('pico1715-*.so')}}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
