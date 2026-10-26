#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the standalone analyzer desk checks and record source identities."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('output already exists; choose a new report path')
    result = subprocess.run(['make', 'test-analyzer', 'lint-analyzer', 'synth-analyzer'],
                            cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=120)
    print(result.stdout, end='')
    result.check_returncode()
    subprocess.run(['python3', '-m', 'unittest', 'discover', '-s', 'tests',
                    '-p', 'test_analyzer.py', '-v'], cwd=ROOT, check=True)
    directed = re.search(r'analyzer PASS: (\d+) checks', result.stdout)
    random = re.search(r'analyzer randomized PASS: (\d+) captures, (\d+) records', result.stdout)
    if not directed or not random:
        raise RuntimeError('missing test results')
    synthesis = (ROOT/'build/analyzer-synthesis.log').read_text()
    cells = {name: int(count) for name, count in
             re.findall(r'^\s+(SB_\w+)\s+(\d+)\s*$', synthesis, re.M)}
    # Catch accidental loss of block-RAM inference or a huge logic regression.
    if cells.get('SB_RAM40_4K') != 5 or cells.get('SB_LUT4', 99999) > 1000:
        raise RuntimeError(f'analyzer resource budget regression: {cells}')
    sources = ['hardware/rtl/analyzer_top.v', 'tests/analyzer_tb.v',
               'tests/analyzer_random.py', 'tests/test_analyzer.py',
               'tools/analyzer_trace.py', 'tools/check_analyzer.py', 'Makefile']
    versions = {}
    for tool, arg in [('iverilog', '-V'), ('verilator', '--version'), ('yosys', '-V')]:
        run = subprocess.run([tool, arg], text=True, capture_output=True, check=True)
        versions[tool] = run.stdout.splitlines()[0]
    report = {'schema': 1, 'profile': 'standalone-passive-raw-analyzer',
              'physical_timing_qualified': False, 'board_pins_assigned': False,
              'usb_transport_implemented': False, 'cpu_cosimulated': False,
              'depth': 256, 'record_bits': 72, 'sample_clock_hz_fixture': 50000000,
              'directed_checks': int(directed[1]), 'random_captures': int(random[1]),
              'random_records': int(random[2]), 'seed': 1715, 'ice40_cells': cells,
              'tools': versions,
              'source_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                                for p in sources}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
