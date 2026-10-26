# Footprint audit and placement allocation

The [unrouted review PCB](carrier.kicad_pcb) now places 74 electrical footprints
and four provisional mounting holes. [Board preview](preview/pcb-placement.svg)
and [coordinates](pcb-placement.json) accompany it. X2 is the sole unplaced
schematic component. The earlier [allocation drawing](preview/placement-study.svg)
remains historical context; its zones are not the current board geometry.

The 160 x 210 mm outline is deliberately roomy for reviewing connectivity and
access. It is not an enclosure-fit result or a cost-optimized production size.
ICs and passives are staged by function, not yet optimized for routing; in
particular decoupling capacitors must move beside their associated supply pins.
No traces or copper fills exist. Four M3 clearance holes are provisional carrier
mounts, not HX8K or PC1715 mounting coordinates.

| Reference | Selection | Evidence and remaining check |
| --- | --- | --- |
| SW1 | C&K JS202011JCQN | Manufacturer JS series drawing, rev 2026-01-14 p9, visually reviewed. Original footprint uses terminals 1,2,3 / 5,6,7 and commons 2,6. Sample continuity/actuator orientation still required. |
| J2 | PIM724 with two 1x20 sockets | Original 2.54 mm pitch, 17.78 mm row spacing, 40-pin footprint; pin 1 opposite pin 40. 21x53 mm nominal module envelope. Choose socket height/part and confirm USB, buttons and underside clearance. |
| J3 | Hirose DM3AT-SF-PEJM5 | Installed KiCad footprint and manufacturer catalog pin functions; eight SD signals, two unused detection terminals and four ground shield lands. Current engineering drawing and copper-exclusion geometry must be reviewed before routing. |
| EXT1–3 | Candidate 2x20 male 1.27 mm headers, cable attachment | Three Olimex CABLE-40-40-10CM female/female cables are the reference proposal. Generic through-hole header geometry is assigned; exact male part, exposed pin length, shell clearance and cable continuity remain to qualify. No stacking sockets assumed. |
| X2 | EFS58, identified by the owner | The electrical mapping is A1–A29/B1–B29. Exact mating connector variant and solder-tail drawing remain to select before assigning the footprint. |
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
SD exclusion zones. Six mutation controls reject wrong nets, missing pads or
parts, broken schematic associations, a removed SD hold and a false release flag.
Results are recorded in [the PCB report](../../reports/carrier-pcb.json); older
mechanics/desk reports remain historical snapshots. The current local KiCad DRC has zero geometric/silkscreen violations and **336
unconnected items**. This is an unrouted placement check, not a passing production
DRC. The settings are default review settings, not a chosen fabricator's rules.

The installed SD footprint already carries five F.Cu exclusion regions. Preserve
these and the additional conservative temporary routing hold. Exact copper/layer
restrictions and ejection geometry still require Hirose drawing 0000947170; the
manufacturer download returned HTTP 403 during this review. Do not route on the
assumption that the temporary rectangular hold is the final manufacturer pattern.

The original PC1715 scan, PDF page 5 (assembly 1.93.300101.5/09), shows X2 A1/B1
orientation but supplies no mating connector dimensions. Contact naming and
orientation evidence cannot establish pitch, tail spacing, keying or board fit.
The owner identified X2 as **EFS58** on 2026-10-26. This resolves the connector
family; it does not yet identify the exact mating part and its solder-tail form.
The existing A/B contact map remains unchanged. X2's footprint remains unassigned
until the matching variant's dimensioned drawing is available.

Search leads for the next mechanical audit are the EFS manufacturer catalog and
TGL 29331/03. The [Robotrontechnik connector overview](https://www.robotrontechnik.de/html/komponenten/stecker.htm)
and its [variant discussion](https://www.robotrontechnik.de/html/forum/thwb/showtopic.php?threadid=10898)
are secondary discovery references, not dimensioned footprint authority. Do not
substitute a generic 2.54 mm header or infer solder-tail row spacing from mating
contact spacing. A primary drawing is still needed to close those dimensions.

Sources for connector selection:

- [Olimex CABLE-40-40-10CM](https://www.olimex.com/Products/Components/Cables/Ribbon/CABLE-40-40-10CM/): two 40-contact, 0.05-inch pitch connectors, 10 cm long. Candidate compatibility is inferred from pitch and the reference board header; verify mating and pin-1-to-pin-1 continuity before power.
- [JST XH manufacturer catalog](https://www.jst-mfg.com/product/pdf/eng/eXH.pdf): 2.5 mm pitch, top-entry header, XHP housing and SXH contacts. No assumption of a 2.54 mm clone being equivalent.

Regenerating the PCB resets placement to the scripted review layout. Once manual
routing starts, update the generator deliberately or retain the edited board;
do not regenerate over manual work. No fabrication exports are supplied.
