#!/usr/bin/env python3
"""Extract additional copper from a local router SES, preserving hand routes.

Writes a candidate JSON, never overwrites the canonical board. Review the
candidate with the generator, independent connectivity checker and KiCad DRC.
"""
import argparse
import hashlib
import json
from pathlib import Path
import pcbnew as k

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'hardware/carrier'


def point(p):
    return [round(k.ToMM(p.x), 6), round(k.ToMM(p.y), 6)]


def uncovered(a, z, existing):
    """Subtract collinear hand-route intervals (SES may split fixed tracks)."""
    dx, dy = z[0]-a[0], z[1]-a[1]
    length2 = dx*dx+dy*dy
    if length2 < 1e-12:
        return []
    intervals = [(0., 1.)]
    for start, end in existing:
        if any(abs((p[0]-a[0])*dy-(p[1]-a[1])*dx) > 1e-5
               for p in (start, end)):
            continue
        lo, hi = sorted(((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length2
                        for p in (start, end))
        updated = []
        for x, y in intervals:
            if hi <= x or lo >= y:
                updated.append((x, y))
            else:
                if lo > x: updated.append((x, lo))
                if hi < y: updated.append((hi, y))
        intervals = updated
    return [([round(a[0]+x*dx, 6), round(a[1]+x*dy, 6)],
             [round(a[0]+y*dx, 6), round(a[1]+y*dy, 6)])
            for x, y in intervals if y-x > 1e-8]


def extract(session, output, base_dir=BASE):
    original = base_dir/'carrier.kicad_pcb'
    plan = json.loads((base_dir/'pcb-placement.json').read_text())
    assert not any(t['tag'].startswith('additional/') for t in plan['routes']), \
        'extract against the hand-routed baseline, not an already supplemented board'
    board = k.LoadBoard(str(original))
    assert k.ImportSpecctraSES(board, str(session)), 'SES import failed'
    # Only accept additions on nets with outstanding non-SD signal connections.
    completed = {'GND', 'V3P3', 'V5_HOST', 'V5_MODULE', 'P3V3', 'P_VSYS',
                 'PG3', 'PG5', 'PGP', 'RAILS_OK', 'POWERED', 'QUALIFIED',
                 'BACKEND_OK', 'RESET_OK', 'LINK_OK', 'LINK_OE_N', 'CDONE',
                 'PERSONALITY_CTL'}
    old = {}
    for t in plan['routes']:
        old.setdefault((t['net'], t['layer'], t['width']), []).append((t['start'], t['end']))
    old_vias = {(v['net'], tuple(v['at'])) for v in plan['vias']}
    routes, vias = [], []
    for t in board.GetTracks():
        net = t.GetNetname().removeprefix('/')
        if net in completed:
            continue
        if isinstance(t, k.PCB_VIA):
            at = point(t.GetPosition())
            if (net, tuple(at)) not in old_vias:
                vias.append(dict(net=net, at=at, diameter=round(k.ToMM(t.GetWidth(k.F_Cu)), 6),
                                 drill=round(k.ToMM(t.GetDrillValue()), 6)))
            continue
        layer = board.GetLayerName(t.GetLayer())
        width = round(k.ToMM(t.GetWidth()), 6)
        for a, z in uncovered(point(t.GetStart()), point(t.GetEnd()),
                              old.get((net, layer, width), [])):
            if a != z:
                # Freerouting may neck down SMT escapes below the requested
                # width. Restore our minimum before independent KiCad DRC;
                # widening is never evidence of clearance by itself.
                routes.append(dict(net=net, start=a, end=z, width=max(.25, width), layer=layer))
    routes.sort(key=lambda t: (t['net'], t['layer'], t['start'], t['end']))
    vias.sort(key=lambda v: (v['net'], v['at']))
    base_hash=hashlib.sha256(json.dumps({key:plan[key] for key in ['placements','routes','vias']},sort_keys=True).encode()).hexdigest()
    result = dict(schema=1, base_route_sha256=base_hash, source_board_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                  session_sha256=hashlib.sha256(session.read_bytes()).hexdigest(),
                  minimum_imported_width_mm=.25,
                  omitted_refs=['J3'], unplaced_refs=['X2'], routes=routes, vias=vias)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(f'Candidate: {len(routes)} segments, {len(vias)} vias; must pass DRC')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--base-dir', type=Path, default=BASE,
                        help='directory generated with generate_carrier_pcb.py --base-only')
    args = parser.parse_args()
    extract(args.session, args.output, args.base_dir)
