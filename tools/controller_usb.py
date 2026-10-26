#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read Pico1715 controller status or request orderly eject over USB CDC."""
import argparse
import binascii
import json
import struct
import time

HEADER = struct.Struct('<4sBBBBII')
FIELDS = ('state', 'dirty_blocks', 'storage_error', 'max_service_us', 'shutdown',
          'shutdown_reason', 'backup', 'write_policy', 'dirty_limit', 'storage_busy',
          'requests', 'reserve_us', 'shutdown_deadline', 'writes', 'rejected_writes',
          'overruns', 'underflows', 'tx_overruns', 'tx_underruns')
ERRORS = {1: 'malformed request', 2: 'unsupported command', 3: 'controller cannot accept command',
          4: 'control mailbox busy'}


class Client:
    def __init__(self, port, timeout=5):
        if timeout <= 0:
            raise ValueError('timeout must be positive')
        self.port, self.timeout, self.request_id = port, timeout, 0

    def exact(self, size, deadline):
        data = bytearray()
        while len(data) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('controller response timed out; reconnect and query status')
            self.port.timeout = remaining
            chunk = self.port.read(size - len(data))
            if not chunk:
                raise TimeoutError('controller response incomplete; reconnect and query status')
            data.extend(chunk)
        return bytes(data)

    def command(self, command, timeout=None):
        budget = self.timeout if timeout is None else timeout
        deadline = time.monotonic() + budget
        self.request_id = (self.request_id + 1) & 0xffffffff
        raw = struct.pack('<4sBBHI', b'P1CQ', 1, command, 0, self.request_id)
        raw += struct.pack('<I', binascii.crc32(raw))
        self.port.write_timeout = budget
        if self.port.write(raw) != len(raw):
            raise IOError('incomplete controller request; eject outcome may be unknown')
        raw = self.exact(HEADER.size, deadline)
        magic, version, cmd, error, reserved, request_id, size = HEADER.unpack(raw)
        if (magic, version, cmd, reserved, request_id) != (b'P1CR', 1, command, 0, self.request_id) or size not in (0, 112):
            raise ValueError('invalid controller response header')
        payload = self.exact(size, deadline)
        crc, = struct.unpack('<I', self.exact(4, deadline))
        if binascii.crc32(raw + payload) != crc:
            raise ValueError('controller response CRC mismatch')
        if error:
            raise RuntimeError(ERRORS.get(error, f'device error {error}'))
        if size != 112:
            raise ValueError('invalid controller status size')
        return dict(zip(FIELDS, struct.unpack('<10I9Q', payload)))

    def status(self):
        return self.command(1)

    def eject(self, timeout=30):
        if timeout <= 0:
            raise ValueError('eject timeout must be positive')
        deadline = time.monotonic() + timeout
        status = self.command(2, min(self.timeout, timeout))
        while status['shutdown'] in (0, 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('eject still pending; keep power on and query status')
            time.sleep(min(0.05, remaining))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('eject still pending; keep power on and query status')
            status = self.command(1, min(self.timeout, remaining))
        if status['shutdown'] != 2 or status['dirty_blocks'] or status['storage_busy'] or status['storage_error']:
            raise RuntimeError(f"eject UNSAFE: {json.dumps(status)}")
        return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--timeout', type=float, default=5, help='seconds per USB request')
    parser.add_argument('--eject-timeout', type=float, default=30)
    parser.add_argument('command', choices=('status', 'eject'))
    args = parser.parse_args()
    import serial
    try:
        with serial.Serial(args.port, timeout=args.timeout, write_timeout=args.timeout) as port:
            client = Client(port, args.timeout)
            result = client.status() if args.command == 'status' else client.eject(args.eject_timeout)
            print(json.dumps(result, indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
