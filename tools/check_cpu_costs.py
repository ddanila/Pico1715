#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure named cost profiles with the unchanged Z80/ROM/SCP BDOS workload."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from check_classic import ROM_HASH, DISK_HASH, digest, require
from classic_workload import install, small_file
from firmware_costs import stress_profile, stress_environment, stress_evidence, validate_stress
from firmware_costs import parse_costs, environment, evidence

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
for key in ('dac','rom','disk','out'):
    p.add_argument('--'+key, required=True, type=Path)
p.add_argument('--profile', action='append', required=True, help='name=poll,field,read,write,commit,snapshot')
p.add_argument('--sd-write-delay-us', type=int, default=5000)
p.add_argument("--stress-profile", type=Path)
a = p.parse_args()
stress = stress_profile(json.loads(a.stress_profile.read_text()) if a.stress_profile else {})
profiles = {}
for value in a.profile:
    name, sep, specification = value.partition('=')
    if not sep or not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in name) or name in profiles:
        p.error('profiles require unique lowercase names followed by = and six costs')
    try: profiles[name] = parse_costs(specification)
    except argparse.ArgumentTypeError as error: p.error(str(error))
if not 0 <= a.sd_write_delay_us <= 1000000: p.error('invalid SD delay')
dac,rom,disk,out = (getattr(a,k).resolve() for k in ('dac','rom','disk','out'))
pin = json.loads((ROOT/'docs/sources.json').read_text())['dac']['commit']
require(subprocess.check_output(['git','-C',str(dac),'rev-parse','HEAD'],text=True).strip()==pin, 'unqualified DAC revision')
for command in (['diff','--quiet'],['diff','--cached','--quiet']):
    subprocess.run(['git','-C',str(dac),*command],check=True)
require(digest(rom)==ROM_HASH and digest(disk)==DISK_HASH,'unqualified external ROM/image')
out.mkdir(parents=True,exist_ok=False)
names = ('tools/check_cpu_costs.py','tools/firmware_costs.py','tools/check_classic.py',
         'tools/classic_probe.c','tools/classic_workload.py','tools/build_cosim.py',
         'tools/firmware_host/bridge.cpp','tools/firmware_host/host_hal.c','tools/firmware_host/host_hal.h',
         'firmware/service.c','firmware/service.h','firmware/platform.h','firmware/store.c','firmware/store.h',
         'model/controller.c','model/controller.h','hardware/rtl/firmware_cosim_top.v',
         'hardware/rtl/pico1715_top.v','hardware/rtl/bus_frontend.v','hardware/rtl/irq_frontend.v')
def hashes(): return {name:digest(ROOT/name) for name in names}
sources = hashes()
with (out/'build.log').open('w') as log:
    subprocess.run([sys.executable,str(ROOT/'tools/build_cosim.py'),'--firmware','--dac',str(dac),
                    '--out',str(out/'build')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
fixture,payload=install(disk.read_bytes());media=out/'workload.img';media.write_bytes(fixture)
media_hash=digest(media)
cases={}
for name,costs in profiles.items():
    folder=out/name;folder.mkdir()
    env={k:v for k,v in os.environ.items() if not k.startswith('PICO1715_')}
    env['PICO1715_LOSS_TRACE']=str(folder/'first-loss.csv')
    env.update(stress_environment(stress))
    env.update(environment(costs));env.update(PICO1715_TIMED='0',PICO1715_SD_WRITE_DELAY_US=str(a.sd_write_delay_us))
    proc=subprocess.run([str(out/'build/classic-probe'),str(rom),str(media),str(folder),'PICOTEST\r'],
                        env=env,capture_output=True,text=True,timeout=300)
    (folder/'stdout.txt').write_text(proc.stdout);(folder/'stderr.txt').write_text(proc.stderr)
    require(proc.returncode in (0,1),f'{name}: probe execution error: {proc.stderr}')
    probe=json.loads(proc.stdout);cost=evidence(proc.stderr)
    stress_stats=stress_evidence(proc.stderr)
    validate_stress(stress_stats,cost['calls'])
    require(stress_stats['config']==stress,'wrong stress configuration')
    require(cost['config']==list(costs),f'{name}: wrong cost profile')
    screen=(folder/'screen.txt').read_text()
    try: contents=small_file((folder/'disk.img').read_bytes(),b'PICOTESTTXT')==payload*20
    except (ValueError,RuntimeError,AssertionError): contents=False
    checks={'handoff':probe['rom_handoff_target']==0xd900,
            'keyboard':probe['keyboard_bytes']==probe['sio_reads']==18 and not probe['sio_errors'],
            'guest': 'PICO READ WRITE OK' in screen and 'PICO TEST FAILED' not in screen and 'BIOS ERR' not in screen,
            'contents':contents, 'writes':probe['writes']>0 and not probe['rejected_writes'],
            'bytes':not any(probe[k] for k in ('overruns','underflows','tx_overruns','tx_underruns')),
            'watchdog':not cost['faults']}
    cases[name]={'stress':stress_stats,'costs':cost,'probe':probe,'checks':checks,'accepted':all(checks.values()),
                 'returncode':proc.returncode,'output_sha256':digest(folder/'disk.img'),
                 'screen':'\n'.join(line.rstrip() for line in screen.splitlines()).rstrip()}
    (folder/'report.json').write_text(json.dumps(cases[name],indent=2)+'\n')
    print(name, 'accepted' if cases[name]['accepted'] else 'rejected',
          [key for key,ok in checks.items() if not ok], flush=True)
    require(digest(media)==media_hash,'input workload modified')
require(hashes()==sources and digest(rom)==ROM_HASH and digest(disk)==DISK_HASH,'inputs changed')
report={'schema':1,'profile':'stock-z80-firmware-cost-experiments','dac_commit':pin,
        'rom_sha256':ROM_HASH,'disk_sha256':DISK_HASH,'rom_patched':False,'bios_patched':False,
        'hardware_executed':False,'sd_write_delay_us':a.sd_write_delay_us,
        'source_sha256':sources,'cases':cases,
        'limitations':'Injected aggregate work costs and cooperative lock contention, not measured Pico execution. '
                       'Each rejected case is retained; successful process exit means experiments completed, not that all profiles passed. '
                       'No claim of exhaustive or monotonic timing limits, actual cache behavior or physical bus qualification.'}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
