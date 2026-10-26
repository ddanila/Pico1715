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
ERRORS = {1: 'invalid command', 2: 'capture state does not permit command',
          3: 'capture ID changed', 4: 'invalid read range', 5: 'capture unavailable'}


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

    def command(self, command, generation=0, offset=0, length=0):
        self.request_id = (self.request_id + 1) & 0xffffffff
        request = REQUEST.pack(b'P17Q', 1, command, 0, self.request_id, generation, offset, length)
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
        if command in (3, 4) and gen != generation:
            raise ValueError('capture ID changed')
        if command == 4:
            if size != length:
                raise ValueError('short capture chunk')
            return payload
        if size != 40:
            raise ValueError('invalid status size')
        status = dict(zip(FIELDS, struct.unpack('<10I', payload)))
        if status['generation'] != gen:
            raise ValueError('inconsistent capture ID')
        return status

    def status(self):
        return self.command(1)

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
        if total != 32 + 16 * status['records'] or total > 7 * 1024 * 1024:
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
    for name in ('status', 'arm', 'stop'):
        sub.add_parser(name)
    sub.add_parser('download').add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        import serial
    except ImportError:
        parser.error('USB access requires pyserial: python3 -m pip install pyserial')
    try:
        with serial.Serial(args.port, 115200, timeout=3, write_timeout=3) as port:
            # DTR drop resets protocol framing, never the capture or CPU.
            port.dtr = False
            time.sleep(0.1)
            port.reset_input_buffer()
            port.dtr = True
            time.sleep(0.1)
            client = Client(port)
            result = client.download(args.output) if args.command == 'download' else getattr(client, args.command)()
            print(json.dumps(result, indent=2))
    except (OSError, RuntimeError, ValueError, TimeoutError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
