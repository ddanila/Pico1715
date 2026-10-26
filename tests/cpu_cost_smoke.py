#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original Z80 program exercises all cost sites, writeback, reset and overload."""
import csv
import binascii
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from firmware_costs import environment, evidence

binary = Path(sys.argv[1]).resolve()
program = bytearray(bytes.fromhex('f3 31 00 f0'))  # DI; SP=F000

def out(port, value):
    program.extend((0x3e, value, 0xd3, port))

def arm():
    out(4, 0xa5); out(4, 0x85)

def transfer(address, count, write=False):
    program.extend((0x21, address & 255, address >> 8, 0x11, count & 255, count >> 8))
    start = len(program)
    program.extend((0x7e, 0xd3, 0) if write else (0xdb, 2, 0x77))
    program.extend((0x23, 0x1b, 0x7a, 0xb3, 0x20))
    program.append((start-len(program)-1) & 255)

out(0x20, 0xef); out(6, 4)
arm(); transfer(0x9000, 10)
arm(); transfer(0x9100, 1030)
out(4, 0xb4); transfer(0x300, 1030, True)
program.extend(bytes(20))  # allow the final transmit byte to serialize
out(4, 0xbf)
arm(); transfer(0x9600, 10)
arm(); transfer(0x9700, 1030)  # real reads overlap journal writeback
program.extend(bytes.fromhex('76 18 fd'))
field = b'\xa1\xa1\xa1\xfb' + bytes([0x63])*1024
field += binascii.crc_hqx(field, 0xffff).to_bytes(2, 'big')
empty_field = b'\xa1\xa1\xa1\xfb' + bytes(1024)
empty_field += binascii.crc_hqx(empty_field, 0xffff).to_bytes(2, 'big')
rom = program.ljust(0x300, b'\0') + field
rom = rom.ljust(2048, b'\0')
assert len(rom) == 2048
results = {}
with tempfile.TemporaryDirectory(prefix='p1715-cpu-cost-') as name:
    root = Path(name); (root/'rom').write_bytes(rom); (root/'disk').write_bytes(bytes(819200))
    profiles = [('zero', (0,0,0,0,0,0), 0), ('combined', (1,4,1,1,4,8), 0), ('read-ahead', (1,4,8,1,4,8), 0),
                ('tx-staging', (1,4,8,8,4,8), 0), ('reset-write', (1,4,8,8,4,8), 2),
                ('reset', (1,4,1,1,4,8), 1), ('reset-writeback', (1,4,1,1,4,8), 3), ('overload', (0,0,100,0,0,0), 0), ('startup-slow', (100,0,0,0,0,0), 0)]
    for name, costs, reset in profiles:
        folder = root/name; folder.mkdir()
        env = {k:v for k,v in os.environ.items() if not k.startswith('PICO1715_')}
        env['PICO1715_LOSS_TRACE']=str(folder/'first-loss.csv')
        env.update(environment(costs));env.update(PICO1715_CYCLES='1000000', PICO1715_TIMED='0',
                                                  PICO1715_SD_WRITE_DELAY_US='5000', PICO1715_RESET_PHASE=str(reset))
        result = subprocess.run([str(binary), str(root/'rom'), str(root/'disk'), str(folder)],
                                capture_output=True, text=True, env=env, timeout=60)
        assert result.returncode == 1, (name,result.stderr)  # no stock-ROM handoff
        report = json.loads(result.stdout); c = evidence(result.stderr)
        rows = list(csv.DictReader((folder/'first-loss.csv').open()))
        assert len(rows) <= 320
        if report['overruns'] or report['tx_underruns']:
            assert rows and any(int(r['overruns']) or int(r['underruns']) for r in rows)
            assert all(int(b['us']) >= int(a['us']) for a,b in zip(rows,rows[1:]))
        else: assert not rows
        # Capture is observational: run one normal profile again without it.
        if name == 'combined':
            plain = root/'untraced';plain.mkdir()
            plain_env = dict(env);plain_env.pop('PICO1715_LOSS_TRACE')
            check = subprocess.run([str(binary),str(root/'rom'),str(root/'disk'),str(plain)],
                                   capture_output=True,text=True,env=plain_env,timeout=60)
            assert (check.returncode,check.stdout,check.stderr)==(result.returncode,result.stdout,result.stderr)
            for artifact in ('ram.bin','disk.img','screen.txt'):
                assert (plain/artifact).read_bytes()==(folder/artifact).read_bytes()

        assert c['config'] == list(costs), (name,c)
        if name in ('overload', 'startup-slow'):
            assert c['faults'] and c['calls'][2 if name == 'overload' else 0] and c['yields'], c
        else:
            assert not c['faults'] and report['writes'] == 1, (name,report,c)
            assert not any(report[k] for k in ('overruns','underflows','tx_overruns','tx_underruns','rejected_writes')), (name,report)
            assert all(c['calls']), (name,c)
            assert (folder/'disk.img').read_bytes() == bytes([0x63])*1024+bytes(819200-1024)
            ram = (folder/'ram.bin').read_bytes()
            assert ram[0x9000:0x900a] == bytes.fromhex('a1 a1 a1 fe 00 00 01 03 da 4e')
            assert ram[0x9100:0x9506] == (field if name == 'reset-writeback' else empty_field), name
            assert ram[0x9700:0x9b06] == empty_field, name
            assert report['resets'] == bool(reset)
            if reset: assert report['reset_image_unchanged'] == 1
            if reset == 3: assert 'resets_while_busy=1' in result.stderr
            if any(costs): assert c['yields'] and c['lock_wait_us'], c
        results[name] = {'probe':report, 'costs':c}
assert results['combined']['probe']['wait_ticks'] > results['zero']['probe']['wait_ticks']
print('Z80 cost smoke PASS: real IN/OUT, all cost sites, SD, contention, reset, watchdog')
if len(sys.argv)>2:
    with Path(sys.argv[2]).open('x') as stream: json.dump(results,stream,indent=2);stream.write('\n')
