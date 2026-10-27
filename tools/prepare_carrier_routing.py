#!/usr/bin/env python3
"""Export a constrained DSN for a local router; requires KiCad pcbnew.

The router never owns the schematic, placement, SD hold or existing copper.
Use an ignored output directory; import and verify a candidate separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import pcbnew as k

ROOT = Path(__file__).resolve().parents[1]


def prepare(board_path, output, clearance=.25):
    board = k.LoadBoard(str(board_path))
    board.BuildConnectivity()
    raw = output.with_suffix('.raw.dsn')
    output.parent.mkdir(parents=True, exist_ok=True)
    assert k.ExportSpecctraDSN(board, str(raw))
    source = raw.read_text()
    # Work on the exporter grammar rather than deleting footprints through
    # pcbnew: KiCad 10's SWIG ownership can invalidate embedded zone pointers.
    source, n = re.subn(r'    \(plane /GND .*?\)\)\n', '', source, flags=re.S)
    assert n in (1, 2), 'expected one or two ground pours'
    source, n = re.subn(r'^.*\(place J3 .*\n', '', source, flags=re.M)
    assert n == 1, 'expected one held SD socket'
    source = re.sub(r'\bJ3-[\w@]+\s*', '', source)
    source = source.replace('(width 200)', '(width 250)')
    source = source.replace('(clearance 200)', f'(clearance {round(clearance*1000)})')
    source = source.replace('(type route)', '(type fix)')
    via = '(via "Via[0-1]_600:300_um")'
    assert source.count(via) == 1
    source = source.replace(via,
        '(keepout "host-reserved" (rect F.Cu 20000 -230000 180000 -201000))\n'
        '    (keepout "host-reserved" (rect B.Cu 20000 -230000 180000 -201000))\n'
        '    ' + via)
    start = source.index('    (class kicad_default')
    prefix, classes = source[:start], source[start:]
    assert ' /GND ' in classes
    classes = classes.replace(' /GND ', ' ', 1)
    source = prefix + ('    (class plane_ground /GND '
        '(circuit (use_via "Via[0-1]_600:300_um")) '
        f'(rule (width 250) (clearance {round(clearance*1000)})))\n') + classes
    output.write_text(source)
    evidence = dict(board_sha256=hashlib.sha256(board_path.read_bytes()).hexdigest(),
                    dsn_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                    kicad_version=k.GetBuildVersion(),
                    omitted_refs=['J3'], unplaced_refs=['X2'],
                    excluded_net_class='plane_ground',
                    fixed_existing_copper=True, width_mm=.25, clearance_mm=clearance)
    output.with_suffix('.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--board', type=Path,
                        default=ROOT/'hardware/carrier/carrier.kicad_pcb')
    parser.add_argument('--clearance', type=float, choices=[.2,.25], default=.25,
                        help='mm; .20 is the existing KiCad net-class rule')
    args = parser.parse_args()
    prepare(args.board, args.output, args.clearance)
