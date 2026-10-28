# Rev A carrier engineering candidate

**Not for fabrication or connection to a 1715.** This directory is a separate
four-layer development candidate. The reviewed two-layer baseline remains in
`../carrier`. No physical validation is claimed.

The electrical ECO replaces the unplaced X2 schematic symbol with J6, a 60-pin
2.54 mm keyed IDC header candidate, and adds J7 for optional reserve power.
All 76 schematic components are placed. ERC and DRC are checked afresh by the
CAD target. The SD socket is now Würth 693071010811, with all connections closed.
J6 uses the exact 61206021621 drawing dimensions, including 1.10 mm holes.
J7's 0.95 mm finished holes match the JST 0.90–1.00 mm reference range.
See `sd-replacement-review.md` and `connector-review.json` for sources and limits.
Drawing checks do not claim physical fit or signal-integrity qualification.

## Harness and power

Use a straight-through keyed 60-conductor cable, maximum 100 mm, to a separate
EFS58 adapter. The **electrical** assignment is A1→1, B1→2, … A29→57,
B29→58; pins 59 and 60 are NC. Every contact, including existing unused
contacts, is in `connections.json`. This mapping is not a claim about the
EFS contact fit. J6 top-view pin 1 is at (60,215), pin 2 at
(60,212.46); the key faces south, toward the odd row. The mate-facing view
is mirrored: assemble by pin numbers and verify continuity before use. Do not infer orientation
from a mirrored photograph or wire-colour convention.

J7 is a power connector, not a status/GPIO port:

| Pin | Net | Function |
| --- | --- | --- |
| 1 | GND | Common return |
| 2 | V5_MODULE | Raw module supply |
| 3 | P_VSYS | Backed Pico supply |

Keep D1 fitted. Leave J7 empty for the initial assembly; the reserve daughterboard
is not included in the first order. Never jumper pins 2 and 3 as an improvised
reserve bypass. The normal D1 feed already supports operation without reserve.
Reserve status uses Pico SP/CE GP32/33/36 separately; the firmware supervisor
must not report a protected write budget without measured hold-up evidence.

## Layout and validation

The candidate is 160 × 210 mm. F.Cu/B.Cu carry signals and power; In1.Cu/In2.Cu
are GND. The proposed 1.6 mm ENIG stack-up targets JLC04161H-7628 but remains
subject to supplier confirmation. The SD body exclusion applies only to F.Cu.
Existing outer copper is retained; the routing workflow removes F_CLK and
F_WR_N for re-routing and adds the host/reserve connections. Router output is
never itself sign-off evidence.

- `make test-carrier-reva`: portable net parity and interface mutation tests.
- `make test-carrier-reva-cad`: fresh schematic export, ERC and DRC review.
  It explicitly permits and **reports** open connections; it is not an order gate.
- `python3 tools/package_carrier_reva.py --out local/reva-review-<unique-name>`:
  freshly checked, hashed engineering review ZIP. No order Gerbers are included.
- `/usr/bin/python3 tools/prepare_carrier_reva_routing.py --out local/reva-router`:
  outer-layer router input with SD present and ground excluded.
- `/usr/bin/python3 tools/import_carrier_reva_routing.py local/reva-router local/reva-routes.json`:
  candidate additions from `carrier.ses`; import into the generator with
  `--routes`, then refill/check independently before adoption.

Regenerate the schematic with `python3 tools/generate_carrier_reva.py`, export
its netlist with KiCad's `kicadxml` format, then generate the PCB with
`/usr/bin/python3 tools/generate_carrier_reva_pcb.py`. The board generator needs
KiCad 10's system Python module. It uses the checked-in `routes.json` by default. `--base-only` explicitly
creates the uncompleted placement candidate. `--routes` selects a different
candidate for review.

A fabrication release still needs closure of the remaining return-path outliers,
a complete assembly review,
independently inspected fabrication exports, source hashes and a delivered
Estonia quote. Physical EFS fit, power isolation, signal integrity and functional
bring-up remain later gates. Assemble and test one board before populating four
more. CPU RESET2 remains an input, not a board-driven CPU reset output.
