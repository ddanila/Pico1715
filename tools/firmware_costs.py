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


def stress_profile(value):
    """Validate and normalize an explicit, reproducible stress schedule."""
    defaults = dict(period=257, width=0, phase=0, extra_us=[0]*6,
                    sd_delays_us=[], index_phase_us=0)
    if not isinstance(value, dict) or set(value)-set(defaults):
        raise ValueError('unknown stress profile fields')
    result = defaults | value
    def integer(n, lo, hi): return type(n) is int and lo <= n <= hi
    if not integer(result['period'],1,1000000): raise ValueError('invalid stress period')
    if not integer(result['width'],0,result['period']): raise ValueError('invalid burst width')
    if not integer(result['phase'],0,result['period']-1): raise ValueError('invalid burst phase')
    for key,length in [('extra_us',6),('sd_delays_us',None)]:
        values=result[key]
        if not isinstance(values,list) or (len(values)!=length if length else len(values)>16) or any(not integer(n,0,1000000) for n in values):
            raise ValueError('invalid '+key)
    if not integer(result['index_phase_us'],-100000,100000): raise ValueError('invalid index phase')
    return result


def stress_environment(profile):
    p=stress_profile(profile)
    env={f'PICO1715_STRESS_{k.upper()}':str(p[k]) for k in ('period','width','phase','index_phase_us')}
    env.update({f'PICO1715_STRESS_EXTRA_{name}':str(v) for name,v in zip(NAMES,p['extra_us'])})
    if p['sd_delays_us']: env['PICO1715_STRESS_SD_SEQUENCE']=','.join(map(str,p['sd_delays_us']))
    return env


def stress_evidence(stderr):
    import json
    match=re.search(r'^Stress (\{.*\})$',stderr,re.M)
    if not match: raise ValueError('missing stress evidence')
    return json.loads(match[1])


def validate_stress(stats, calls):
    p=stress_profile(stats['config'])
    def prefix(n): return n//p['period']*p['width']+min(n%p['period'],p['width'])
    hits=[prefix(n+p['phase'])-prefix(p['phase']) if extra else 0
          for n,extra in zip(calls,p['extra_us'])]
    if len(calls)!=6 or stats['hits']!=hits: raise ValueError('incorrect burst accounting')
    if stats['index_resets']:
        shift=abs(p['index_phase_us'])*2458000//1000000
        expected=2458000//5+(-shift if p['index_phase_us']<0 else shift)
        if stats['index_start_tick']!=expected: raise ValueError('incorrect index phase')
    if p['sd_delays_us'] and stats['sd_calls']:
        seen=p['sd_delays_us'][:min(stats['sd_calls'],len(p['sd_delays_us']))]
        if (stats['sd_min_us'],stats['sd_max_us'])!=(min(seen),max(seen)):
            raise ValueError('incorrect SD schedule')
