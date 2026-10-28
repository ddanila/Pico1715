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
TRACE_FIELDS = ('capability', 'capture_state', 'records', 'fpga_dropped', 'local_dropped',
                'total_bytes', 'cursor', 'chunk_bytes', 'framing_errors', 'crc_errors', 'filtered', 'pending_command')
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
        if 3 <= command <= 7:
            status = dict(zip(TRACE_FIELDS, struct.unpack('<12I', payload[:48])))
            n = status['chunk_bytes']
            if n > 64:
                raise ValueError('invalid trace chunk size')
            status['data'] = payload[48:48+n]
            return status
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

    def trace_stop(self, timeout=30):
        deadline = time.monotonic() + timeout
        status = self.command(4)
        while status['capture_state'] not in (4, 5):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('capture has not drained; keep controller powered')
            time.sleep(min(.05, remaining))
            status = self.command(5, min(self.timeout, max(.001, deadline-time.monotonic())))
        if status['capture_state'] != 4:
            raise RuntimeError('capture failed; no complete trace can be downloaded')
        return status

    def trace_save(self, path):
        # The device enforces SAFE eject. Never implicitly eject a running guest.
        status = self.command(7)
        total = status['total_bytes']
        if status['capture_state'] != 4 or not 32 <= total <= 7*1024*1024:
            raise ValueError('invalid completed trace size/state')
        data = bytearray()
        while len(data) < total:
            part = self.command(6)
            chunk = part['data']
            if not chunk or part['cursor'] != len(data)+len(chunk) or part['total_bytes'] != total:
                raise ValueError('trace cursor or length changed; rewind and retry')
            data.extend(chunk)
        if len(data) != total or data[:8] != b'P1715CY\0':
            raise ValueError('invalid trace data')
        with open(path, 'xb') as output:
            output.write(data)
        return {'path': str(path), 'bytes': total, 'hardware_qualification': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--timeout', type=float, default=5, help='seconds per USB request')
    parser.add_argument('--eject-timeout', type=float, default=30)
    parser.add_argument('--output', help='new output file for trace-save')
    parser.add_argument('command', choices=('status', 'eject', 'trace-start', 'trace-stop', 'trace-status', 'trace-save'))
    args = parser.parse_args()
    if args.command == 'trace-save' and not args.output:
        parser.error('trace-save requires --output')
    import serial
    try:
        with serial.Serial(args.port, timeout=args.timeout, write_timeout=args.timeout) as port:
            client = Client(port, args.timeout)
            if args.command == 'status': result = client.status()
            elif args.command == 'eject': result = client.eject(args.eject_timeout)
            elif args.command == 'trace-stop': result = client.trace_stop(args.eject_timeout)
            elif args.command == 'trace-save': result = client.trace_save(args.output)
            else: result = client.command(3 if args.command == 'trace-start' else 5)
            result.pop('data', None)
            print(json.dumps(result, indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
