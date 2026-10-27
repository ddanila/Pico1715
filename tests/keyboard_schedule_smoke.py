#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Actual CPU/SIO check: disabled/full bytes are rejected, not replayed."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp);(d/'out').mkdir()
 # Enable receiver then halt without consuming any bytes.
 (d/'rom').write_bytes(bytes.fromhex('f3 3e 03 d3 0e 3e c1 d3 0e 76 18 fd').ljust(2048,b'\0'))
 (d/'disk').write_bytes(bytes(819200))
 (d/'events').write_text('0 99\n1000 224\n2000 65\n3000 224\n4000 66\n')
 env={k:v for k,v in os.environ.items() if not k.startswith('PICO1715_')}
 env.update(PICO1715_KEY_SCHEDULE=str(d/'events'),PICO1715_CYCLES='10000')
 r=subprocess.run([str(Path(sys.argv[1]).resolve()),str(d/'rom'),str(d/'disk'),str(d/'out')],env=env,capture_output=True,text=True,check=False)
 assert r.returncode==1,r.stderr
 s=json.loads(r.stdout)
 assert (s['key_attempted'],s['key_accepted'],s['key_disabled'],s['key_full'],s['key_pending'],s['key_late'])==(5,3,1,1,0,0),s
 assert s['sio_errors']!=0,s
print('CPU/SIO asynchronous schedule PASS')
