#!/usr/bin/env python3
"""ROM-free CI smoke: a tiny original Z80 program uses the RTL/firmware mailbox."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix='p1715-firmware-') as name:
    root = Path(name)
    # DI; LD A,80; OUT (5),A; LD A,CF; OUT (5),A; LD A,FF;
    # OUT (4),A; IN A,(4); HALT; JR HALT. No copyrighted boot ROM.
    program = bytes.fromhex('f3 3e 80 d3 05 3e cf d3 05 3e ff d3 04 db 04 76 18 fd')
    (root / 'rom').write_bytes(program.ljust(2048, b'\0'))
    (root / 'disk').write_bytes(bytes(819200))
    (root / 'output').mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith('PICO1715_')}
    env.update(PICO1715_CYCLES='10000', PICO1715_TIMED='0')
    result = subprocess.run([str(Path(sys.argv[1]).resolve()), str(root / 'rom'),
                             str(root / 'disk'), str(root / 'output')],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1, result.stderr  # deliberately no OS handoff
    report = json.loads(result.stdout)
    assert report['cycles'] == 10000 and report['writes'] == 0 and report['onboard'] == 1, report
    assert 'Firmware state=2 requests=4 sd_reads=1602 sd_writes=0 dirty=0 error=0' in result.stderr, result.stderr
    assert 'RTL requests=4 acks=0 reti=0' in result.stderr, result.stderr
    assert (root / 'output/disk.img').read_bytes() == (root / 'disk').read_bytes()
print('firmware RTL smoke PASS: original Z80 code, four mailbox requests, SD startup, unchanged media')
