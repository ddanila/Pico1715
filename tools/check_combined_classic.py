#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Qualify classic CP/M storage through real combined firmware/RTL, with host file oracle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from cycle_trace import decode
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary',type=Path,required=True)
p.add_argument('--cpm',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--timeout',type=int,default=1200,help='wall-clock seconds per guest run')
a=p.parse_args();cpm=a.cpm.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(cpm/'tools'))
from media import inspect,add
base=(cpm/'out/cpm-plus-1715.img').read_bytes();program=(cpm/'build/p1715test.cim').read_bytes()
if (0,'P1715TST.COM') not in inspect(base):base=add(base,'P1715TST.COM',program)
original={k:f.data for k,f in inspect(base).items()}
env={k:v for k,v in os.environ.items() if not k.startswith('PICO1715_')}
env.update(PICO1715_KEY_START='30000000',PICO1715_CYCLES='400000000')
results=[]
def run(name,image,command,marker,readonly=False):
 d=out/name;d.mkdir();source=d/'input.img';source.write_bytes(image)
 with (d/'stdout.log').open('w') as stdout,(d/'stderr.log').open('w') as stderr:
  subprocess.run([str(a.binary.resolve()),str(cpm/'build/test.rom'),str(source),str(d),command,*(['readonly'] if readonly else [])],env=env|{'PICO1715_STOP_TEXT':marker,'PICO1715_COMBINED_TRACE':str(d/'capture.p1715')},stdout=stdout,stderr=stderr,check=True,timeout=a.timeout)
 assert marker in (d/'screen.txt').read_text(),name
 data=(d/'disk.img').read_bytes();files=inspect(data)
 for key,value in original.items():assert files[key].data==value,(name,key)
 if readonly:assert image==data
 header,cycles=decode((d/'capture.p1715').read_bytes())
 assert cycles and header.clock_hz==50000000
 results.append(dict(case=name,records=len(cycles),capture_header=header.__dict__,disk_sha256=hashlib.sha256(data).hexdigest(),capture_sha256=hashlib.sha256((d/'capture.p1715').read_bytes()).hexdigest()))
 return data
run('info',base,'P1715TST I\r','P1715TEST INFO PASS')
written=run('write',base,'P1715TST W\r','P1715TEST WRITE PASS')
expected=b''.join(bytes(i^j for j in range(128)) for i in range(256));expected=b'P1715TEST-v1\0\1\2\3'+expected[16:]
assert inspect(written)[(0,'P1715TST.DAT')].data==expected
run('cold-verify',written,'P1715TST R\r','P1715TEST VERIFY PASS',True)
report=dict(schema=1,hardware_executed=False,binary_sha256=hashlib.sha256(a.binary.read_bytes()).hexdigest(),cases=results,limitations='Synthetic bus receiver observations and unmeasured service costs; capture loss is reported, not waived. No physical timing or power-loss qualification.')
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print('combined classic PASS: boot, guest write, independent file preservation, cold verify, decoded captures')
