#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind ZMAC listing addresses to exact binary and source identities."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def generate(source, listing, binary, base, space, include_source=False):
    if not 0 <= base < 65536 or not binary or base + len(binary) > 65536:
        raise ValueError('Binary mapping exceeds 64 KiB')
    if space not in ('rom', 'ram'):
        raise ValueError('Unknown address space')
    text = source.read_bytes().decode('utf-8')
    lines = text.splitlines()
    entries, symbols = [], []
    current = source.name
    for row in listing.splitlines():
        marker = re.fullmatch(r'\*\*\*\* (.+) \*\*\*\*', row)
        if marker:
            current = Path(marker[1]).name
            continue
        match = re.match(r'^\s*(\d+):[^\t]*\t([0-9A-F]{4})\s+([0-9A-F]{2,8})\s*\t(.*)$', row)
        if match and current == source.name:
            line, address = int(match[1]), int(match[2], 16)
            emitted = bytes.fromhex(match[3])
            offset = address - base
            if not 0 <= offset < len(binary) or binary[offset:offset+len(emitted)] != emitted:
                raise ValueError(f'Listing differs from binary at {address:04x}')
            if not 1 <= line <= len(lines) or lines[line-1].strip() != match[4].strip():
                raise ValueError(f'Listing differs from source at line {line}')
            statement = re.sub(r'^\s*[\w.$]+:\s*', '', lines[line-1]).strip()
            code = not bool(re.match(r'(db|dw|ds|defb|defw|defs)\b', statement, re.I))
            entries.append({'address': address, 'length': len(emitted), 'line': line, 'code': code})
        symbol = re.match(r'^([\w.$]+)\s+([0-9A-F]{4})\s+\d+\s*$', row)
        if symbol and base <= int(symbol[2], 16) < base + len(binary):
            symbols.append({'name': symbol[1], 'address': int(symbol[2], 16)})
    if not entries:
        raise ValueError('No verified source locations')
    if len({e['address'] for e in entries}) != len(entries):
        raise ValueError('Overlapping listing addresses')
    sha = lambda data: hashlib.sha256(data).hexdigest()
    result = {'schema': 1, 'kind': 'pico1715-source-map', 'base': base, 'space': space,
              'binary_sha256': sha(binary), 'binary_size': len(binary),
              'source': {'name': source.name, 'sha256': sha(source.read_bytes())},
              'entries': entries, 'symbols': symbols}
    if include_source:
        result['source']['text'] = text
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'listing', 'binary', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--base', type=lambda n: int(n, 0), required=True)
    parser.add_argument('--space', choices=['rom', 'ram'], required=True)
    parser.add_argument('--include-source', action='store_true')
    args = parser.parse_args()
    result = generate(args.source, args.listing.read_text(), args.binary.read_bytes(),
                      args.base, args.space, args.include_source)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
