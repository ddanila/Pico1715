#!/usr/bin/env python3
"""Read the standalone fixture's 115200 8N1 result from a tty or saved capture."""
import argparse
import json
import os
from pathlib import Path
import select
import struct
import termios
import time

FAILURES = {0: 'pass', 1: 'backend lost or frontend fault', 2: 'backend boot timeout',
            3: 'read data/output-enable mismatch', 4: 'host output enabled on write',
            5: 'transaction timeout', 6: 'mailbox drain timeout', 7: 'interrupt timeout',
            8: 'interrupt vector/source mismatch', 9: 'RETI notification missing',
            255: 'invalid fixture state'}


def decode(data):
    """Resynchronize after noise/truncation; accept only checksummed full frames."""
    for i in range(max(0, len(data)-8)):
        b = data[i:i+9]
        if b[0] != 0xa5:
            continue
        checksum = 0
        for v in b[:8]:
            checksum ^= v
        if checksum != b[8]:
            continue
        _, code, count, ticks = struct.unpack('<BBHI', b[:8])
        if code not in FAILURES or (code == 0 and count != 515):
            continue
        return dict(schema=1, result=FAILURES[code], failure_code=code,
                    completed_transactions=count, max_cycle_ticks=ticks,
                    max_cycle_us=ticks/25, clock_hz=25000000,
                    electrical_timing_qualified=False)
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--port', type=Path, help='3.3 V USB UART receive port')
    g.add_argument('--capture', type=Path, help='raw previously recorded UART bytes')
    p.add_argument('--timeout', type=float, default=25)
    p.add_argument('--out', type=Path, required=True, help='new JSON report file')
    a = p.parse_args()
    if a.out.exists():
        p.error('output already exists')
    if a.timeout <= 0:
        p.error('timeout must be positive')
    if a.capture:
        r = decode(a.capture.read_bytes())
    else:
        fd = os.open(a.port, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
        old = termios.tcgetattr(fd)
        try:
            config = termios.tcgetattr(fd)
            config[0] = config[1] = config[3] = 0
            config[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
            config[4] = config[5] = termios.B115200
            config[6][termios.VMIN] = 0
            config[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, config)
            end = time.monotonic()+a.timeout
            data = b''
            r = None
            while time.monotonic() < end and r is None:
                if select.select([fd], [], [], max(0, end-time.monotonic()))[0]:
                    data = (data+os.read(fd, 4096))[-8192:]
                    r = decode(data)
        finally:
            termios.tcsetattr(fd, termios.TCSANOW, old)
            os.close(fd)
    if r is None:
        p.exit(2, 'No valid fixture frame received; no result recorded.\n')
    r['source'] = str(a.port or a.capture)
    r['source_kind'] = 'serial' if a.port else 'unverified_capture'
    with a.out.open('x') as f:
        json.dump(r, f, indent=2)
        f.write('\n')
    print(f"{r['result']}: {r['completed_transactions']} transactions; "
          f"max sampled cycle {r['max_cycle_us']:.2f} us (includes fixture hold time)")
    return int(r['failure_code'] != 0)


if __name__ == '__main__':
    raise SystemExit(main())
