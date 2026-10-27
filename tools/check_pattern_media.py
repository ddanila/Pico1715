#!/usr/bin/env python3
"""Indexed multi-extent, disk-full and corruption-detection guest tests."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
from pattern_workload import fixture,replace_program,nearly_full,read_file,record,DIRECTORY,BLOCK
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for n in ['binary','rom','disk','out']:ap.add_argument('--'+n,type=Path,required=True)
 ap.add_argument('--backend',choices=['native','shared-firmware-rtl'],required=True);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
 catalog=json.loads((ROOT/'tests/extended-media-inputs.json').read_text());assert digest(a.rom)==catalog['rom_sha256'];assert digest(a.disk)==catalog['images']['anasana.cpm']['sha256']
 original=digest(a.disk);a.out.mkdir(parents=True,exist_ok=False);env={k:v for k,v in os.environ.items() if not k.startswith('PICO1715_')};env['PICO1715_TIMED']='0';cases=[]
 def run(name,data,marker,readonly=False):
  source=a.out/(name+'.img');source.write_bytes(data);folder=a.out/name;folder.mkdir();before=digest(source)
  r=subprocess.run([str(a.binary.resolve()),str(a.rom.resolve()),str(source.resolve()),str(folder.resolve()),'PICOTEST\r',*(['readonly'] if readonly else [])],env=env,text=True,capture_output=True,check=True,timeout=180)
  stats=json.loads(r.stdout);screen=(folder/'screen.txt').read_text();assert marker in screen,(name,screen)
  assert all(stats[k]==0 for k in ['overruns','underflows','drops','tx_overruns','tx_underruns','sio_errors']),stats
  assert digest(source)==before
  output=(folder/'disk.img').read_bytes()
  if readonly:assert output==data
  cases.append(dict(case=name,input_sha256=before,output_sha256=hashlib.sha256(output).hexdigest(),stats=stats,marker=marker));print(name,flush=True)
  return output
 image=a.disk.read_bytes()
 for seed in [83,166]:
  output=run(f'pattern-{seed}',fixture(image,256,seed),'PICO PATTERN OK')
  expected=b''.join(record(i,seed) for i in range(256));assert read_file(output)==expected
  verify=replace_program(output,records=256,seed=seed,verify_only=True)
  run(f'cold-read-{seed}',verify,'PICO PATTERN OK',True)
  if seed==83:
   corrupt=bytearray(verify);offset=next(i for i in range(DIRECTORY,DIRECTORY+4096,32) if corrupt[i:i+12]==b'\0PICOTESTTXT')
   block=int.from_bytes(corrupt[offset+16:offset+18],'little');corrupt[DIRECTORY+block*BLOCK+40]^=1
   run('corrupt-negative',bytes(corrupt),'PICO PATTERN FAILED',True)
 full=nearly_full(fixture(image,256,83,expect_full=True),10)
 output=run('disk-full',full,'PICO DISK FULL OK');assert read_file(output)==b''.join(record(i) for i in range(160))
 run('disk-full-cold-read',replace_program(output,records=160,verify_only=True),'PICO PATTERN OK',True)
 assert digest(a.disk)==original
 report=dict(schema=1,hardware_executed=False,backend=a.backend,binary_sha256=digest(a.binary),rom_sha256=digest(a.rom),disk_sha256=original,cases=cases,source_sha256={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'tools/pattern_workload.py',ROOT/'tools/classic_probe.c']})
 a.report.write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(cases))
if __name__=='__main__':main()
