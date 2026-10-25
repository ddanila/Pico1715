#!/usr/bin/env python3
"""Build and observe the external W/M baseline; never patch or write input media."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'robotron1715m-wm-reference'
SOURCES = [
    'machines/robotron1715m/robotron.c',
    'machines/robotron1715m/disk.c',
    'machines/robotron1715m/keyboard.c',
    'machines/robotron1715m/sio.c',
    'common/cpu/z80.c', 'common/media/media.c', 'common/trace/trace.c',
]


def digest(path):
    with path.open('rb') as stream:
        result = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def validate_inputs(paths):
    expected = {'rom': 2048, 'prom': 256, 'disk': 819200}
    for name, path in paths.items():
        if path.stat().st_size != expected[name]:
            raise ValueError(f'{name}: expected {expected[name]} bytes for {PROFILE}')
    return {name: {'bytes': path.stat().st_size, 'sha256': digest(path)}
            for name, path in paths.items()}


def summarize_trace(path):
    counts = {}
    total = 0
    previous = -1
    with path.open() as stream:
        for line in stream:
            event = json.loads(line)
            if event['kind'] not in ('IR', 'IW', 'IA'):
                raise ValueError('unexpected event kind')
            if not isinstance(event['cycle'], int) or event['cycle'] < previous:
                raise ValueError('non-monotonic trace')
            if not 0 <= event['address'] <= 65535 or not 0 <= event['data'] <= 255:
                raise ValueError('event outside bus bounds')
            if event['master'] not in (0, 1):
                raise ValueError('unknown bus master')
            previous = event['cycle']
            key = f"{event['kind']}:{event['address'] & 255:02x}:" + (
                'cpu' if event['master'] == 0 else 'dma')
            counts[key] = counts.get(key, 0) + 1
            total += 1
    return {'events': total, 'by_kind_port_master': dict(sorted(counts.items()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dac', 'rom', 'prom', 'disk', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--ticks', type=int, default=100000000)
    parser.add_argument('--cc', default='cc')
    args = parser.parse_args()
    if not 1 <= args.ticks <= 500000000:
        parser.error('--ticks must be between 1 and 500000000')
    dac = args.dac.resolve()
    sources = json.loads((ROOT / 'docs/sources.json').read_text())
    revision = subprocess.check_output(
        ['git', '-C', str(dac), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != sources['dac']['commit']:
        parser.error('DAC revision differs from docs/sources.json; review it before repinning')
    for command in (['diff', '--quiet'], ['diff', '--cached', '--quiet']):
        if subprocess.run(['git', '-C', str(dac), *command], check=False).returncode:
            parser.error('DAC has tracked changes; use a clean pinned checkout')
    paths = {name: getattr(args, name).resolve() for name in ('rom', 'prom', 'disk')}
    identities = validate_inputs(paths)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    binary = build / 'dac-capture'
    command = [args.cc, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
               '-I', str(dac), str(ROOT / 'tools/dac_capture.c'),
               *(str(dac / source) for source in SOURCES), '-o', str(binary)]
    subprocess.run(command, check=True, timeout=120)
    notices = build / 'licenses'
    notices.mkdir(exist_ok=True)
    for source, name in [
        ('LICENSE', 'dac-LICENSE'), ('NOTICE', 'dac-NOTICE'),
        ('third_party/cpu/chips/LICENSE', 'chips-LICENSE'),
        ('machines/robotron1715m/REFERENCE_LICENSE', 'robotron-REFERENCE_LICENSE'),
    ]:
        shutil.copyfile(dac / source, notices / name)
    result = subprocess.run(
        [str(binary), *(str(paths[n]) for n in ('rom', 'prom', 'disk')),
         str(args.ticks), str(out / 'io.jsonl')],
        capture_output=True, text=True, timeout=120)
    (out / 'screen.txt').write_text(result.stdout)
    (out / 'runner.stderr').write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f'capture failed ({result.returncode}): {result.stderr}')
    state = json.loads(result.stderr)
    trace = summarize_trace(out / 'io.jsonl')
    unchanged = identities == validate_inputs(paths)
    booted = result.stdout.rstrip().endswith('A>')
    passed = (unchanged and booted and state['disk_reads'] > 0 and
              state['disk_writes'] == 0 and state['dropped'] == 0 and
              trace['events'] == state['events'] and trace['events'] > 0)
    report = {
        'schema': 1, 'profile': PROFILE, 'dac_commit': revision,
        'adapter_sha256': digest(ROOT / 'tools/dac_capture.c'),
        'binary_sha256': digest(binary),
        'compiler': subprocess.check_output([args.cc, '--version'], text=True).splitlines()[0],
        'inputs': identities, 'requested_ticks': args.ticks,
        'input_files_unchanged': unchanged, 'boot_prompt_observed': booted,
        'passed': passed, 'state': state, 'trace': trace,
        'screen_sha256': digest(out / 'screen.txt'),
        'trace_sha256': digest(out / 'io.jsonl'),
        'limitations': ['W/M baseline only; no classic-1715 or card model',
                        'Observer events, not physical bus-edge timing',
                        'Boot/read only; no write or persistence qualification'],
    }
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': passed, 'profile': PROFILE,
                      'events': trace['events'], 'report': str(out / 'report.json')}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
