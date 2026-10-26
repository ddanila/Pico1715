#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pack simulated analyzer samples and export frozen captures. No USB transport yet."""
import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import struct

MAGIC = b'P1715LA\0'
HEADER = struct.Struct('<8sHHIIIIIIQQ')
RECORD = struct.Struct('<IQ')
NO_TRIGGER = 0xffffffff
SIGNALS = [('addr', 0, 16), ('data', 16, 8), ('mreq_n', 24, 1),
           ('iorq_n', 25, 1), ('rd_n', 26, 1), ('wr_n', 27, 1),
           ('m1_n', 28, 1), ('rfsh_n', 29, 1), ('clock', 30, 1),
           ('reset_n', 31, 1), ('wait_n', 32, 1), ('int_n', 33, 1),
           ('busrq_n', 34, 1), ('bao_n', 35, 1), ('iei', 36, 1),
           ('ieo', 37, 1)]


@dataclass
class Capture:
    clock_hz: int
    pre: int
    post: int
    trigger_index: int
    stopped: bool
    records: list
    trigger_mask: int = 0
    trigger_value: int = 0

    def validate(self):
        if not 1 <= self.clock_hz <= 0xffffffff:
            raise ValueError('invalid sample clock')
        if not 0 <= self.pre <= 0xffffffff or not 0 <= self.post <= 0xffffffff:
            raise ValueError('invalid capture limits')
        if not 0 <= self.trigger_mask < (1 << 38) or not 0 <= self.trigger_value < (1 << 38):
            raise ValueError('invalid trigger bits')
        n = len(self.records)
        if n > self.pre + self.post + 1:
            raise ValueError('capture exceeds configured capacity')
        if self.trigger_index == NO_TRIGGER:
            if not self.stopped or n > self.pre:
                raise ValueError('untriggered capture must be stopped within history limit')
        else:
            if not 0 <= self.trigger_index < n or self.trigger_index > self.pre:
                raise ValueError('invalid trigger index')
            after = n - self.trigger_index - 1
            if after > self.post or (not self.stopped and after != self.post):
                raise ValueError('invalid post-trigger length')
        for i, (tick, sample) in enumerate(self.records):
            if not 0 <= tick <= 0xffffffff or not 0 <= sample < (1 << 40):
                raise ValueError('invalid record bits')
            if sample >> 38:
                raise ValueError('reserved sample bits set')
            if i and tick != (self.records[i-1][0] + 1) & 0xffffffff:
                raise ValueError('gap or duplicate in raw sample sequence')
        return self

    def encode(self):
        self.validate()
        flags = int(self.trigger_index != NO_TRIGGER) | (int(self.stopped) << 1)
        return HEADER.pack(MAGIC, 1, RECORD.size, self.clock_hz, len(self.records),
                           self.trigger_index, flags, self.pre, self.post, self.trigger_mask, self.trigger_value) + b''.join(
                               RECORD.pack(*r) for r in self.records)


def decode(blob):
    if len(blob) < HEADER.size:
        raise ValueError('truncated header')
    magic, version, size, hz, n, trigger, flags, pre, post, mask, value = HEADER.unpack_from(blob)
    if magic != MAGIC or version != 1 or size != RECORD.size or flags & ~3:
        raise ValueError('unsupported capture header')
    if bool(flags & 1) != (trigger != NO_TRIGGER):
        raise ValueError('inconsistent trigger flag')
    if len(blob) != HEADER.size + n * RECORD.size:
        raise ValueError('truncated capture or trailing data')
    return Capture(hz, pre, post, trigger, bool(flags & 2),
                   list(RECORD.iter_unpack(blob[HEADER.size:])), mask, value).validate()


def fields(sample):
    return {name: (sample >> bit) & ((1 << width)-1) for name, bit, width in SIGNALS}


def cycle_kind(sample):
    """Classify a sampled level; not an instruction or completed-cycle decoder."""
    f = fields(sample)
    if not f['reset_n']:
        return 'reset'
    if not f['iorq_n'] and not f['m1_n']:
        return 'interrupt_ack'
    if not f['mreq_n'] and not f['rfsh_n']:
        return 'refresh'
    if not f['mreq_n'] and not f['iorq_n']:
        return 'invalid'
    if not f['mreq_n'] or not f['iorq_n']:
        if f['rd_n'] == f['wr_n']:
            return 'invalid' if not f['rd_n'] else 'bus_setup'
        if not f['mreq_n']:
            if not f['rd_n']:
                return 'opcode_fetch' if not f['m1_n'] else 'memory_read'
            return 'memory_write'
        return 'io_read' if not f['rd_n'] else 'io_write'
    return 'idle'


def export_csv(capture, output):
    capture.validate()
    writer = csv.writer(output)
    writer.writerow(['sample_index', 'tick32', 'relative_ns', 'trigger', 'kind'] +
                    [s[0] for s in SIGNALS])
    for i, (tick, sample) in enumerate(capture.records):
        f = fields(sample)
        writer.writerow([i, tick, i * 1000000000 // capture.clock_hz,
                         int(i == capture.trigger_index), cycle_kind(sample)] +
                        [f[s[0]] for s in SIGNALS])


def export_vcd(capture, output):
    capture.validate()
    # Integer picoseconds suffice for supported FPGA clocks. Reject collisions.
    if capture.clock_hz > 1000000000000:
        raise ValueError('sample clock exceeds VCD resolution')
    output.write('$timescale 1ps $end\n$scope module pico1715 $end\n')
    for i, (name, _, width) in enumerate(SIGNALS):
        output.write(f'$var wire {width} s{i} {name} $end\n')
    output.write('$var wire 1 t trigger $end\n$upscope $end\n$enddefinitions $end\n')
    for i, (_, sample) in enumerate(capture.records):
        output.write(f'#{i * 1000000000000 // capture.clock_hz}\n')
        for j, (name, _, width) in enumerate(SIGNALS):
            output.write(f'b{fields(sample)[name]:0{width}b} s{j}\n')
        output.write(f'{int(i == capture.trigger_index)}t\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    pack = sub.add_parser('pack', help='pack decimal-tick/hex-sample simulation rows')
    pack.add_argument('input', type=Path)
    pack.add_argument('output', type=Path)
    pack.add_argument('--clock-hz', type=int, required=True)
    pack.add_argument('--pre', type=int, required=True)
    pack.add_argument('--post', type=int, required=True)
    pack.add_argument('--trigger-index', type=int, default=NO_TRIGGER)
    pack.add_argument('--stopped', action='store_true')
    pack.add_argument('--mask', type=lambda x: int(x, 0), default=0)
    pack.add_argument('--value', type=lambda x: int(x, 0), default=0)
    export = sub.add_parser('export')
    export.add_argument('input', type=Path)
    export.add_argument('--csv', type=Path)
    export.add_argument('--vcd', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'pack':
            records = []
            for line in args.input.read_text().splitlines():
                if line.strip():
                    tick, sample = line.split()
                    records.append((int(tick), int(sample, 16)))
            blob = Capture(args.clock_hz, args.pre, args.post, args.trigger_index,
                           args.stopped, records, args.mask, args.value).encode()
            args.output.write_bytes(blob)
        else:
            if not args.csv and not args.vcd:
                parser.error('provide --csv and/or --vcd')
            capture = decode(args.input.read_bytes())
            if args.csv:
                with args.csv.open('w', newline='') as f:
                    export_csv(capture, f)
            if args.vcd:
                with args.vcd.open('w') as f:
                    export_vcd(capture, f)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
