# SPDX-License-Identifier: MIT
"""Shared parsing for injected firmware execution costs and bridge evidence."""
import argparse
import re

NAMES = ('POLL', 'FIELD', 'READ', 'WRITE', 'COMMIT', 'SNAPSHOT')

def parse_costs(value):
    try:
        parts = value.split(',')
        if len(parts) != len(NAMES) or any(not p.isascii() or not p.isdecimal() for p in parts):
            raise ValueError
        result = tuple(map(int, parts))
        if any(n > 1000000 for n in result):
            raise ValueError
        return result
    except ValueError:
        raise argparse.ArgumentTypeError('costs must be six comma-separated integers from 0 to 1000000') from None

def environment(costs):
    return {f'PICO1715_COST_{name}_US': str(value) for name, value in zip(NAMES, costs)}

def evidence(stderr):
    match = re.search(r'Costs config=\[([\d,]+)\] calls=\[([\d,]+)\] yields=(\d+) lock_wait_us=(\d+) faults=(\d+) first_fault_us=(\d+)', stderr)
    if not match:
        raise ValueError('missing firmware cost evidence')
    config, calls = (list(map(int, match[i].split(','))) for i in (1, 2))
    if len(config) != 6 or len(calls) != 6:
        raise ValueError('invalid cost evidence')
    return dict(config=config, calls=calls, **dict(zip(
        ('yields', 'lock_wait_us', 'faults', 'first_fault_us'), map(int, match.groups()[2:]))))
