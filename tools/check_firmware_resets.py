#!/usr/bin/env python3
"""Boot stock software through delayed firmware and reset during active work."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from check_classic import ROM_HASH, DISK_HASH, digest, require
from classic_workload import small_file
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
for name in ('dac', 'rom', 'disk', 'out'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
dac, rom, disk, out = (getattr(a, k).resolve() for k in ('dac', 'rom', 'disk', 'out'))
pin = json.loads((ROOT / 'docs/sources.json').read_text())['dac']['commit']
require(subprocess.check_output(['git', '-C', str(dac), 'rev-parse', 'HEAD'], text=True).strip() == pin,
        'unqualified DAC revision')
for cmd in (['diff', '--quiet'], ['diff', '--cached', '--quiet']):
    require(subprocess.run(['git', '-C', str(dac), *cmd]).returncode == 0, 'dirty DAC dependency')
require(digest(rom) == ROM_HASH and digest(disk) == DISK_HASH, 'unqualified ROM/disk')
out.mkdir(parents=True, exist_ok=False)
names = ('tools/classic_probe.c', 'tools/build_cosim.py', 'tools/check_firmware_resets.py',
         'tools/check_classic.py', 'tools/classic_workload.py',
         'tools/firmware_host/bridge.cpp', 'tools/firmware_host/host_hal.c',
         'tools/firmware_host/host_hal.h', 'tools/cosim/bridge.h',
         'firmware/service.c', 'firmware/service.h', 'firmware/platform.h',
         'firmware/store.c', 'firmware/store.h', 'firmware/sd_spi.h',
         'model/controller.c', 'model/controller.h',
         'hardware/rtl/firmware_cosim_top.v', 'hardware/rtl/pico1715_top.v',
         'hardware/rtl/bus_frontend.v', 'hardware/rtl/irq_frontend.v')
sources = {name: digest(ROOT / name) for name in names}
with (out / 'build.log').open('w') as log:
    subprocess.run([sys.executable, str(ROOT / 'tools/build_cosim.py'), '--firmware',
                    '--dac', str(dac), '--out', str(out / 'build')],
                   check=True, stdout=log, stderr=subprocess.STDOUT, timeout=180)
results = {}
for phase, name in ((1, 'active-read'), (2, 'partial-sector-write'), (3, 'sd-writeback')):
    folder = out / name
    folder.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith('PICO1715_')}
    env.update(PICO1715_TIMED='0', PICO1715_SD_WRITE_DELAY_US='5000',
               PICO1715_RESET_PHASE=str(phase))
    command = 'DIR\r' if phase == 1 else 'SAVE 1 PICO.BIN\rDIR PICO.BIN\r'
    proc = subprocess.run([str(out / 'build/classic-probe'), str(rom), str(disk),
                           str(folder), command], env=env, capture_output=True,
                          text=True, timeout=180)
    (folder / 'stderr.txt').write_text(proc.stderr)
    require(proc.returncode == 0, f'{name}: {proc.stderr}')
    report = json.loads(proc.stdout)
    require(report['resets'] == report['reset_image_unchanged'] == 1, 'reset not verified')
    require(report['rom_handoff_target'] == 0xd900, 'stock ROM did not reboot OS')
    require(all(report[k] == 0 for k in ('overruns', 'underflows', 'tx_overruns', 'tx_underruns', 'rejected_writes')),
            'unexpected controller fault')
    screen = (folder / 'screen.txt').read_text()
    require('A>' in screen and 'BIOS ERR' not in screen, 'guest failed')
    storage = re.search(r'Storage delay_us=(\d+) yields=(\d+) resets_while_busy=(\d+)', proc.stderr)
    fw = re.search(r'Firmware state=(\d+) requests=(\d+) sd_reads=(\d+) sd_writes=(\d+) dirty=(\d+) error=(\d+)', proc.stderr)
    rtl = re.search(r'RTL requests=(\d+) acks=(\d+) reti=(\d+)', proc.stderr)
    require(storage and fw and rtl, 'missing combined-path evidence')
    report['storage_schedule'] = dict(zip(('delay_us', 'yields', 'resets_while_busy'), map(int, storage.groups())))
    report['firmware'] = dict(zip(('state', 'requests', 'sd_reads', 'sd_writes', 'dirty', 'error'), map(int, fw.groups())))
    report['rtl'] = dict(zip(('requests', 'acks', 'reti'), map(int, rtl.groups())))
    require(report['firmware']['state'] == 2 and report['firmware']['dirty'] == report['firmware']['error'] == 0,
            'firmware did not drain cleanly')
    require(report['firmware']['requests'] == report['rtl']['requests'], 'request counters differ')
    require(report['storage_schedule']['resets_while_busy'] == (1 if phase == 3 else 0), 'wrong reset boundary')
    if phase == 1:
        require('SCP-DOS  COM' in screen and digest(folder / 'disk.img') == DISK_HASH, 'read-only boot changed disk')
    else:
        require(report['writes'] > 0 and report['storage_schedule']['yields'] > 0, 'write path not exercised')
        require('PICO     BIN' in screen, 'saved file missing')
        require(small_file((folder / 'disk.img').read_bytes(), b'PICO    BIN') ==
                (folder / 'ram.bin').read_bytes()[256:512], 'saved bytes differ from guest memory')
    report['output_sha256'] = digest(folder / 'disk.img')
    report['screen'] = '\n'.join(line.rstrip() for line in screen.splitlines()).rstrip()
    results[name] = report
require(digest(rom) == ROM_HASH and digest(disk) == DISK_HASH, 'external inputs changed')
require(sources == {name: digest(ROOT / name) for name in names}, 'sources changed during test')
report = {'schema': 1, 'profile': 'stock-rom-firmware-reset-recovery', 'dac_commit': pin,
          'rom_sha256': ROM_HASH, 'disk_sha256': DISK_HASH,
          'rom_patched': False, 'bios_patched': False, 'hardware_timing_qualified': False,
          'source_sha256': sources, 'cases': results,
          'limitations': 'Host resets preserve Pico RAM; scripted power-loss/torn-write cases are in the separate fault suite. Deterministic SD yields are not instruction-level multicore timing.'}
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'3 stock-ROM firmware reset cases passed; report: {out / "report.json"}')
