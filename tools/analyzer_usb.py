#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Control Pico1715 analyzer over USB CDC and download completed captures."""
import argparse
import binascii
import json
import os
from pathlib import Path
import struct
import tempfile
import time
from cycle_trace import read_header, records

REQUEST = struct.Struct('<4sBBHIIII')
RESPONSE = struct.Struct('<4sBBBBIIIII')
FIELDS = ('state', 'generation', 'records', 'bytes', 'fpga_dropped',
          'local_dropped', 'filtered', 'retries', 'full', 'stopping')
TRIGGER_FIELDS = ('enabled', 'kinds', 'address', 'data', 'pre', 'post', 'triggered',
                  'trigger_index', 'trigger_sequence', 'omitted', 'post_collected', 'stop_reason')
RESET_FIELDS = ('enabled', 'reset_state', 'reset_id', 'capture_generation', 'requested_us32',
                'asserted_us32', 'released_observed_us32', 'reason')
ERRORS = {1: 'invalid command', 2: 'capture state does not permit command',
          3: 'capture ID changed', 4: 'invalid read range', 5: 'capture unavailable',
          6: 'reset accessory unavailable', 7: 'reset token changed'}


class Client:
    def __init__(self, port):
        self.port = port
        self.request_id = 0

    def exact(self, size):
        data = bytearray()
        while len(data) < size:
            piece = self.port.read(size - len(data))
            if not piece:
                raise TimeoutError('USB response incomplete; reconnect and retry')
            data.extend(piece)
        return bytes(data)

    def command(self, command, generation=0, offset=0, length=0, payload=b''):
        self.request_id = (self.request_id + 1) & 0xffffffff
        request = REQUEST.pack(b'P17Q', 1, command, 0, self.request_id, generation, offset, length) + payload
        if self.port.write(request) != len(request):
            raise IOError('incomplete USB request')
        raw = self.exact(RESPONSE.size)
        magic, version, cmd, error, reserved, req, gen, pos, size, crc = RESPONSE.unpack(raw)
        if (magic, version, cmd, reserved, req, pos) != (b'P17R', 1, command, 0, self.request_id, offset) or size > 1024:
            raise ValueError('invalid USB response header')
        payload = self.exact(size)
        if binascii.crc32(raw[:24] + payload) != crc:
            raise ValueError('USB response CRC mismatch')
        if error:
            raise RuntimeError(ERRORS.get(error, f'device error {error}'))
        if command in (3, 4, 5, 6, 8) and gen != generation:
            raise ValueError('capture ID changed')
        if command in (7, 8, 9):
            if size != 32:
                raise ValueError('invalid reset status size')
            result = dict(zip(RESET_FIELDS, struct.unpack('<8I', payload)))
            result['generation'] = gen
            return result
        if command == 4:
            if size != length:
                raise ValueError('short capture chunk')
            return payload
        if command in (5, 6):
            if size != 48:
                raise ValueError('invalid trigger status size')
            return dict(zip(TRIGGER_FIELDS, struct.unpack('<12I', payload)))
        if size != 40:
            raise ValueError('invalid status size')
        status = dict(zip(FIELDS, struct.unpack('<10I', payload)))
        if status['generation'] != gen:
            raise ValueError('inconsistent capture ID')
        return status

    def status(self):
        return self.command(1)

    def configure_trigger(self, enabled=0, kinds=0, address=0, data=0, pre=0, post=0):
        generation = self.status()['generation']
        return self.command(5, generation, 0, 24, struct.pack('<6I', enabled, kinds, address, data, pre, post))

    def trigger_status(self, generation=None):
        if generation is None:
            generation = self.status()['generation']
        return self.command(6, generation)

    def reset_status(self):
        return self.command(7)

    def reset(self, arm=False, timeout=2):
        status = self.reset_status()
        if not status['enabled']:
            raise RuntimeError('reset accessory unavailable')
        status = self.command(9 if arm else 8, status['generation'], status['reset_id'])
        token = status['reset_id']
        deadline = time.monotonic() + timeout
        while status['reset_state'] in (1, 2):
            if time.monotonic() >= deadline:
                raise TimeoutError('reset completion unknown; query reset-status before another reset')
            time.sleep(0.01)
            status = self.reset_status()
            if status['reset_id'] != token:
                raise RuntimeError('reset token changed while waiting')
        if status['reset_state'] != 3:
            raise RuntimeError(f"reset cancelled/failed, reason {status['reason']}")
        return status

    def arm_reset(self):
        return self.reset(arm=True)

    def arm(self):
        return self.command(2, self.status()['generation'])

    def stop(self, timeout=15):
        status = self.status()
        generation = status['generation']
        status = self.command(3, generation)
        deadline = time.monotonic() + timeout
        while status['state'] != 4:
            if status['state'] == 5:
                raise RuntimeError('capture failed; incomplete data cannot be downloaded')
            if time.monotonic() >= deadline:
                raise TimeoutError('capture still draining; query status before retrying')
            time.sleep(0.05)
            status = self.status()
            if status['generation'] != generation:
                raise ValueError('capture ID changed while stopping')
        return status

    def download(self, destination):
        destination = Path(destination)
        if destination.exists():
            raise FileExistsError(destination)
        status = self.status()
        if status['state'] != 4:
            raise RuntimeError('stop capture and wait for DONE before downloading')
        total = status['bytes']
        if total - 16 * status['records'] not in (32, 80) or total > 7 * 1024 * 1024:
            raise ValueError('invalid capture size')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=destination.name+'.', suffix='.part', delete=False) as stream:
                temporary = Path(stream.name)
                for offset in range(0, total, 1024):
                    stream.write(self.command(4, status['generation'], offset, min(1024, total-offset)))
                stream.flush()
                os.fsync(stream.fileno())
            with temporary.open('rb') as stream:
                header = read_header(stream)
                if sum(1 for _ in records(stream, header)) != status['records']:
                    raise ValueError('capture record count differs')
            # Atomic publication without replacing an existing user file.
            os.link(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True, help='CDC serial port, e.g. /dev/ttyACM0')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('status', 'stop', 'reset-status'):
        sub.add_parser(name)
    reset = sub.add_parser('reset')
    reset.add_argument('--reset-log', type=Path, help='save command metadata to a new JSONL file')
    for name in ('arm', 'arm-reset'):
        arm = sub.add_parser(name)
        if name == 'arm-reset':
            arm.add_argument('--reset-log', type=Path, help='save command metadata to a new JSONL file')
        arm.add_argument('--trigger', choices=('io-read', 'io-write', 'io', 'iack', 'reset'))
        arm.add_argument('--address', type=lambda s: int(s, 0))
        arm.add_argument('--address-mask', type=lambda s: int(s, 0))
        arm.add_argument('--data', type=lambda s: int(s, 0))
        arm.add_argument('--data-mask', type=lambda s: int(s, 0))
        arm.add_argument('--pre', type=int, default=0, help='preceding retained records')
        arm.add_argument('--post', type=int, default=0, help='following retained records')
    sub.add_parser('download').add_argument('output', type=Path)
    args = parser.parse_args()
    config = None
    if args.command in ('arm', 'arm-reset'):
        if args.address_mask is None:
            args.address_mask = 65535 if args.address is not None else 0
        if args.data_mask is None:
            args.data_mask = 255 if args.data is not None else 0
        args.address = args.address or 0
        args.data = args.data or 0
        if not (0 <= args.address <= 65535 and 0 <= args.address_mask <= 65535 and
                0 <= args.data <= 255 and 0 <= args.data_mask <= 255 and
                0 <= args.pre <= 458746 and 0 <= args.post <= 458746):
            parser.error('trigger masks/values or window size out of range')
        if not args.trigger and any((args.address, args.address_mask, args.data, args.data_mask, args.pre, args.post)):
            parser.error('trigger options require --trigger')
        kinds = {'io-read': 16, 'io-write': 32, 'io': 48, 'iack': 64, 'reset': 256}
        config = dict(enabled=int(bool(args.trigger)), kinds=kinds.get(args.trigger, 0),
                      address=args.address | args.address_mask << 16,
                      data=args.data | args.data_mask << 8, pre=args.pre, post=args.post)
    try:
        import serial
    except ImportError:
        parser.error('USB access requires pyserial: python3 -m pip install pyserial')
    try:
        from contextlib import ExitStack
        with ExitStack() as stack:
            log_path = getattr(args, 'reset_log', None)
            log = stack.enter_context(log_path.open('x')) if log_path else None
            if log:
                log.write(json.dumps({'command': args.command, 'port': args.port}) + '\n')
                log.flush()
            port = stack.enter_context(serial.Serial(args.port, 115200, timeout=3, write_timeout=3))
            # DTR drop resets protocol framing, never the capture or CPU.
            port.dtr = False
            time.sleep(0.1)
            port.reset_input_buffer()
            port.dtr = True
            time.sleep(0.1)
            client = Client(port)
            if config is not None:
                client.configure_trigger(**config)
            result = client.download(args.output) if args.command == 'download' else getattr(client, args.command.replace('-', '_'))()
            if log:
                log.write(json.dumps({'result': result}) + '\n')
                log.flush()
            result['trigger'] = client.trigger_status(result['generation'])
            print(json.dumps(result, indent=2))
    except (OSError, RuntimeError, ValueError, TimeoutError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
