# Footprint audit and placement allocation

The [partially routed review PCB](carrier.kicad_pcb) now places 74 electrical footprints
and four provisional mounting holes. [Board preview](preview/pcb-placement.svg)
and [coordinates](pcb-placement.json) accompany it; the
[bottom copper preview](preview/pcb-ground.svg) shows the ground plane and SD exclusion.
X2 is the sole unplaced
schematic component. The earlier [allocation drawing](preview/placement-study.svg)
remains historical context; its zones are not the current board geometry.

The 160 x 210 mm outline is deliberately roomy for reviewing connectivity and
access. It is not an enclosure-fit result or a cost-optimized production size.
Receivers are grouped toward the host reservation, link switches beside the Pico,
and interlock gates and supervisors in separate functional groups. Eighteen IC
bypass capacitors now sit beside their supply pins. Local power/ground routes and
a bottom ground plane are present; most signal and rail distribution remains open. Four M3 clearance holes are provisional carrier
mounts, not HX8K or PC1715 mounting coordinates.

| Reference | Selection | Evidence and remaining check |
| --- | --- | --- |
| SW1 | C&K JS202011JCQN | Manufacturer JS series drawing, rev 2026-01-14 p9, visually reviewed. Original footprint uses terminals 1,2,3 / 5,6,7 and commons 2,6. Sample continuity/actuator orientation still required. |
| J2 | PIM724 with two 1x20 sockets | Original 2.54 mm pitch, 17.78 mm row spacing, 40-pin footprint; pin 1 opposite pin 40. 21x53 mm nominal module envelope. Choose socket height/part and confirm USB, buttons and underside clearance. |
| J3 | Hirose DM3AT-SF-PEJM5 | Installed KiCad footprint and manufacturer catalog pin functions; eight SD signals, two unused detection terminals and four ground shield lands. Current engineering drawing and copper-exclusion geometry must be reviewed before routing. |
| EXT1–3 | Candidate 2x20 male 1.27 mm headers, cable attachment | Three Olimex CABLE-40-40-10CM female/female cables are the reference proposal. Generic through-hole header geometry is assigned; exact male part, exposed pin length, shell clearance and cable continuity remain to qualify. No stacking sockets assumed. |
| X2 | 202-58 angled female; Form 7 reference | Original service manual and TGL drawings now recovered. [Investigation and reference geometry](efs58/investigation.md). Installation orientation, body clearance and sample fit remain before assigning the active footprint. |
| J1 | 1x2, 2.54 mm male header | Carrier pin 1 = CDONE, pin 2 = GND. Wire to HX8K PGM1 pin 5 and ground; carrier numbering is separate from PGM1 numbering. Programmer connection remains on the FPGA board. |
| J4 | JST B2B-XH-A, 2.50 mm top-entry header | XHP-2 housing and suitable SXH contacts; pin 1 = regulated +5 V, pin 2 = GND. Harness polarity and crimp must be verified; this is not a reverse-polarity protection circuit. |
| J5 | 1x15, 2.54 mm male probe header | Exact net sequence is in the schematic/BOM; pin 1 is GND. Reserve probe access, secure cables to separate strain relief. |

The switch manufacturer drawing shows a **bottom view**. The original footprint
reflects that view into component-side coordinates: 1/2/3 have y=+1.2 mm;
5/6/7 have y=-1.2 mm; x=-2.5/0/+2.5 mm. Pads are 1.0x1.6 mm, giving the
recommended 4 mm overall land span. The stock KiCad JS202011JCQN footprint has
1–6 numbering; assigning it unchanged would put the second-pole common on the
wrong schematic net. Both the schematic and connectivity checker now use the
manufacturer numbering, not a hidden pad translation. No live switching is allowed.

MicroSD pad numbers 9/10 are KiCad's identifiers for the separate detection
contacts, not SD bus pins. Both are explicit NC; neither is silently grounded or
mistaken for SH. The footprint audit requires all repeated SH lands. Detection
is not used by firmware; restart is still required after safe eject.

## HX8K extraction and placement

The pinned manufacturer PCB outline is 65x67 mm. Relative to its top-left
(115,53) mm source datum, the EXT1/2/3 footprint centers are respectively
(15.175,12.405), (46.925,12.405), (15.175,3.515) mm. Along a row the contact pitch
is 1.27 mm. **4.064 mm is the distance between its SMT tail-pad rows**, not a
specification for the mating connector's contact rows. Do not turn the module's
copper-tail geometry into a female socket footprint. These facts were extracted
from the pinned Rev B1 PCB without copying its artwork into our design.

The allocation study reserves the complete FPGA module, an adjacent Pico with
USB/button access, SD insertion/ejection space and an accessible mode switch.
It separates host receivers/drivers from the Pico isolation/supervisor area.
X2 has a deliberately dimensionless mechanical reservation: the drawn area is
space allocation, not connector size. Zone-overlap checks do not establish
component placement, creepage, routing, fit or usable USB/card finger clearance.
The current PCB chooses a separate FPGA board connected by cables. Its mounting
location and cable strain relief are external to the carrier and remain to design.
Three 10 cm cables add electrical loading and propagation/reflection concerns;
existing FPGA timing closure does not qualify that physical interconnect.

## Reproduce

```sh
python3 tools/generate_carrier_mechanics.py
python3 tools/generate_carrier.py
make test-carrier-schematic test-carrier-footprints test-carrier-pcb
/usr/bin/python3 tools/generate_carrier_pcb.py
python3 tools/check_carrier_footprints.py --library-root /usr/share/kicad/footprints
```

The inventory records pad identifiers/centers and SHA-256 of the installed KiCad
files. Portable CI checks coverage, project-owned footprint hashes, both module
rows, switch numbering, SD shield/detect handling and allocation overlaps. Five
negative tests reject renumbered switch pads, mirrored Pico pads, missing SD
detection pads, overlapping zones and a false fabrication-ready flag. Use
`--refresh` only after reviewing a library change; hashes alone do not certify a
manufacturer land pattern. Existing IC/passive footprints receive pad-coverage
checks here, not a new dimensional qualification.

References:

- [Manufacturer JS series](https://www.littelfuse.com/assetdocs/littelfuse-ck-slide-js-series-datasheet?assetguid=aba42b08-0d2c-423b-813d-a2faa5a3bb14), p9; [same manufacturer PDF, accessible mirror](https://static.datasheets.com/doc/3674279-c-k-js202011scqn-ds.pdf).
- [Hirose product and current drawing](https://www.hirose.com/product/p/CL0609-0031-0-00); [manufacturer catalog via DigiKey](https://www.digikey.se/en/resources/datasheets/hirose/dm3-series-microsd). Direct drawing download was unavailable; final land-pattern approval remains open.
- [PIM724 product dimensions and pinout](https://shop.pimoroni.com/products/pimoroni-pico-plus-2).
- [Pinned HX8K Rev B1 PCB](https://github.com/OLIMEX/iCE40HX8K-EVB/blob/dba688dedb3ae08d05e81a0f56a847f155622d21/HARDWARE/REV-B1/iCE40HX8K-EVB_Rev_B1.kicad_pcb).

Our new footprints and allocation graphics are original MIT-licensed work based
on dimensional facts. Manufacturer PDFs are not redistributed. The PCB embeds installed KiCad library
footprints under the KiCad library CC-BY-SA-4.0 license with its board-design
exception; those library elements are not re-licensed as original MIT artwork.
See https://www.kicad.org/libraries/license/.

## Layout checks and remaining release gates

The board checker compares all 557 electrical pads, including repeated shield
lands, with the freshly exported KiCad schematic nets. It checks schematic UUID
association, footprint identity, explicit NCs, placement coordinates and retained
SD exclusion zones. Twenty-one mutation controls reject wrong nets, missing pads or parts, broken schematic
associations, removed routing/vias, excessive bypass distance, a wrong plane net,
a weakened SD hold and a false release flag. Four controls remove copper and its
manifest entry together, checking that independent connectivity assertions catch
broken supervisor supply/sense/divider paths and resistor ground returns. Five
additional controls remove a rail branch from each domain, a control branch, or
a crossover via from both the board and manifest. The latter ensures opposite
layers are not falsely treated as connected at coincident coordinates.
Results are recorded in [the PCB report](../../reports/carrier-pcb.json); older
mechanics/desk reports remain historical snapshots. The current local KiCad DRC has zero geometric/silkscreen violations and **177
unconnected items**, down from 336. This is partial routing, not a passing production
DRC. The settings are default review settings, not a chosen fabricator's rules.

The installed SD footprint already carries five F.Cu exclusion regions. Preserve
these and the additional conservative **both-copper-layer** routing hold. Exact copper/layer
restrictions and ejection geometry still require Hirose drawing 0000947170; the
manufacturer file download again returned HTTP 403 during the 2026-10-26 layout
review. Search indexing identifies the six-page drawing, but no dimensionally
reviewable local copy was obtained. Do not route on the
assumption that the temporary rectangular hold is the final manufacturer pattern.

The original PC1715 scan, PDF page 5 (assembly 1.93.300101.5/09), shows X2 A1/B1
orientation but supplies no mating connector dimensions. Contact naming and
orientation evidence cannot establish pitch, tail spacing, keying or board fit.
The owner identified X2 as **EFS58** on 2026-10-26. The subsequent
[primary-source investigation](efs58/investigation.md) identifies the card-side
202-58 angled female and recovers the dimensioned PCB pattern. The Form 7
reference has 2.5 mm pitch, 5 mm tail rows and 85 mm mounting centres. A full-size
drilling template and an original KiCad reference footprint are available there.
X2 remains unassigned in this review PCB pending installation orientation and
clearance integration, rather than because the connector drawing is missing.
The existing A/B electrical map remains unchanged.

Sources for connector selection:

- [Olimex CABLE-40-40-10CM](https://www.olimex.com/Products/Components/Cables/Ribbon/CABLE-40-40-10CM/): two 40-contact, 0.05-inch pitch connectors, 10 cm long. Candidate compatibility is inferred from pitch and the reference board header; verify mating and pin-1-to-pin-1 continuity before power.
- [JST XH manufacturer catalog](https://www.jst-mfg.com/product/pdf/eng/eXH.pdf): 2.5 mm pitch, top-entry header, XHP housing and SXH contacts. No assumption of a 2.54 mm clone being equivalent.

Regenerating the PCB resets placement to the scripted review layout. Once manual
routing starts, update the generator deliberately or retain the edited board;
do not regenerate over manual work. No carrier fabrication exports are supplied.


## Local power/ground routing increment (2026-10-26)

C1–C18 now serve RX1–RX5, U4–U13 and ISO1–ISO3 respectively according to the
explicit mapping in `pcb-placement.json` (U13 precedes U9 in that mapping).
Supply traces are 1.75 mm for the SO/TSSOP placements and 2.05 mm for SOT parts;
each capacitor has a 1.3 mm ground escape to its own 0.6/0.3 mm through via.
IC ground inputs also escape to the bottom GND plane. These are pad-centre lengths,
not measured loop inductance. C19 remains outside the SD hold; its power/ground routes were added in the
2026-10-27 increment below.

C20 is beside the FPGA 3V3 entry; C21 is beside Pico 3V3. C22 supports module 5V.
The module 5V input is routed to EXT1 and through D1 to Pico VSYS. Those module
rails do not connect to host V5_HOST. The top copper uses 0.8 mm module-power
traces, 0.5 mm 3V3 bulk links and 0.25/0.3 mm ground/local bypass traces. These are
review-layout choices, not a qualified ampacity or regulator load budget.

Only GND is poured, on B.Cu with 0.25 mm clearance and direct pad connections.
It stops at Y=201 before the host reservation and excludes the SD hold on both
layers. Final solderability/thermal-relief choice, copper weight, return paths
under signal routes and supply distribution need review as routing progresses.
No claim of completed power integrity, cable timing or immunity follows from DRC.

The existing 100 nF values are consistent with the local-bypass guidance in
[TI SN74LVC541A, Rev O, sections 8.3–8.4](https://www.ti.com/lit/ds/symlink/sn74lvc541a.pdf).
No schematic or net assignments changed in this layout increment.

Reproduce the partial layout with `/usr/bin/python3 tools/generate_carrier_pcb.py`.
Then run `make test-carrier-pcb test-carrier-layout-cad`. The latter checks fresh
KiCad JSON output and updates `reports/carrier-pcb.json`; geometric violations
fail the check, while the remaining open connections are explicitly reported.
Refresh both visual previews with `python3 tools/preview_carrier_pcb.py`.
The independent footprint and schematic checks remain required. The generator
owns the routed layout, so regeneration preserves these routes rather than
resetting the board to the previous unrouted staging arrangement.

## Supervisor and resistor return routing (2026-10-26)

U10/U11/U12 now connect to their respective R1/R3/R5 pull-ups and R2/R4/R6
pull-downs. R2/R4/R6 are rotated so the sense branch reaches the matching pad
without crossing the supply route. The supervisor supply domains remain V3P3,
V5_HOST and P3V3 respectively; upstream rail distribution and downstream
power-good qualification gates were still unrouted at this stage.

All thirteen resistor ground pads have 1.5 mm top-layer returns to individual
0.6/0.3 mm ground vias. This increment adds 37 segments and 13 vias, reducing
unconnected items from 234 to 212 with zero geometric DRC violations. The portable
checker traverses actual copper endpoints for each supervisor network and checks
each resistor's short via return independently of the routing manifest. This
checks the intended local paths; filled-plane connectivity and clearances remain
KiCad DRC responsibilities. No schematic values or net assignments changed.

## Rail distribution and local controls (2026-10-27)

The FPGA V3P3 source at EXT1 now reaches all 37 placed pads on that rail,
including receiver/logic/isolator supplies, U9 unused inputs, pull-ups, the mode
switch and probe header. Pico P3V3 reaches all 10 placed pads outside J3,
including C19, SD pull-ups, U12 and the probe header. All 10 placed V5_HOST pads
are interconnected, including the priority pull-up; their X2 supply entry remains
unplaced. Neither 3V3 rail is joined to the other, and host 5V remains separate
from module 5V. J3 power routing remains blocked by the SD drawing review.

The FPGA trunk uses 0.8 mm top copper, with 0.5 mm supply branches and 0.3 mm
pull-up/probe links. Two host-rail and three Pico-rail crossings use short 3 mm
bottom traces and ten 0.6/0.3 mm vias. The bottom GND fill remains connected
around those clearances; signal routing must account for these interruptions
in its return paths. This is routing continuity evidence, not measured rail
impedance, a load/transient budget, or approval of the provisional large outline.

Local CDONE, mode-control and host-priority resistor branches are also routed.
These nets still need their other signal connections. Total copper is now 227
segments, 73 ground vias and 10 power vias. KiCad reports zero geometric
violations and 177 unconnected items, down from 212 before this increment.

The portable checker derives rail paths directly from copper on each layer,
splits T junctions, and joins layers only at actual vias or through-hole pads.
It checks every placed rail pad against the schematic except the explicit J3
hold. It uses U11 as the V5_HOST continuity reference, without implying a live
host supply. KiCad DRC remains responsible for physical clearances and filled
plane connectivity. Regeneration and updated front/back previews are verified.
