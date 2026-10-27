# Carrier routing evidence

All placed terminals outside the J3 SD hold are connected in the review PCB.
The board contains 2,206 segments and 403 vias, with GND pours on F.Cu and B.Cu.
Fresh KiCad 10.0.6 DRC reports **zero violations and 12 open connections**, all
involving J3. X2 is still unplaced and therefore does not appear in that airwire
count. This is not a fabrication release.

The SD opens comprise P3V3, five ground/shield connections, four SPI signals and
two unused-data pull-ups. The all-layer SD hold and the host connector reservation
remain intact. The Hirose dimensional drawing could not be visually reviewed
(the download returned 403 and the browser view was blank), so no land-pattern
or exclusion approval is inferred from this routing work.

## Accepted copper

`generate_carrier_pcb.py` retains the previous hand-routed placement, power,
bypass and interlock geometry. [additional-routes.json](additional-routes.json)
adds 1,827 segments and 269 vias. Its base hash covers the original placements,
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
The final board has 75 ground, 10 power and 318 signal vias. Both pours stop at
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
