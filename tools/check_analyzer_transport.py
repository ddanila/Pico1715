#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise production FIFO/link and shared C receiver with explicit fault profiles."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from cycle_trace import read_header, records

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ('normal', 'slow', 'crc', 'index', 'lost_ack', 'disconnect',
             'overflow', 'full', 'permanent_crc', 'trigger', 'trigger-early',
             'trigger-never', 'trigger-overflow', 'trigger-crc', 'trigger-lost-ack')


def digest(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workload', type=Path)
    parser.add_argument('--reference', type=Path)
    args = parser.parse_args()
    if args.reference and not args.workload:
        parser.error('--reference requires --workload')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)

    def run(command, log):
        with (out / log).open('w') as stream:
            subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)

    run(['make', 'test-cycle-analyzer', 'test-analyzer-transport-top',
         'lint-analyzer-transport', 'synth-analyzer-transport'], 'rtl.log')
    run(['python3', 'tools/build_analyzer_transport.py', '--out', str(out / 'build')], 'build.log')
    results = {}
    for name in (*SCENARIOS, *(('boot-normal', 'boot-slow', 'boot-trigger') if args.workload else ())):
        case = out / name
        case.mkdir()
        command = [str(out / 'build/transport-test'), name.removeprefix('boot-'), str(case)]
        if name.startswith('boot-'):
            command.append(str(args.workload.resolve()))
        run(command, name + '.log')
        result = json.loads((case / 'report.json').read_text())
        capture = case / 'capture.p1715'
        if result['state'] == 4:
            with capture.open('rb') as stream:
                header = read_header(stream)
                assert sum(1 for _ in records(stream, header)) == result['records']
            result['capture_sha256'] = digest(capture)
            if header.trigger is not None:
                result['trigger_metadata'] = header.trigger
            if name in ('boot-normal', 'boot-slow') and args.reference:
                assert result['capture_sha256'] == digest(args.reference), 'reference capture differs'
                result['reference_identical'] = True
        else:
            assert name == 'permanent_crc' and result['state'] == 5 and not capture.exists()
        results[name] = result
        print(name, 'PASS', flush=True)
    sources = [*ROOT.glob('hardware/rtl/analyzer*.v'),
               ROOT / 'hardware/rtl/cycle_capture_top.v', ROOT / 'hardware/rtl/cycle_encoder.v',
               *ROOT.glob('firmware/analyzer*'), ROOT / 'firmware/psram.c',
               ROOT / 'firmware/CMakeLists.txt', ROOT / 'tests/analyzer_transport.cpp',
               ROOT / 'tests/analyzer_transport_top_tb.v', ROOT / 'tests/cycle_analyzer_tb.v',
               ROOT / 'tools/build_analyzer_transport.py', Path(__file__).resolve(),
               ROOT / 'tools/cycle_trace.py', ROOT / 'Makefile']
    report = {
        'qualification': 'simulation and synthesis only; no physical timing qualification',
        'sources': {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(sources))},
        'tools': {tool: subprocess.check_output([tool, option], text=True).splitlines()[0]
                  for tool, option in [('verilator', '--version'), ('yosys', '-V'), ('cc', '--version')]},
        'checks': ['native cycle-to-packet integration and passive outputs',
                   'existing cycle analyzer regression', 'RTL lint', 'iCE40 synthesis',
                   'shared C firmware and RTL FIFO/link replay', 'capture format validation'],
        'model': {'fpga_clock_hz': 50000000, 'receiver_poll_ns': [100, 200],
                  'psram_commit_delay_ns': 1000,
                  'note': 'Polling and memory latency are modeled assumptions, not measured RP2350 performance. Boot replay injects completed records into the production FIFO at original completion times.'},
        'results': results,
    }
    if args.workload:
        report['workload_sha256'] = digest(args.workload)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
