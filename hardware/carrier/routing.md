# Carrier routing evidence

All placed terminals outside the J3 SD hold are connected in the review PCB.
The board contains 2,206 segments and 426 vias, with GND pours on F.Cu and B.Cu.
Fresh KiCad 10.0.6 DRC reports **zero violations and 12 open connections**, all
involving J3. X2 is still unplaced and therefore does not appear in that airwire
count. This is not a fabrication release.

The SD opens comprise P3V3, five ground/shield connections, four SPI signals and
two unused-data pull-ups. The all-layer SD hold and the host connector reservation
remain intact. A readable 2025 manufacturer catalog now confirms the pin order
and main pad dimensions; the full engineering-drawing/exclusion review remains
open. See the [SD evidence](sd-review.md).

## Accepted copper

`generate_carrier_pcb.py` retains the previous hand-routed placement, power,
bypass and interlock geometry. [additional-routes.json](additional-routes.json)
adds 1,827 segments and 292 vias. Its base hash covers the original placements,
segments and vias; changing that baseline requires a new routing review.
The JSON stores copper coordinates, not executable router output.

A constrained Freerouting pass supplied most signal routes. The external tool
was `ddanila/freerouting` 2.3.1-SNAPSHOT, built from commit
`3c788799241bc9dda7f01190387615cdc3aa4018`; its JAR SHA-256 and input/session
hashes are recorded in the JSON. The input preserved existing copper as fixed,
excluded J3, removed the ground plane from the routing search and reserved the
host connector area. The run used 0.25 mm width/clearance and
`-inc plane_ground -mp 30 -mt 1 -da --gui.enabled=false`.

The router's own incomplete/violation counts are not acceptance evidence.
Import discarded additions to already-complete power/control nets, preserved
all original hand copper, and widened necked escapes back to at least 0.25 mm.
Two remaining nets, H_PRIORITY and POWER_GOOD, used targeted 0.1 mm grid path
candidates followed by clearance corrections and independent KiCad checks.
The existing KiCad 0.20 mm net-class clearance rule was not relaxed.

Front GND fill reconnects ground sections separated by signal routing. A short
SW1 return and one stitch at (52.8005, 38.380564) mm complete the ground network.
The final board has 98 ground, 10 power and 318 signal vias. Both pours stop at
the host reservation and respect the SD hold.

## Reproduction and verification

Normal regeneration needs KiCad and its footprint libraries, but no autorouter:

```sh
/usr/bin/python3 tools/generate_carrier_pcb.py
make test-carrier-schematic test-carrier-footprints test-carrier-pcb test-carrier-layout-cad
python3 tools/preview_carrier_pcb.py
```

The portable checker compares all 557 pad assignments against the schematic,
checks copper against the manifest and follows layer-aware copper connectivity
for every placed non-SD net. Fresh KiCad DRC must contain no violations and no
airwire without a held J3 endpoint. The report records these counts separately;
SD opens are reported, not waived. Tests include 44 PCB mutations and three
DRC failures, including lost newly completed routes/vias and a ground airwire.

For a future routing experiment, keep outputs outside the canonical directory:

```sh
/usr/bin/python3 tools/generate_carrier_pcb.py --base-only --output-dir local/routing-base
/usr/bin/python3 tools/prepare_carrier_routing.py local/routing/input.dsn \
  --board local/routing-base/carrier.kicad_pcb
# Run a separately installed router against input.dsn to produce output.ses.
/usr/bin/python3 tools/import_carrier_routing.py local/routing/output.ses \
  local/routing/candidate.json --base-dir local/routing-base
/usr/bin/python3 tools/generate_carrier_pcb.py \
  --additional local/routing/candidate.json --output-dir local/routing/candidate
```

A scratch DRC also needs the canonical `.kicad_pro`, footprint library table and
custom library resolvable from its directory. Do not ignore library or dangling
via failures. The preparation tool optionally accepts `--clearance .2`, matching
the existing project rule. Import creates a candidate only: it does not certify
completion or copy results into the canonical board. Additional ground stitching
and route finishing may still be necessary. Router search is heuristic; exact
reproduction of the accepted board uses the checked JSON and generator.

## Remaining release work

- Qualify the SD footprint/exclusions, then route J3.
- Resolve X2 contact/installation geometry, place its connector and route the
  host interface. Existing single-terminal host nets are not claimed connected
  to a physical motherboard socket.
- Review return paths, long parallel routes, edge rates and connector/cable
  behavior; DC continuity and geometric clearance do not qualify timing or EMC.
- Complete assembly, power, interlock and real-machine testing, then review
  manufacturing rules and release a prototype package.

See [mechanics](mechanics.md), [the roadmap](../../docs/roadmap.md) and the
[current PCB report](../../reports/carrier-pcb.json).

## Desk electrical review (2026-10-27)

The [routing metrics](../../reports/carrier-routing-review.json) screen copper
length, long parallel segments, opposite-layer ground fill and signal-via return
proximity. Reproduce with `/usr/bin/python3 tools/review_carrier_routing.py`.
These are geometric indicators, not impedance, timing or EMC qualification.

Twenty-three GND stitches were added near clock/control transitions where both
layers already had ground fill and clearance allowed a via. The total is now
98 ground, 10 power and 318 signal vias. The F_CLK transition's nearest GND via
is 1.020 mm away, down from 6.654 mm. Every new stitch passed fresh KiCad DRC;
positions and associated signal transitions are retained in additional-routes.json.

F_CLK has 204.656 mm of total routed copper; F_WR_N has 259.701 mm.
The screen flags an approximately 106.345 mm F_A0/F_A2 parallel run with 0.367 mm
edge gap. Approximately 42% of the clock trace lacks opposite-layer filled GND
at the sampled positions. Same-layer ground and PTH returns are not included in
that metric, so it does not establish a broken return or its electrical impact.
Stitching improves local return access but does not remove the long parallel runs.

Before release, assess the actual driver edge rates, cable and host loading and
measure ringing/setup/hold at the receiver. If the two-layer layout fails those
checks, revise placement/routing or stack-up; the present geometric report cannot
substitute for those measurements. See also the [assembly plan](assembly.md) and
[separate provisional X2 adapter](../x2-adapter/README.md).

## Parallel-spacing refinement and rejected shortening experiment

The long A0/A2 edge run now has 0.5066 mm edge-to-edge spacing, increased from
0.3666 mm without adding signal vias or relaxing the 0.20 mm clearance rule.
A0 moved 0.10 mm toward the board edge and A2 moved 0.04 mm inward. Fresh DRC
still reports zero violations and only the 12 held SD opens. These are geometric
improvements; no crosstalk voltage or EMC measurement is claimed.

A separate [shorter-write candidate](shorter-write-candidate.json) reduced F_WR_N
from 259.701 to 220.060 mm, but increased signal vias from four to six and the
sampled absence of opposite-layer ground from 35.61% to 66.33%. Despite passing
DRC, it was **not adopted** because the length reduction did not establish better
electrical behavior. Clock alternatives likewise added transitions or did not
shorten the route; the canonical clock copper is retained.

The saved candidate can be recreated without changing the canonical board:

```sh
python3 tools/prepare_write_route_candidate.py --output local/write-review.json
/usr/bin/python3 tools/generate_carrier_pcb.py --additional local/write-review.json \
  --output-dir local/write-review
```

Use the canonical project rules and resolve its footprint library table when
running DRC on that scratch board. The candidate generator refuses a changed
supplemental-copper baseline. Further timing/return-path improvement may require
moving components or revising the stack-up, rather than accepting a shorter
trace with worse return geometry.
