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
from firmware_costs import environment, evidence, stress_profile, stress_environment, stress_evidence, validate_stress

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
                ('burst', (1,4,8,8,4,8), 0), ('burst-reset', (1,4,8,8,4,8), 2), ('burst-reset-writeback', (1,4,8,8,4,8), 3),
                ('burst-overload', (1,4,8,8,4,8), 0), ('burst-irq-overload', (1,4,8,8,4,8), 0), ('tx-staging', (1,4,8,8,4,8), 0), ('reset-write', (1,4,8,8,4,8), 2),
                ('reset', (1,4,1,1,4,8), 1), ('reset-writeback', (1,4,1,1,4,8), 3), ('overload', (0,0,100,0,0,0), 0), ('startup-slow', (100,0,0,0,0,0), 0)]
    for name, costs, reset in profiles:
        folder = root/name; folder.mkdir()
        env = {k:v for k,v in os.environ.items() if not k.startswith('PICO1715_')}
        env['PICO1715_LOSS_TRACE']=str(folder/'first-loss.csv')
        profile_path = Path(__file__).parent/'stress'/('overload.json' if name in ('burst-overload','burst-irq-overload') else 'combined.json')
        stress = stress_profile(json.loads(profile_path.read_text()) if name.startswith('burst') else {})
        selected_rom=root/'rom'
        if name=='burst-irq-overload':
            stress['extra_us'][3]=120
            # IM1 and a minimal EI/RETI handler exercise IACK after mailbox isolation.
            body=bytes.fromhex('f3 31 00 f0 ed 56 3e 10 d3 05 3e 83 d3 05 fb')+program[4:]
            assert 0x100+len(body)<=0x300
            irq_rom=bytearray(rom)
            irq_rom[:0x300]=bytes(0x300)
            irq_rom[:3]=bytes.fromhex('c3 00 01')
            irq_rom[0x38:0x3b]=bytes.fromhex('fb ed 4d')
            irq_rom[0x100:0x100+len(body)]=body
            selected_rom=root/'irq-rom';selected_rom.write_bytes(irq_rom)
        env.update(stress_environment(stress))
        env.update(environment(costs));env.update(PICO1715_CYCLES='1000000', PICO1715_TIMED='0',
                                                  PICO1715_SD_WRITE_DELAY_US='5000', PICO1715_RESET_PHASE=str(reset))
        result = subprocess.run([str(binary), str(selected_rom), str(root/'disk'), str(folder)],
                                capture_output=True, text=True, env=env, timeout=60)
        assert result.returncode == 1, (name,result.stderr)  # no stock-ROM handoff
        report = json.loads(result.stdout); c = evidence(result.stderr)
        stress_stats = stress_evidence(result.stderr)
        validate_stress(stress_stats,c['calls'])
        assert stress_stats['index_resets']==1+bool(reset)
        assert stress_stats['config']==stress
        if name.startswith('burst'):
            assert stress_stats['hits'][3], stress_stats
            if name not in ('burst-overload','burst-irq-overload'):
                assert all(stress_stats['hits']), stress_stats
                assert (stress_stats['sd_min_us'],stress_stats['sd_max_us'])==(200,20000), stress_stats
        rows = list(csv.DictReader((folder/'first-loss.csv').open()))
        assert len(rows) <= 320
        if report['overruns'] or report['tx_underruns']:
            assert rows and any(int(r['overruns']) or int(r['underruns']) for r in rows)
            assert all(int(b['us']) >= int(a['us']) for a,b in zip(rows,rows[1:]))
        else: assert not rows
        # Capture is observational: run one normal profile again without it.
        if name in ('combined','burst'):
            plain = root/('untraced-'+name);plain.mkdir()
            plain_env = dict(env);plain_env.pop('PICO1715_LOSS_TRACE')
            check = subprocess.run([str(binary),str(root/'rom'),str(root/'disk'),str(plain)],
                                   capture_output=True,text=True,env=plain_env,timeout=60)
            assert (check.returncode,check.stdout,check.stderr)==(result.returncode,result.stdout,result.stderr)
            for artifact in ('ram.bin','disk.img','screen.txt'):
                assert (plain/artifact).read_bytes()==(folder/artifact).read_bytes()

        assert c['config'] == list(costs), (name,c)
        if name in ('burst-overload','burst-irq-overload'):
            if name=='burst-irq-overload': assert not stress_stats['fault_iacks'] and c['faults'], (stress_stats,c)
            assert report['tx_underruns'] or c['faults'], (report,c)
            saved=(folder/'disk.img').read_bytes()
            assert saved in (bytes(819200),bytes([0x63])*1024+bytes(819200-1024))
            assert report['writes'] in (0,1)
            assert saved == (bytes([0x63])*1024+bytes(819200-1024) if report['writes'] else bytes(819200))
            # Cold remount the exported logical disk with the injected overload removed.
            recovery=root/('recovery-'+name);recovery.mkdir()
            clean={k:v for k,v in env.items() if not k.startswith('PICO1715_STRESS_') and k!='PICO1715_LOSS_TRACE'}
            recovered=subprocess.run([str(binary),str(root/'rom'),str(folder/'disk.img'),str(recovery)],
                                     capture_output=True,text=True,env=clean,timeout=60)
            assert recovered.returncode==1, recovered.stderr
            q=json.loads(recovered.stdout)
            assert not evidence(recovered.stderr)['faults'] and q['writes']==1
            assert not any(q[k] for k in ('overruns','underflows','tx_overruns','tx_underruns','rejected_writes'))
            assert (recovery/'disk.img').read_bytes()==bytes([0x63])*1024+bytes(819200-1024)
            assert (folder/'disk.img').read_bytes()==saved
            stress_stats['recovery']=q
            stress_stats['sector_atomicity_checked']=True
        elif name in ('overload', 'startup-slow'):

            assert c['faults'] and c['calls'][2 if name == 'overload' else 0] and c['yields'], c
        else:
            assert not c['faults'] and report['writes'] == 1, (name,report,c)
            assert not any(report[k] for k in ('overruns','underflows','tx_overruns','tx_underruns','rejected_writes')), (name,report)
            assert all(c['calls']), (name,c)
            assert (folder/'disk.img').read_bytes() == bytes([0x63])*1024+bytes(819200-1024)
            ram = (folder/'ram.bin').read_bytes()
            assert ram[0x9000:0x900a] == bytes.fromhex('a1 a1 a1 fe 00 00 01 03 da 4e')
            assert ram[0x9100:0x9506] == (field if reset == 3 else empty_field), name
            assert ram[0x9700:0x9b06] == empty_field, name
            assert report['resets'] == bool(reset)
            if reset: assert report['reset_image_unchanged'] == 1
            if reset == 3: assert 'resets_while_busy=1' in result.stderr
            if any(costs): assert c['yields'] and c['lock_wait_us'], c
        results[name] = {'probe':report, 'costs':c, 'stress':stress_stats}
assert results['combined']['probe']['wait_ticks'] > results['zero']['probe']['wait_ticks']
print('Z80 cost smoke PASS: real IN/OUT, all cost sites, SD, contention, reset, watchdog')
if len(sys.argv)>2:
    with Path(sys.argv[2]).open('x') as stream: json.dump(results,stream,indent=2);stream.write('\n')
