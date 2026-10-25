#!/usr/bin/env python3
"""Run nine stock-software regressions, latency sweeps and timed fault cases.

Sweep limits describe this digital model/workload, not physical pin deadlines.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from check_classic import ROOT, digest, require
from classic_workload import small_file, program


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('dac', 'rom', 'disk', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    baseline = out / 'baseline'
    subprocess.run([sys.executable, str(ROOT / 'tools/check_classic.py'), '--timed',
                    '--dac', str(args.dac.resolve()), '--rom', str(args.rom.resolve()),
                    '--disk', str(args.disk.resolve()), '--out', str(baseline)], check=True)
    environment = {k: v for k, v in os.environ.items() if not k.startswith('PICO1715_')}
    image = baseline / 'workload.img'
    original = digest(image)
    cases = {}
    payload = program()[1] * 20

    def run(name, **options):
        folder = out / name
        folder.mkdir()
        config = {'PICO1715_TIMED': '0', **{k: str(v) for k, v in options.items()}}
        proc = subprocess.run([str(baseline / 'classic-probe'), str(args.rom.resolve()),
                               str(image), str(folder), 'PICOTEST\r'],
                              env={**environment, **config}, text=True, capture_output=True, timeout=60)
        require(proc.returncode in (0, 1), f'{name}: runner failed: {proc.stderr}')
        report = json.loads(proc.stdout)
        screen = (folder / 'screen.txt').read_text()
        try:
            exact_file = small_file((folder / 'disk.img').read_bytes(), b'PICOTESTTXT') == payload
        except ValueError:
            exact_file = False
        report['software_pass'] = (proc.returncode == 0 and 'PICO READ WRITE OK' in screen and
                                   'BIOS ERR' not in screen and 'PICO TEST FAILED' not in screen and exact_file)
        report['clean_pass'] = report['software_pass'] and all(report[k] == 0 for k in
            ('overruns', 'underflows', 'tx_overruns', 'tx_underruns', 'rejected_writes', 'drops'))
        report['options'] = config
        report['output_sha256'] = digest(folder / 'disk.img')
        report['screen'] = '\n'.join(line.rstrip() for line in screen.splitlines()).rstrip()
        require(digest(image) == original, 'fixture input changed')
        (folder / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        (folder / 'stderr.txt').write_text(proc.stderr)
        cases[name] = report
        print(f'{name}: software={report["software_pass"]} clean={report["clean_pass"]} '
              f'rx_lost={report["overruns"]} tx_lost={report["tx_underruns"]}', flush=True)
        return report

    # Establish local adjacent pass/fail points. No global monotonicity is claimed.
    boundaries = {}
    for label, key in [('read', 'PICO1715_TIMED'), ('write', 'PICO1715_WRITE_DELAY'),
                       ('irq', 'PICO1715_IRQ_DELAY')]:
        tested = {}
        for value in (0, 8, 16, 32, 64, 128):
            tested[value] = run(f'{label}-{value}', **{key: value})
        low = 0
        high = next(v for v in sorted(tested) if not tested[v]['clean_pass'])
        require(tested[0]['clean_pass'], f'{label}: baseline failed')
        low = max(v for v in tested if v < high and tested[v]['clean_pass'])
        while high - low > 1:
            middle = (high + low) // 2
            tested[middle] = run(f'{label}-{middle}', **{key: middle})
            if tested[middle]['clean_pass']:
                low = middle
            else:
                high = middle
        boundaries[label] = {'adjacent_clean_pass_ticks': low, 'adjacent_failure_ticks': high,
                             'tested_ticks': sorted(tested), 'clock_hz': 2458000,
                             'physical_timing_limit': False}
    # More buffering can cover transient backlog, but not sustained excess latency.
    run('fifo2-read16', PICO1715_TIMED=16, PICO1715_FIFO=2)
    run('fifo16-read64', PICO1715_TIMED=64, PICO1715_FIFO=16)
    no_wait = run('no-wait', PICO1715_NO_WAIT=1)
    require(not no_wait['software_pass'] and no_wait['underflows'] > 0, 'no-WAIT fault not detected')
    for name, config in [('drop-data', {'PICO1715_DROP_BYTE': 50}),
                         ('bad-crc', {'PICO1715_CORRUPT_CRC': 1}),
                         ('mark-timeout', {'PICO1715_MARK_DELAY': 1000000})]:
        result = run(name, **config)
        require(not result['software_pass'], f'{name}: failure not exposed')
        require(result['writes'] == 0 and result['output_sha256'] == original,
                f'{name}: read-side fault modified media')
    for phase, name in [(1, 'reset-read'), (2, 'reset-write')]:
        result = run(name, PICO1715_RESET_PHASE=phase)
        require(result['clean_pass'] and result['resets'] == 1 and result['reset_image_unchanged'],
                f'{name}: reset/reboot recovery failed')
    base_report = json.loads((baseline / 'report.json').read_text())
    report = {'schema': 1, 'profile': 'pc1715-timing-experiments',
              'baseline_cases': len(base_report['cases']), 'dac_commit': base_report['dac_commit'],
              'clock_hz': 2458000, 'bit_rate': 250000, 'byte_period_us': 32,
              'byte_period_ticks': 78.656, 'hardware_timing_qualified': False,
              'scope': 'scheduled field bytes and transaction waits; not a flux/half-clock simulation',
              'source_sha256': {**base_report['source_sha256'], 'tools/check_timing.py': digest(Path(__file__))},
              'boundaries': boundaries, 'cases': cases}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Timing suite passed: {len(cases)} experiments; {out / "report.json"}')


if __name__ == '__main__':
    main()
