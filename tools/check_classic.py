#!/usr/bin/env python3
"""Qualify the functional card with external, unchanged classic ROM and SCP."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import re
import subprocess
from classic_workload import install, small_file

ROOT = Path(__file__).resolve().parents[1]
ROM_HASH = '51cb80639b5667f2611da71ce7305061566cf3474bda7db6fc82709d08e46d01'
DISK_HASH = '16c4389cd8d4b7759ece28efdda5b9b1a04536cdeb3f644c583d953d5ecd55c4'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('dac', 'rom', 'disk', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--timed', action='store_true', help='scheduled 250 kbit/s bytes with transaction waits')
    parser.add_argument("--cosim", action="store_true", help="run normal I/O and IRQ/RETI through Verilated RTL")
    parser.add_argument('--firmware-cosim', action='store_true',
                        help='run shared Pico service/storage code against the board-level RTL')
    args = parser.parse_args()
    if args.firmware_cosim:
        args.cosim = True
    if args.cosim:
        args.timed = True
    dac, rom, disk, out = (getattr(args, k).resolve() for k in ('dac', 'rom', 'disk', 'out'))
    pin = json.loads((ROOT / 'docs/sources.json').read_text())['dac']['commit']
    revision = subprocess.check_output(['git', '-C', str(dac), 'rev-parse', 'HEAD'], text=True).strip()
    require(revision == pin, 'unqualified DAC revision')
    for cmd in (['diff', '--quiet'], ['diff', '--cached', '--quiet']):
        require(subprocess.run(['git', '-C', str(dac), *cmd]).returncode == 0, 'dirty DAC dependency')
    require(digest(rom) == ROM_HASH and digest(disk) == DISK_HASH, 'unqualified external ROM/image')
    out.mkdir(parents=True, exist_ok=False)
    binary = out / 'classic-probe'
    if args.cosim:
        subprocess.run([sys.executable, str(ROOT / 'tools/build_cosim.py'), '--dac', str(dac),
                        '--out', str(out / 'build'), *(['--firmware'] if args.firmware_cosim else [])], check=True, timeout=180)
        shutil.copyfile(out / 'build/classic-probe', binary)
        binary.chmod(0o755)
    else:
        subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(dac),
                        str(ROOT / 'tools/classic_probe.c'), str(ROOT / 'model/controller.c'),
                        str(dac / 'machines/robotron1715/pc1715.c'),
                        str(dac / 'common/cpu/z80.c'), str(dac / 'common/trace/trace.c'),
                        '-o', str(binary)], check=True, timeout=120)
    for source, name in [('LICENSE', 'dac-LICENSE'), ('NOTICE', 'dac-NOTICE'),
                         ('third_party/cpu/chips/LICENSE', 'chips-LICENSE')]:
        shutil.copyfile(dac / source, out / name)
    results = {}
    environment = {k: v for k, v in os.environ.items() if not k.startswith('PICO1715_')}
    if args.timed:
        environment['PICO1715_TIMED'] = '0'

    def run(name, media, command='', readonly=False, absent=False):
        folder = out / name
        folder.mkdir()
        cmd = [str(binary), str(rom), str(media), str(folder), command]
        if absent:
            cmd.append('absent')
        elif readonly:
            cmd.append('readonly')
        before = digest(media)
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=180 if args.cosim else 60, env=environment)
        (folder / 'stderr.txt').write_text(proc.stderr)
        require(proc.returncode == (1 if absent else 0), f'{name}: probe failed: {proc.stderr}')
        report = json.loads(proc.stdout)
        if args.cosim:
            stats = re.search(r'RTL requests=(\d+) acks=(\d+) reti=(\d+)', proc.stderr)
            require(stats is not None, 'missing RTL evidence')
            report['rtl'] = dict(zip(('requests', 'acks', 'reti'), map(int, stats.groups())))
            require(absent or all(report['rtl'][key] > 0 for key in ('requests', 'acks', 'reti')),
                    'RTL path not exercised')
        if args.firmware_cosim:
            stats = re.search(r'Firmware state=(\d+) requests=(\d+) sd_reads=(\d+) sd_writes=(\d+) dirty=(\d+) error=(\d+)', proc.stderr)
            require(stats is not None, 'missing firmware evidence')
            report['firmware'] = dict(zip(('state', 'requests', 'sd_reads', 'sd_writes', 'dirty', 'error'), map(int, stats.groups())))
            fw = report['firmware']
            require(fw['state'] == (0xe2 if absent else 2), 'unexpected firmware startup state')
            require(fw['dirty'] == fw['error'] == 0, 'firmware storage did not drain cleanly')
            require(absent or (fw['requests'] == report['rtl']['requests'] and fw['sd_reads'] >= 1602),
                    'firmware service/storage path not exercised')
            require(not report['writes'] or fw['sd_writes'] > 0, 'guest writes did not reach journaled SD')
        screen = (folder / 'screen.txt').read_text()
        require(report['rom_handoff_target'] == (0 if absent else 0xd900), f'{name}: wrong ROM handoff')
        require(digest(media) == before, f'{name}: input modified')
        require((readonly or 'BIOS ERR' not in screen) and 'PICO TEST FAILED' not in screen, f'{name}: guest failure')
        if args.timed:
            require(report['timed'] == 1, f'{name}: timed model not enabled')
            require(all(report[k] == 0 for k in ('overruns', 'underflows', 'tx_overruns', 'tx_underruns')),
                    f'{name}: unexpected timing fault')
        report['input_sha256'] = before
        report['output_sha256'] = digest(folder / 'disk.img')
        report['screen'] = '\n'.join(line.rstrip() for line in screen.splitlines()).rstrip()
        results[name] = report
        (folder / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        return folder, report, screen

    _, boot, screen = run('boot-dir', disk, 'DIR\r')
    require('A>' in screen and 'SCP-DOS  COM' in screen and boot['writes'] == 0, 'directory failed')
    require(boot['input_sha256'] == boot['output_sha256'], 'read altered media')
    folder, save, screen = run('save', disk, 'SAVE 1 PICO.BIN\rDIR PICO.BIN\r')
    require('PICO     BIN' in screen and save['writes'] > 0 and not save['rejected_writes'], 'SAVE failed')
    require(small_file((folder / 'disk.img').read_bytes(), b'PICO    BIN') ==
            (folder / 'ram.bin').read_bytes()[256:512], 'SAVE bytes differ from guest memory')
    _, _, screen = run('save-reboot', folder / 'disk.img', 'DIR PICO.BIN\r')
    require('PICO     BIN' in screen, 'saved file missing after cold boot')
    fixture, payload = install(disk.read_bytes())
    fixture_path = out / 'workload.img'
    fixture_path.write_bytes(fixture)
    folder, work, screen = run('bdos-read-write', fixture_path, 'PICOTEST\r')
    require('PICO READ WRITE OK' in screen and work['writes'] > 0 and not work['rejected_writes'], 'BDOS test failed')
    require(small_file((folder / 'disk.img').read_bytes(), b'PICOTESTTXT') == payload * 20,
            'independent file content comparison failed')
    _, reread, screen = run('read-after-reboot', folder / 'disk.img', 'TYPE PICOTEST.TXT\r')
    require('Pico1715 independent stock BIOS test.' in screen and reread['writes'] == 0, 'TYPE after reboot failed')
    erased, deletion, screen = run('delete', folder / 'disk.img', 'ERA PICOTEST.TXT\rDIR PICOTEST.TXT\r')
    require('NO FILE' in screen.upper() and deletion['writes'] > 0, 'delete failed')
    _, _, screen = run('delete-reboot', erased / 'disk.img', 'DIR PICOTEST.TXT\r')
    require('NO FILE' in screen.upper(), 'delete did not persist')
    _, protected, screen = run('write-protected', disk, 'SAVE 1 PICO.BIN\r', readonly=True)
    require(protected['writes'] == 0 and protected['input_sha256'] == protected['output_sha256'], 'write protection failed')
    require('BIOS ERR' in screen, 'protected write did not produce expected BIOS error')
    _, missing, _ = run('absent-media', disk, absent=True)
    require(missing['fields'] == missing['writes'] == missing['index_interrupts'] == 0,
            'absent media generated disk activity')
    require(missing['input_sha256'] == missing['output_sha256'], 'absent media changed image')
    require(digest(rom) == ROM_HASH and digest(disk) == DISK_HASH, 'external inputs changed')
    report = {'schema': 2, 'profile': 'pc1715-firmware-rtl-cosim' if args.firmware_cosim else 'pc1715-rtl-cosim' if args.cosim else 'pc1715-timed-card' if args.timed else 'pc1715-functional-card', 'dac_commit': revision,
              'rom_sha256': ROM_HASH, 'disk_sha256': DISK_HASH, 'rom_patched': False,
              'bios_patched': False, 'hardware_timing_qualified': False,
              'source_sha256': {name: digest(ROOT / name) for name in
                  ('model/controller.c', 'model/controller.h', 'tools/classic_probe.c',
                   'tools/classic_workload.py', 'tools/check_classic.py')}, 'cases': results}
    if args.cosim:
        report['source_sha256'].update({name: digest(ROOT / name) for name in
            ('hardware/rtl/bus_frontend.v', 'hardware/rtl/irq_frontend.v', 'hardware/rtl/cosim_top.v',
             'tools/cosim/bridge.cpp', 'tools/cosim/bridge.h', 'tools/build_cosim.py')})
        report['limitations'] = 'C disk/controller backend; transaction-level waits; RTL normal I/O and IRQ/RETI; not physical timing'
    if args.firmware_cosim:
        report['source_sha256'].update({name: digest(ROOT / name) for name in
            ('firmware/main.c', 'firmware/service.c', 'firmware/service.h', 'firmware/platform.h',
             'firmware/store.c', 'firmware/store.h', 'firmware/CMakeLists.txt',
             'tools/firmware_host/bridge.cpp', 'tools/firmware_host/host_hal.c',
             'tools/firmware_host/host_hal.h', 'hardware/rtl/pico1715_top.v',
             'hardware/rtl/firmware_cosim_top.v')})
        report['limitations'] = ('Host-compiled shared firmware service and storage code; simulated GPIO, '
            'microsecond clock, PSRAM and SD block device; cooperative storage worker; '
            '1 us service polling; DAC deferred I/O and synthetic keyboard; '
            'not ARM instruction execution, SPI/QMI electrical emulation, multicore contention or physical timing')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{len(results)} classic compatibility cases passed; report: {out / "report.json"}')


if __name__ == '__main__':
    main()
