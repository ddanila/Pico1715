#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Private line-protocol adapter for the shared JS experiment runner."""
import ctypes as C
import json
import sys

m = C.CDLL(sys.argv[1])
for name in ('ram', 'disk', 'screen', 'capture_data'):
    getattr(m, 'p1715_' + name).restype = C.c_void_p
m.p1715_stat.restype = C.c_double
m.p1715_init.argtypes = [C.c_void_p, C.c_uint, C.c_void_p, C.c_uint, C.c_int]
calls = {'version': 0, 'stat': 1, 'reg': 1, 'run': 1, 'key': 1, 'reset': 0,
         'cancel': 0, 'break': 1, 'export': 0, 'capture_start': 3,
         'capture_stop': 0, 'capture_release': 0, 'capture_status': 1}
calls.update(sim_capabilities=0, sim_fault=2, sim_config=1)
for line in sys.stdin:
    try:
        req = json.loads(line)
        if req['op'] == 'init':
            rom, disk = bytes.fromhex(req['rom']), bytes.fromhex(req['disk'])
            if req.get('absent') and m.p1715_sim_config(1):
                raise ValueError('Initial media configuration rejected')
            result = m.p1715_init(rom, len(rom), disk, len(disk), req['writable'])
        elif req['op'] == 'call':
            name, args = req['name'], req['args']
            if name not in calls or len(args) != calls[name]:
                raise ValueError('Unsupported call')
            result = getattr(m, 'p1715_' + name)(*args)
        elif req['op'] == 'read':
            name, length = req['name'], req['length']
            bounds = {'ram': 65536, 'disk': 819200, 'screen': 1920,
                      'capture_data': m.p1715_capture_status(2)}
            if name not in bounds or not 0 <= length <= bounds[name]:
                raise ValueError('Invalid read')
            result = C.string_at(getattr(m, 'p1715_' + name)(), length).hex()
        else:
            raise ValueError('Unsupported operation')
        print(json.dumps({'result': result}), flush=True)
    except Exception as error:
        print(json.dumps({'error': str(error)}), flush=True)
