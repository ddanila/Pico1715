#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""ROM-free guest tests for the probe's real SIO FIFO path (native or RTL)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

binary = Path(sys.argv[1]).resolve()
results = {}
with tempfile.TemporaryDirectory(prefix='p1715-sio-') as name:
    root = Path(name)
    (root/'disk').write_bytes(bytes(819200))
    # DI; configure CTC0 counter; select SIO A WR3; enable receiver;
    # HL=9000; poll RR0; consume FIFO with IN (0C); store successive bytes.
    setup = bytes.fromhex('f3 3e d7 d3 08 3e 01 d3 08 3e 03 d3 0e 3e c1 d3 0e 21 00 90')
    loop = bytes.fromhex('db 0e e6 01 28 fa db 0c 77 23 18 f4')
    for enabled in (False, True):
        program = bytearray(setup + loop)
        if not enabled:
            program[14] = 0xc0  # clear receive-enable only
        (root/'rom').write_bytes(program.ljust(2048, b'\0'))
        output = root/('enabled' if enabled else 'disabled')
        output.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith('PICO1715_')}
        env['PICO1715_CYCLES'] = '21000000'
        result = subprocess.run([str(binary), str(root/'rom'), str(root/'disk'), str(output), 'DIR\r'],
                                env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 1, result.stderr  # no OS handoff in synthetic ROM
        report = json.loads(result.stdout)
        assert report['onboard'] == 1 and report['sio_errors'] == 0, report
        assert report['ctc_writes'] == 2 and report['sio_writes'] == 2, report
        count = 8 if enabled else 0
        assert report['keyboard_bytes'] == report['sio_reads'] == count, report
        ram = (output/'ram.bin').read_bytes()
        assert ram[0x9000:0x9008] == (b'\xe0D\xe0I\xe0R\xe0\r' if enabled else bytes(8))
        assert (output/'disk.img').read_bytes() == (root/'disk').read_bytes()
        results['enabled' if enabled else 'disabled'] = report
print('onboard keyboard PASS: guest RX enable gates injection; eight FIFO bytes consumed; SD unchanged')

if len(sys.argv) > 2:
    with Path(sys.argv[2]).open("x") as stream:
        json.dump(results, stream, indent=2)
        stream.write("\n")
