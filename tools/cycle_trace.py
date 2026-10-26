#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate/export compact cycle captures without loading a boot trace into RAM."""
import argparse
import csv
from dataclasses import dataclass
import io
from pathlib import Path
import struct

HEADER = struct.Struct('<8sHHIIIII')
TRIGGER = struct.Struct('<12I')
RECORD = struct.Struct('<BBHHHII')
MAGIC = b'P1715CY\0'
KINDS = {1: 'opcode_fetch', 2: 'memory_read', 3: 'memory_write', 4: 'io_read',
         5: 'io_write', 6: 'interrupt_ack', 7: 'refresh', 8: 'reset', 9: 'invalid'}


@dataclass(frozen=True)
class Header:
    clock_hz: int
    count: int
    dropped: int = 0
    filtered: int = 0
    capture_mask: int = 0x3fe
    trigger: tuple | None = None

    @property
    def size(self):
        return HEADER.size + (TRIGGER.size if self.trigger is not None else 0)

    def validate(self):
        if not 1 <= self.clock_hz <= 0xffffffff:
            raise ValueError('invalid clock')
        if any(not 0 <= x <= 0xffffffff for x in (self.count, self.dropped, self.filtered)):
            raise ValueError('invalid counts')
        if self.capture_mask & ~0x3fe or self.capture_mask < 0:
            raise ValueError('invalid kind mask')
        if self.trigger is not None:
            if len(self.trigger) != 12 or any(not 0 <= v <= 0xffffffff for v in self.trigger):
                raise ValueError('invalid trigger metadata')
            enabled, kinds, address, data, pre, post, fired, index, sequence, omitted, collected, reason = self.trigger
            if enabled != 1 or not kinds or kinds & ~0x170 or data > 65535 or fired not in (0, 1):
                raise ValueError('invalid trigger configuration')
            if pre + post + 1 > 458747 or omitted > self.filtered or reason not in (1, 2):
                raise ValueError('invalid trigger window')
            if fired:
                if index > pre or index >= self.count or collected > post or self.count != index + 1 + collected:
                    raise ValueError('invalid trigger position')
                if reason == 1 and collected != post:
                    raise ValueError('incomplete automatic trigger window')
            elif index != 0xffffffff or sequence != 0xffffffff or collected or reason != 2 or self.count > pre:
                raise ValueError('invalid untriggered window')
        return self

    def encode(self):
        self.validate()
        return HEADER.pack(MAGIC, 2 if self.trigger is not None else 1, RECORD.size, self.clock_hz, self.count,
                           self.dropped, self.filtered, self.capture_mask) + (TRIGGER.pack(*self.trigger) if self.trigger is not None else b'')


@dataclass(frozen=True)
class Cycle:
    kind: int
    flags: int
    data: int
    address: int
    wait_samples: int
    duration: int
    tick: int
    sequence: int

    def validate(self):
        if self.kind not in KINDS or not 0 <= self.flags <= 15:
            raise ValueError('invalid kind or flags')
        for value, maximum in ((self.data, 255), (self.address, 65535),
                               (self.wait_samples, 65535), (self.duration, 65535),
                               (self.tick, 0xffffffff), (self.sequence, 0xffffffff)):
            if not 0 <= value <= maximum:
                raise ValueError('invalid record field')
        if not self.duration or self.wait_samples > self.duration:
            raise ValueError('invalid duration/wait count')
        if self.flags & 4 and self.duration != 65535:
            raise ValueError('saturation flag without saturated duration')
        if self.kind == 8 and (self.address or self.data or self.wait_samples):
            raise ValueError('reset interval has bus payload')
        return self

    def encode(self):
        self.validate()
        return RECORD.pack((self.kind << 4) | self.flags, self.data, self.address,
                           self.wait_samples, self.duration, self.tick, self.sequence)


def read_header(stream):
    data = stream.read(HEADER.size)
    if len(data) != HEADER.size:
        raise ValueError('truncated header')
    magic, version, size, *fields = HEADER.unpack(data)
    if magic != MAGIC or version not in (1, 2) or size != RECORD.size:
        raise ValueError('unsupported compact capture header')
    trigger = None
    if version == 2:
        extra = stream.read(TRIGGER.size)
        if len(extra) != TRIGGER.size:
            raise ValueError('truncated trigger header')
        trigger = TRIGGER.unpack(extra)
    return Header(*fields, trigger=trigger).validate()


def records(stream, header):
    previous = None
    gaps = 0
    for index in range(header.count):
        data = stream.read(RECORD.size)
        if len(data) != RECORD.size:
            raise ValueError('truncated record')
        tag, value, address, wait, duration, tick, seq = RECORD.unpack(data)
        record = Cycle(tag >> 4, tag & 15, value, address, wait, duration, tick, seq).validate()
        if not header.capture_mask & (1 << record.kind):
            raise ValueError('record excluded by capture mask')
        gap = seq if previous is None else (seq - previous.sequence - 1) & 0xffffffff
        if previous:
            if seq == previous.sequence:
                raise ValueError('duplicate sequence')
            elapsed = (tick - previous.tick) & 0xffffffff
            if elapsed < previous.duration:
                raise ValueError('overlapping intervals')
        gaps += gap
        if gaps > header.dropped + header.filtered:
            raise ValueError('unexplained sequence gap')
        if header.trigger is not None and header.trigger[6] and index == header.trigger[7]:
            _, kinds, address, data, *_ = header.trigger
            if (seq != header.trigger[8] or not kinds & (1 << record.kind) or
                (record.address ^ address) & (address >> 16) or
                (record.data ^ data) & (data >> 8)):
                raise ValueError('trigger record does not match metadata')
        yield record, gap
        previous = record
    if stream.read(1):
        raise ValueError('trailing bytes')


def decode(blob):
    stream = io.BytesIO(blob)
    header = read_header(stream)
    return header, list(records(stream, header))


def export_csv(stream, header, output):
    writer = csv.writer(output)
    writer.writerow(['sequence', 'tick32', 'kind', 'address_hex', 'data_hex',
                     'duration_samples', 'wait_low_samples', 'partial_start',
                     'truncated_end', 'counter_saturated', 'address_changed', 'gap_before'] + (['trigger'] if header.trigger is not None else []))
    for r, gap in records(stream, header):
        writer.writerow([r.sequence, r.tick, KINDS[r.kind], f'{r.address:04x}',
                         f'{r.data:02x}', r.duration, r.wait_samples,
                         *[int(bool(r.flags & (1 << i))) for i in range(4)], gap] + ([int(bool(header.trigger[6]) and r.sequence == header.trigger[8])] if header.trigger is not None else []))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--csv', type=Path, help='omit to validate without exporting')
    a = p.parse_args()
    try:
        with a.input.open('rb') as source:
            header = read_header(source)
            if a.input.stat().st_size != header.size + header.count * RECORD.size:
                raise ValueError('file length does not match header')
            if a.csv:
                if a.csv.resolve() == a.input.resolve():
                    raise ValueError('input and output must differ')
                with a.csv.open('w', newline='') as output:
                    export_csv(source, header, output)
            else:
                for _ in records(source, header):
                    pass
        print(f'{header.count} records; {header.filtered} intentionally filtered; '
              f'{header.dropped} dropped; sample clock {header.clock_hz} Hz')
        if header.trigger is not None:
            print(f'triggered={bool(header.trigger[6])}; index={header.trigger[7]}; '
                  f'window omissions={header.trigger[9]}; post records={header.trigger[10]}')
    except (ValueError, OSError) as exc:
        p.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
