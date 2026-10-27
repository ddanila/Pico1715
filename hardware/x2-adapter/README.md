# Provisional X2 passive breakout

This separate 100 × 33 mm PCB routes all 58 EFS58 contacts to a 2×30, 2.54 mm
header. It provides an inspectable adapter and continuity fixture. It is **not
released for fabrication or host insertion**, and does not place X2 on the carrier.

The [schematic](adapter.kicad_sch), [PCB](adapter.kicad_pcb),
[contact map](harness.md) and [1:1 drilling template](drilling-template.svg)
use the audited [202-58 Form 7 reference](../carrier/efs58/investigation.md).
A contacts go to odd header pins; B contacts go to even pins; 59/60 are NC.
All traces are separate, including host ground contacts. No active electronics,
power source, pull-ups or bus termination are fitted.

The connector PCB tails have 2.5 mm contact pitch and 5 mm row spacing; the
mating rows are 2.5 mm apart. Mounting holes are 85 mm apart, diameter 2.7 mm.
The board edge is 6.5 mm toward the connector from row A. Finished contact holes
of 1.0 mm and pads of 1.8 mm are design choices, not certified contact-fit limits.
The original edge datum puts mounting-hole centres only 1.5 mm inside the edge;
verify the actual connector mounting hardware before approving this outline.

A/B numbering is derived from the termination drawing. A real sample must
confirm orientation, contact fit, body envelope, mounting and motherboard
clearance. The template does not model the connector body or a proven printable
housing. Print at 100% and check its 10 mm scale bar. The 2×30 header is a
provisional probing/harness interface; cable length and signal integrity remain
unqualified. Power pins must not be wired from this map without verifying both
ends against the host and carrier schematics.

Regenerate with `/usr/bin/python3 tools/generate_x2_adapter.py`; verify with
`make test-x2-adapter-cad`. The copied KiCad header footprint retains its upstream
library provenance; the project's MIT license does not relicense third-party
library assets. The EFS reference footprint and generator are original work.
