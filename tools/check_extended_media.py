#!/usr/bin/env python3
"""Bounded external-media survey and persistent 96-record CP/M workloads."""
import argparse, hashlib, json, os, subprocess
from pathlib import Path
from classic_workload import install, small_file
ROOT=Path(__file__).resolve().parents[1]
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
    if not ok: raise RuntimeError(msg)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('dac','rom','images','out'): ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--report',type=Path,default=ROOT/'reports/extended-media.json')
    a=ap.parse_args(); a.out=a.out.resolve(); a.dac=a.dac.resolve()
    catalog=json.loads((ROOT/'tests/extended-media-inputs.json').read_text())
    require(digest(a.rom)==catalog['rom_sha256'],'ROM hash mismatch')
    sha=subprocess.check_output(['git','-C',str(a.dac),'rev-parse','HEAD'],text=True).strip()
    require(sha==catalog['dac_commit'],'DAC pin mismatch')
    require(not subprocess.check_output(['git','-C',str(a.dac),'status','--porcelain','--untracked-files=no'],text=True).strip(),'DAC tracked changes')
    inputs={name:a.images/name for name in catalog['images']}
    for name,p in inputs.items(): require(digest(p)==catalog['images'][name]['sha256'],name+': hash mismatch')
    a.out.mkdir(parents=True,exist_ok=False); binary=a.out/'classic-probe'
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(a.dac),str(ROOT/'tools/classic_probe.c'),str(ROOT/'model/controller.c'),str(a.dac/'machines/robotron1715/pc1715.c'),str(a.dac/'common/cpu/z80.c'),str(a.dac/'common/trace/trace.c'),'-o',str(binary)],check=True)
    env={k:v for k,v in os.environ.items() if not k.startswith('PICO1715_')}; env.update(PICO1715_TIMED='0',PICO1715_CYCLES='100000000')
    results=[]
    def run(name,media,command,readonly=False):
        before=digest(media); folder=a.out/name; folder.mkdir()
        cmd=[str(binary),str(a.rom.resolve()),str(media.resolve()),str(folder),command]
        if readonly: cmd.append('readonly')
        r=subprocess.run(cmd,check=True,capture_output=True,text=True,env=env,timeout=90)
        stats=json.loads(r.stdout); screen=(folder/'screen.txt').read_text()
        require(digest(media)==before,name+': input modified')
        require(all(stats[k]==0 for k in ('overruns','underflows','drops','tx_overruns','tx_underruns','sio_errors')),name+': transport errors')
        output=folder/'disk.img'
        if readonly: require(digest(output)==before,name+': readonly output changed')
        row={'case':name,'input_sha256':before,'output_sha256':digest(output),'stats':stats,'screen':'\n'.join(x.rstrip() for x in screen.splitlines()).strip()}
        results.append(row); print(name,flush=True)
        return output,stats,screen
    for name,p in inputs.items():
        _,stats,screen=run(p.stem+'-boot',p,'DIR\r',True)
        prompt='A>DIR' in screen and stats['keyboard_bytes']>0
        require(prompt==catalog['images'][name]['prompt_observed'],name+': boot behavior changed; investigate')
        results[-1]['qualification']='prompt observed' if prompt else 'unqualified: no prompt within 100M cycles'
        if not prompt: continue
        fixture,payload=install(p.read_bytes(),records=96,block=None)
        media=a.out/(p.stem+'-fixture.img'); media.write_bytes(fixture)
        for round_ in range(3):
            prefix=f'{p.stem}-round{round_+1}'
            media,stats,screen=run(prefix+'-write-read',media,'PICOTEST\r')
            require('PICO READ WRITE OK' in screen and stats['writes']>0 and stats['rejected_writes']==0,prefix+': workload failed')
            require(small_file(media.read_bytes(),b'PICOTESTTXT')==payload*96,prefix+': independent payload mismatch')
            readback,stats,screen=run(prefix+'-cold-read',media,'TYPE PICOTEST.TXT\r',True)
            require('Pico1715 independent stock BIOS test.' in screen and stats['writes']==0,prefix+': cold read failed')
            require(small_file(readback.read_bytes(),b'PICOTESTTXT')==payload*96,prefix+': cold payload mismatch')
            media,stats,screen=run(prefix+'-delete',media,'ERA PICOTEST.TXT\rDIR PICOTEST.TXT\r')
            require('NO FILE' in screen.upper() and stats['writes']>0 and stats['rejected_writes']==0,prefix+': delete failed')
            _,_,screen=run(prefix+'-cold-deleted',media,'DIR PICOTEST.TXT\r',True)
            require('NO FILE' in screen.upper(),prefix+': delete not persistent')
    for name,p in inputs.items(): require(digest(p)==catalog['images'][name]['sha256'],name+': original changed')
    report={'schema':1,'hardware_executed':False,'backend':'native functional controller; scheduled 250 kbit/s bytes; transaction waits; no RTL or MCU cost model','dac_commit':sha,'records_per_workload':96,'rounds_per_bootable_image':3,'limitations':['Both prompt-bearing images identify SCP version 0006, not distinct OS versions.','Four non-prompt images remain unqualified; this does not identify the cause.','Repeated payload checks do not prove arbitrary data-pattern or power-loss correctness.'],'cases':results,'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'tools/classic_workload.py',ROOT/'tools/classic_probe.c',ROOT/'model/controller.c',ROOT/'tests/extended-media-inputs.json']}}
    a.report.write_text(json.dumps(report,indent=2)+'\n'); print('PASS',len(results),'cases')
if __name__=='__main__': main()
