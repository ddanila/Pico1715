#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Qualify compact RTL against DAC callbacks; optional private stock-ROM boot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from cycle_trace import read_header, records

ROOT = Path(__file__).resolve().parents[1]
ROM_HASH = '51cb80639b5667f2611da71ce7305061566cf3474bda7db6fc82709d08e46d01'
DISK_HASH = '16c4389cd8d4b7759ece28efdda5b9b1a04536cdeb3f644c583d953d5ecd55c4'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(path):
    selected = hashlib.sha256()
    count = 0
    with path.open('rb') as source:
        header = read_header(source)
        for record, _ in records(source, header):
            if (1 << record.kind) & 0x170:
                selected.update(record.encode())
                count += 1
    return {'header': vars(header), 'bytes': path.stat().st_size,
            'io_records': count, 'io_records_sha256': selected.hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dac', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--rom', type=Path)
    p.add_argument('--disk', type=Path)
    a = p.parse_args()
    if bool(a.rom) != bool(a.disk):
        p.error('--rom and --disk must be supplied together')
    dac, out = a.dac.resolve(), a.out.resolve()
    pin = json.loads((ROOT/'docs/sources.json').read_text())['dac']['commit']
    revision = subprocess.check_output(['git', '-C', str(dac), 'rev-parse', 'HEAD'], text=True).strip()
    require(revision == pin, 'unqualified DAC revision')
    for cmd in (['diff', '--quiet'], ['diff', '--cached', '--quiet']):
        require(subprocess.run(['git', '-C', str(dac), *cmd]).returncode == 0, 'dirty DAC dependency')
    if a.rom:
        require(digest(a.rom) == ROM_HASH and digest(a.disk) == DISK_HASH, 'unqualified ROM/disk')
    out.mkdir(parents=True, exist_ok=False)
    checked = subprocess.run(['make', 'test-cycle-analyzer', 'lint-cycle-analyzer', 'synth-cycle-analyzer'],
                             cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (out/'rtl-checks.log').write_text(checked.stdout)
    checked.check_returncode()
    match = re.search(r'cycle analyzer PASS: (\d+) checks', checked.stdout)
    require(match is not None, 'missing directed checks')
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_cycle_trace.py', '-v'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT/'tools/build_analyzer_cosim.py'), '--dac', str(dac),
                    '--out', str(out/'build')], check=True, timeout=180)
    baseline = out/'baseline-probe'
    subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(dac),
                    str(ROOT/'tools/classic_probe.c'), str(ROOT/'model/controller.c'),
                    str(dac/'machines/robotron1715/pc1715.c'), str(dac/'common/cpu/z80.c'),
                    str(dac/'common/trace/trace.c'), '-o', str(baseline)], check=True)
    for source, name in [('LICENSE', 'dac-LICENSE'), ('NOTICE', 'dac-NOTICE'),
                         ('third_party/cpu/chips/LICENSE', 'chips-LICENSE')]:
        shutil.copyfile(dac/source, out/name)
    program = bytes.fromhex('f3 21 00 80 36 5a 7e d3 04 db 04 76 18 fd')
    (out/'smoke.rom').write_bytes(program.ljust(2048, b'\0'))
    (out/'smoke.disk').write_bytes(bytes(819200))
    cases = {}

    def qualify(name, rom, disk, ticks, stock):
        modes = {}
        input_hashes = [digest(rom), digest(disk)]
        for mode in ('baseline', 'all', 'io-only'):
            folder = out/f'{name}-{mode}'
            folder.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.startswith('PICO1715_')}
            env['PICO1715_CYCLES'] = str(ticks)
            if stock:
                env['PICO1715_TIMED'] = '0'
            if mode == 'io-only':
                env['PICO1715_ANALYZER_IO_ONLY'] = '1'
            binary = baseline if mode == 'baseline' else out/'build/classic-probe'
            run = subprocess.run([str(binary), str(rom.resolve()), str(disk.resolve()), str(folder)],
                                 env=env, text=True, capture_output=True, timeout=180)
            (folder/'stderr.txt').write_text(run.stderr)
            (folder/'probe.json').write_text(run.stdout)
            require(run.returncode == (0 if stock else 1), f'{name}-{mode}: {run.stderr}')
            probe = json.loads(run.stdout)
            if stock:
                screen = (folder/'screen.txt').read_text()
                require(probe['rom_handoff_cycle'] > 0 and 'SCP' in screen and 'A>' in screen,
                        'stock OS prompt not reached')
            else:
                require((folder/'ram.bin').read_bytes()[0x8000] == 0x5a, 'synthetic memory test failed')
            hashes = {n: digest(folder/n) for n in ('ram.bin', 'disk.img', 'screen.txt', 'io.trace')}
            require(hashes['disk.img'] == input_hashes[1], 'read-only test changed disk')
            modes[mode] = {'probe': probe, 'output_sha256': hashes}
            if mode != 'baseline':
                stats = json.loads((folder/'analyzer.json').read_text())
                parsed = inspect(folder/'cycles.p1715')
                require(stats['dropped'] == stats['saturated_records'] == stats['unstable_records'] == 0,
                        'unexpected analyzer loss/ambiguity')
                require(stats['records'] == parsed['header']['count'] and stats['filtered'] == parsed['header']['filtered'],
                        'file metadata differs from simulation')
                require(stats['callbacks_matched'] > 0 and stats['kinds'][4] and stats['kinds'][5],
                        'I/O not exercised')
                if stock:
                    require(stats['kinds'][6] and stats['wait_samples'], 'IRQ or WAIT not exercised')
                modes[mode].update(analyzer=stats, capture=parsed)
            require([digest(rom), digest(disk)] == input_hashes, 'external input changed')
        for mode in ('all', 'io-only'):
            require(modes[mode]['probe'] == modes['baseline']['probe'] and
                    modes[mode]['output_sha256'] == modes['baseline']['output_sha256'],
                    'analyzer changed emulated machine behavior')
        full, filtered = modes['all']['capture'], modes['io-only']['capture']
        require(full['io_records_sha256'] == filtered['io_records_sha256'] and
                full['io_records'] == filtered['io_records'], 'filter changed retained records')
        require(full['header']['count'] - filtered['header']['count'] == filtered['header']['filtered'],
                'filter accounting mismatch')
        cases[name] = modes
        print(f'{name} PASS: full {full["bytes"]} bytes; I/O {filtered["bytes"]} bytes', flush=True)

    qualify('synthetic', out/'smoke.rom', out/'smoke.disk', 1000, False)
    if a.rom:
        qualify('stock-boot', a.rom, a.disk, 20000000, True)
    sources = ['hardware/rtl/cycle_encoder.v', 'hardware/rtl/cycle_capture_top.v',
               'tests/cycle_analyzer_tb.v', 'tests/test_cycle_trace.py', 'tools/cycle_trace.py',
               'tools/analyzer/bridge.cpp', 'tools/analyzer/bridge.h', 'tools/classic_probe.c',
               'model/controller.c', 'model/controller.h', 'tools/build_analyzer_cosim.py',
               'tools/check_cycle_analyzer.py', 'Makefile']
    cells = {name: int(n) for name, n in re.findall(r'^\s+(SB_\w+)\s+(\d+)\s*$',
                                                  (ROOT/'build/cycle-analyzer-synthesis.log').read_text(), re.M)}
    require(cells.get('SB_RAM40_4K') == 8 and cells.get('SB_LUT4', 99999) < 1500,
            'resource regression')
    versions = {}
    for tool, flag in [('iverilog', '-V'), ('verilator', '--version'), ('yosys', '-V')]:
        versions[tool] = subprocess.check_output([tool, flag], text=True, stderr=subprocess.DEVNULL).splitlines()[0]
    report = {'schema': 1, 'profile': 'compact-cycle-analyzer-dac-observer', 'dac_commit': revision,
              'physical_timing_qualified': False, 'usb_transport_implemented': False,
              'samples_per_cpu_tick': 4, 'sample_hz': 9832000, 'directed_checks': int(match[1]),
              'rom_sha256': ROM_HASH if a.rom else None, 'disk_sha256': DISK_HASH if a.disk else None,
              'source_sha256': {s: digest(ROOT/s) for s in sources}, 'tools': versions,
              'ice40_cells': cells, 'cases': cases}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
