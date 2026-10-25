#!/usr/bin/env python3
"""Verify the frontend reference and record reproducible, non-electrical results."""
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
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite an earlier qualification record.
    with args.out.open('x') as output:
        run = subprocess.run(['make', 'test', 'test-frontend', 'lint-frontend', 'synth-frontend'],
                             cwd=ROOT, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=120)
        print(run.stdout, end='')
        run.check_returncode()
        match = re.search(r'frontend PASS: (\d+) checks, (\d+) completed transactions', run.stdout)
        if not match:
            raise RuntimeError('missing simulation result')
        versions = {}
        for name, command in {'iverilog': ['iverilog', '-V'],
                              'verilator': ['verilator', '--version'],
                              'yosys': ['yosys', '-V']}.items():
            result = subprocess.run(command, text=True, capture_output=True, check=True)
            versions[name] = result.stdout.splitlines()[0]
        sources = ['hardware/rtl/bus_frontend.v', 'tests/frontend_tb.v',
                   'tools/check_frontend.py', 'Makefile']
        report = {'schema': 1, 'profile': 'normal-io-frontend-reference',
                  'physical_timing_qualified': False, 'stock_software_cosimulated': False,
                  'device_fitted': False, 'fixture_clock_hz': 50000000,
                  'watchdog_cycles': 4096, 'checks': int(match[1]),
                  'completed_transactions': int(match[2]), 'tools': versions,
                  'validation': ['model unit tests', 'RTL simulation', 'RTL lint',
                                 'generic synthesis and structural check'],
                  'source_sha256': {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest()
                                    for s in sources}}
        json.dump(report, output, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
