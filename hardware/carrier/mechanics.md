# Footprint audit and placement allocation

This increment selects SW1/J2/J3 footprints and checks schematic-to-pad coverage
for all 68 assigned parts. Seven connector references remain unresolved. The
[allocation drawing](preview/placement-study.svg) and its
[millimetre coordinates](placement-study.json) are **not a PCB outline**: no copper,
board file, manufacturing package or enclosure-fit claim is produced.

| Reference | Selection | Evidence and remaining check |
| --- | --- | --- |
| SW1 | C&K JS202011JCQN | Manufacturer JS series drawing, rev 2026-01-14 p9, visually reviewed. Original footprint uses terminals 1,2,3 / 5,6,7 and commons 2,6. Sample continuity/actuator orientation still required. |
| J2 | PIM724 with two 1x20 sockets | Original 2.54 mm pitch, 17.78 mm row spacing, 40-pin footprint; pin 1 opposite pin 40. 21x53 mm nominal module envelope. Choose socket height/part and confirm USB, buttons and underside clearance. |
| J3 | Hirose DM3AT-SF-PEJM5 | Installed KiCad footprint and manufacturer catalog pin functions; eight SD signals, two unused detection terminals and four ground shield lands. Current engineering drawing and copper-exclusion geometry must be reviewed before routing. |
| EXT1–3 | HX8K Rev B1 mating connectors | Actual manufacturer PCB uses PA-V16X-2X20-LF **1.27 mm** headers. Female part, mating height and orientation remain unassigned. |
| X2 | Host mating connector | Source-checked electrical contacts do not establish a physical footprint or board edge. Remains unassigned. |
| J1/J4/J5 | CDONE tap / power / probes | Cable/connector and strain-relief choices remain open; no placeholder footprint assigned. |

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
A compact daughterboard or cable arrangement remains a choice after mating parts
and the owner's existing FPGA boards are identified.

## Reproduce

```sh
python3 tools/generate_carrier_mechanics.py
python3 tools/generate_carrier.py
make test-carrier-schematic test-carrier-footprints
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
on dimensional facts. Manufacturer PDFs and KiCad library artwork are not
redistributed here; system footprints retain their upstream licenses.
