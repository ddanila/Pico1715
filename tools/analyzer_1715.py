#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Streaming classic PC1715 controller trace interpretation and comparison."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from cycle_trace import KINDS, read_header, records


def crc16(data):
    crc = 0xffff
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xffff
    return crc


class Decoder:
    """Interpret only observed state; a cropped trace does not imply reset defaults."""
    def __init__(self):
        self.clear()

    def clear(self):
        self.control = self.select = self.format = None
        self.pending = None
        self.vectors = {}
        self.status = None
        self.size = None
        self.buffers = {'read': bytearray(), 'write': bytearray()}

    def field(self, direction, value):
        buf = self.buffers[direction]
        buf.append(value)
        if len(buf) <= 3:
            if value != 0xa1:
                buf.clear()
            return []
        if len(buf) == 4 and value not in (0xfe, 0xfb):
            # A longer A1 run may still lead into a field.
            buf[:] = b'\xa1' * 3 if value == 0xa1 else b''
            return []
        mark = buf[3]
        if mark == 0xfb and self.size is None:
            buf.clear()
            return ['data field: length unknown (no complete preceding ID)']
        length = 10 if mark == 0xfe else 6 + self.size
        if len(buf) != length:
            return []
        good = crc16(buf[:-2]) == int.from_bytes(buf[-2:], 'big')
        if mark == 0xfe:
            c, h, r, n = buf[4:8]
            self.size = (128 << n) if good and n <= 3 else None
            result = f'ID C={c} H={h} R={r} N={n}; CRC {"ok" if good else "BAD"}'
        else:
            result = f'{direction} data field {self.size} bytes; CRC {"ok" if good else "BAD"}'
        buf.clear()
        return [result]

    def feed(self, r):
        p, d = r.address & 255, r.data
        if r.kind == 8:
            self.clear()
            return ['observed bus reset; inference state cleared (CPU reset not established)']
        if r.flags or r.kind == 9:
            self.clear()
            return ['uncertain cycle; inference state cleared']
        if r.kind == 6:
            names = [name for name, vector in self.vectors.items() if vector == d]
            return [f'interrupt acknowledge vector={d:02x}' + (f' ({"/".join(names)})' if names else '')]
        if r.kind not in (4, 5):
            return []
        if r.kind == 4:
            if p == 2:
                return ['RX byte'] + self.field('read', d)
            if p == 4:
                self.control = d
                return [f'control readback={d:02x}']
            if p == 6:
                changed = self.status is None or self.status != d
                self.status = d
                return [('status changed: ' if changed else 'status: ') +
                        f'ready={int(not d & 1)} mark={int(bool(d & 2))} '
                        f'writable={int(bool(d & 32))} track_zero={int(not d & 128)} '
                        f'format={d & 0x1c:02x} /FW={int(bool(d & 64))}']
            return [f'I/O read port={p:02x} (outside modeled controller subset)']
        if 0x20 <= p <= 0x23:
            if self.select != d:
                self.size = None
                self.buffers = {'read': bytearray(), 'write': bytearray()}
            self.select = d
            return [f'drive latch={d:02x}; selected={int(not d & 0x10)} (media presence unknown)']
        if p == 6:
            self.format = d
            return [f'format={d:02x}; MFM250={int((d & 0x14) == 4)}']
        if p in (5, 7):
            name = 'index' if p == 5 else 'mark'
            if p == 7 and self.pending:
                pending, self.pending = self.pending, None
                return [f'mark PIO {pending}={d:02x}']
            if p == 7 and d == 0xcf:
                self.pending = 'direction'
                return ['mark PIO bit-control mode; direction word follows']
            if not d & 1:
                self.vectors[name] = d
                return [f'{name} vector={d:02x}']
            if d & 15 in (3, 7):
                if p == 7 and d & 15 == 7 and d & 16:
                    self.pending = 'interrupt mask'
                return [f'{name} IRQ enabled={int(bool(d & 128))}' +
                        ('; mask word follows' if p == 7 and self.pending else '')]
            return [f'{name} PIO setup={d:02x} (unmodeled word)']
        if p == 4:
            old, self.control = self.control, d
            out = [f'control={d:02x}; head={int(not d & 4)} /WE={d & 1}']
            if old is not None:
                if old & 1 and not d & 1:
                    self.buffers['write'].clear()
                    out.append('write gate opened')
                if not old & 1 and d & 1:
                    out.append('write gate closed (persistence not observable)')
                    if len(self.buffers['write']) >= 4:
                        out.append('incomplete observed write field')
                    self.buffers['write'].clear()
                if old & 128 and not d & 128:
                    out.append('step ' + ('inward' if d & 32 else 'outward') +
                               ('; selected' if self.select is not None and not self.select & 16 else '; selection unknown/inactive'))
                    self.size = None
                if d & 0x39 == 1 and not d & 2 and old != d:
                    self.buffers['read'].clear()
                    out.append('mark acquisition requested')
            return out
        if p == 0:
            if self.control is None:
                return ['TX byte; write gate unknown']
            if self.control & 1:
                return ['TX register loaded while write gate closed (ignored by model)']
            return ['TX byte'] + self.field('write', d)
        return [f'I/O write port={p:02x} (outside modeled controller subset)']


def scan(path, *, context=8, center=None, wait_us=None, gap_us=None, output=None):
    counts, notes, fields, timeline = Counter(), Counter(), Counter(), []
    decoder = Decoder()
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
        f.seek(0)
        header = read_header(f)
        trigger = header.trigger[7] if header.trigger and header.trigger[6] else None
        center = center if center is not None else (trigger if trigger is not None else 0)
        previous = None
        elapsed = 0
        for index, (r, gap) in enumerate(records(f, header)):
            delta = 0 if previous is None else (r.tick - previous.tick) & 0xffffffff
            elapsed += delta
            extra = []
            if gap and header.dropped:
                decoder.clear()
                extra.append('sequence gap may include loss; inference state cleared')
            if wait_us is not None and r.wait_samples * 1e6 / header.clock_hz > wait_us:
                extra.append('WAIT budget exceeded (configured threshold)')
            if gap_us is not None and previous is not None and (delta - previous.duration) * 1e6 / header.clock_hz > gap_us:
                extra.append('observed idle gap budget exceeded (not proof of controller timeout)')
            annotations = extra + decoder.feed(r)
            counts[KINDS[r.kind]] += 1
            for note in annotations:
                if '; CRC ' in note:
                    fields[('ID' if note.startswith('ID ') else 'data') + (' ok' if note.endswith('ok') else ' BAD')] += 1
                if 'BAD' in note or 'length unknown' in note or 'incomplete' in note or 'unexpected' in note or 'exceeded' in note or 'uncertain' in note or 'may include loss' in note:
                    notes[note] += 1
            event = dict(index=index, sequence=r.sequence, tick=r.tick,
                         elapsed_us=elapsed * 1e6 / header.clock_hz,
                         kind=KINDS[r.kind], address=f'{r.address:04x}', data=f'{r.data:02x}',
                         flags=r.flags, wait_samples=r.wait_samples, duration=r.duration,
                         gap_before=gap, trigger=index == trigger, annotations=annotations)
            if abs(index - center) <= context:
                timeline.append(event)
            if output:
                output.write(json.dumps(event) + '\n')
            previous = r
    return dict(sha256=digest.hexdigest(), clock_hz=header.clock_hz, records=header.count,
                dropped=header.dropped, filtered=header.filtered, trigger_index=trigger,
                kinds=dict(counts), fields=dict(fields), diagnostics=dict(notes), timeline=timeline,
                limitations=['Sequence gaps include filtered cycles; loss location is not recoverable.',
                             'Time unwrap assumes less than one 32-bit clock wrap between records.',
                             'Bus bytes do not prove disk persistence or CPU reset.',
                             'Field interpretation covers the modeled classic 1715 MFM subset only.'])


def comparable(path, align):
    with open(path, 'rb') as f:
        header = read_header(f)
        start = 0
        if align == 'trigger':
            if not header.trigger or not header.trigger[6]:
                raise ValueError('trigger alignment requires a fired trigger in both captures')
            start = header.trigger[7]
        previous = None
        elapsed = 0
        for index, (r, _) in enumerate(records(f, header)):
            if previous is not None:
                elapsed += (r.tick - previous.tick) & 0xffffffff
            previous = r
            if index < start or r.kind not in (4, 5, 6, 8, 9):
                continue
            # High I/O address bytes vary with CPU instructions; classic decode is A0..A7.
            key = (r.kind, r.address & 255 if r.kind in (4, 5) else 0, r.data, r.flags)
            yield dict(index=index, sequence=r.sequence, key=key,
                       time_us=elapsed * 1e6 / header.clock_hz,
                       duration_us=r.duration * 1e6 / header.clock_hz,
                       wait_us=r.wait_samples * 1e6 / header.clock_hz)


def compare(left, right, align='start', tolerance_us=None):
    from itertools import zip_longest
    mismatch = None
    compared = 0
    origins = None
    # Consume both complete streams even after divergence to validate tails.
    for a, b in zip_longest(comparable(left, align), comparable(right, align)):
        if a and b and origins is None:
            origins = (a['time_us'], b['time_us'])
        reason = None
        if a is None or b is None:
            reason = 'different number of selected events'
        elif a['key'] != b['key']:
            reason = 'different bus transaction'
        elif tolerance_us is not None and any(abs(x - y) > tolerance_us for x, y in (
                (a['time_us'] - origins[0], b['time_us'] - origins[1]),
                (a['duration_us'], b['duration_us']), (a['wait_us'], b['wait_us']))):
            reason = 'timing tolerance exceeded'
        if reason and mismatch is None:
            mismatch = dict(event=compared, reason=reason, capture=a, reference=b)
        compared += 1
    return dict(match=mismatch is None and compared > 0, compared_events=compared,
                first_divergence=mismatch, alignment=align, tolerance_us=tolerance_us,
                scope='I/O low-byte port, data, flags; interrupt acknowledge, reset, invalid cycles. '
                      'Memory/refresh excluded; trigger alignment excludes pre-trigger history. '
                      'Equality of observed events does not establish completeness of a lossy capture.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--align', choices=('start', 'trigger'), default='start')
    parser.add_argument('--timing-tolerance-us', type=float)
    parser.add_argument('--wait-budget-us', type=float)
    parser.add_argument('--gap-budget-us', type=float)
    parser.add_argument('--center', type=int, help='record index; default fired trigger or first record')
    parser.add_argument('--context', type=int, default=8)
    parser.add_argument('--events', type=Path, help='stream all annotated records to JSONL')
    parser.add_argument('--json', action='store_true', help='machine-readable summary')
    args = parser.parse_args()
    for value in (args.context, args.center, args.timing_tolerance_us, args.wait_budget_us, args.gap_budget_us):
        if value is not None and (value < 0 or value != value or value == float('inf')):
            parser.error('indices, budgets and tolerances must be finite and nonnegative')
    if args.events and args.events.resolve() in {args.capture.resolve(), args.reference.resolve() if args.reference else None}:
        parser.error('events output must not overwrite an input capture')
    try:
        from contextlib import nullcontext
        with (args.events.open('x') if args.events else nullcontext(None)) as output:
            result = scan(args.capture, context=args.context, center=args.center,
                          wait_us=args.wait_budget_us, gap_us=args.gap_budget_us, output=output)
        if args.reference:
            result['comparison'] = compare(args.capture, args.reference, args.align, args.timing_tolerance_us)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"{result['records']} records; {result['dropped']} dropped; {result['filtered']} filtered")
            for e in result['timeline']:
                print(f"{'*' if e['trigger'] else ' '} {e['index']:8d} {e['elapsed_us']:12.3f} us "
                      f"{e['kind']:16s} {e['address']} {e['data']} " + '; '.join(e['annotations']))
            print('Fields:', json.dumps(result['fields'], sort_keys=True))
            print('Diagnostics:', json.dumps(result['diagnostics'], sort_keys=True))
            if 'comparison' in result:
                print('Comparison:', json.dumps(result['comparison']))
            print('\n'.join(result['limitations']))
        return 1 if args.reference and not result['comparison']['match'] else 0
    except (OSError, ValueError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
