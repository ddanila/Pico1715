# PC1715 EFS58 mating connector investigation

For an independent printed-housing experiment, see the
[four-contact coupon](../../efs58-coupon/README.md). It includes STL/STEP models,
a routed passive test PCB and contact screening instructions. Its modern socket
candidate is not yet qualified for EFS blades and does not replace this reference
or remove the carrier X2 footprint hold.

2026-10-26. The documented card-side connector is **Buchsenleiste 202-58,
TGL 29331/03**: a female, 58-contact, two-row connector with right-angle PCB
tails. The missing dimensional drawing has now been recovered. Form 7 is our
reference mounting choice; the service manual does not specify that accessory.
This closes the connector-family and nominal hole-pattern research, not the
carrier's installed clearance or production qualification.

## Evidence chain

1. [PC1715 service manual](https://www.sax.de/~zander/pc1715/doku/pc_serv.pdf),
   PDF p36 / printed p35, section 1.3.2, explicitly lists 202-58 for the 2xV.24
   expansion card. PDF p41 / printed p40 repeats it for IFSS. This is stronger
   evidence than identifying a connector from appearance alone.
2. [TGL 29331/03, February 1988](https://bauarchivddr.bbr-server.de/bauarchivddr/archiv/tglarchiv/tgl20001bis30000/tgl29001bis29500/tgl-29331-3-feb-1988.pdf):
   p3 Fig.5 depicts Form 202 with mounting element 7; p8 Table 3 identifies the
   termination; p11 Table 4 identifies its two complete rows. P24 Fig.34 and p26
   Table 12 supply the PCB pattern. This edition replaces December 1977 and its
   first amendment; it is a later standard, not proof that every earlier
   manufactured sample is identical in every detail.
3. [TGL 29331/04, December 1977](https://bauarchivddr.bbr-server.de/bauarchivddr/archiv/tglarchiv/tgl20001bis30000/tgl29001bis29500/tgl-29331-4-dez-1977.pdf),
   p13 Figs.29–30, distinguishes mounting accessories 7 and 9. Form 7 has a
   closed round fastening hole; Form 9 has an open slot. They are not the same
   footprint with interchangeable names.
4. [Heiko Poppe's GUN card description](https://www.robotrontechnik.de/downloads/GUN/GUN.pdf),
   31 May 2014, pp1–2, specifies an angled EFS female on the component side and
   a short male/female extension wired 1:1. Its alternative male connector goes
   on the solder side. This independently supports connector sex and warns
   against substituting a male on the same board face. It does not establish
   that X1 and X2 have identical electrical functions or that our carrier fits
   directly in the case.

The existing X2 signal map remains authoritative for electrical wiring. The
motherboard component-side assembly view has X3 left, X4–X6 right, X2 above X1,
contact 1 left, and X2 row A toward X1. A mating connector face, its termination
view, and the top view of a new daughterboard are different projections. Do not
copy one picture's left/right coordinates into another without a transform.

## Dimensions recovered

All dimensions below are millimetres. Page numbers refer to TGL 29331/03.

| Feature | Value | Drawing evidence |
| --- | --- | --- |
| Contacts | 2 × 29, A/B | p11 Table 4, pattern 1 |
| Pitch along a row | 2.5 | p24 Fig.34, ±0.1 PCB pitch |
| First-to-last contact span | 70 | p26 Table 12, e3 ±0.1 |
| Mating row separation | 2.5 | p2 Fig.1, inherited by Fig.5 |
| **Bent PCB-tail row separation** | **5** | p24 Fig.34, ±0.1 |
| Form 7 mounting centres | 85 | p26 Table 12, e4 ±0.1 |
| Form 9 mounting centres | 82.5 | p26 Table 12; p25 note 30 changes end offset to 6.25 |
| Form 7 end-contact to mounting centre, along row | 7.5 | p24 Fig.34 |
| PCB mounting holes | Ø2.7, +0.2/−0 | p24 Fig.34 |
| Mounting line to first tail row | 5 | p24 Fig.34, female e6 |
| **PCB edge to first tail row** | **6.5** | p24 Fig.34, female e7 |
| Nominal connector length l1 | 88, +0/−0.3 | p4 Table 1 |
| Maximum l3 with mounting hardware | 90.6 | p4 Table 1 |
| Body width across mating rows | 8.5 | p3 Fig.5 |

The two edge-related dimensions share the **first tail row** as a datum: do not
add 5 + 6.5 to obtain the edge position. The mounting centre is consequently
1.5 mm inside the illustrated board edge. This is a connector installation
pattern, not a recommendation to give an arbitrary M2.5 fastener only that much
edge clearance elsewhere on a board.

The reference uses Ø1.0 finished plated contact holes and 1.8 copper pads as
**our design choices**, not TGL-specified pad diameters. P2 note 4 says the tails
can enter holes with minimum diameter 0.74; Fig.34 refers finished hole design
to other PCB standards. Fabricator tolerances and an actual tail sample still
matter. Mounting holes are unplated and have no signal assignment.

## Variant and procurement decision

| Description offered by a seller | Treatment |
| --- | --- |
| 202-58, angled female, mounting Form 7 | Reference candidate; ask for underside/tail and accessory photos |
| 202-58 with Form 9 | Same contact family, different mounting holes; separate footprint required |
| 212-58 straight PCB female | Different termination pattern; not a drop-in |
| 222-58 solder-lug female | Cable termination candidate, not this PCB footprint |
| 102-58 male | Opposite sex; not interchangeable on the component side |
| 404/414 family with 58 fitted contacts | Wider three-row body/pattern; reject as an EFS58 substitute |
| Generic 2×29, 2.54 mm | Reject: 1.12 mm cumulative pitch error over 28 intervals |

Buy by **202-58 plus tail and mounting form**, not just “EFS58”. No particular
seller's stock, condition, price or shipping has been qualified here. Prefer a
complete pair with the mounting accessories; do not assume loose old stock
includes them. Original boards can provide a donor connector, but identifying
its variant still precedes selecting a footprint.

## Deliverables and limits

[geometry.json](geometry.json), [reference KiCad footprint](EFS58_202-58_Form7_Reference.kicad_mod)
and [full-size drilling template](drilling-template.svg) are original MIT work,
not copied library artwork. The footprint is deliberately outside the active
carrier library and is not assigned to X2 yet. It has no claimed body/courtyard
outline and is explicitly labelled reference-only.

The proposed component-side coordinates put A1 at (0,0), A29 at (70,0), B1 at
(0,5), B29 at (70,5), mounting holes at (−7.5,−5)/(77.5,−5), and the board-edge
datum at y=−6.5. Numbering is **derived**, not explicitly printed onto Fig.34:
Table 4 is a termination-side view; p17 section 2.12.2 puts row A toward the
PCB for angled connectors; the lower contact uses the shorter bend in Fig.5.
P18 Fig.25 locates the female polarization groove at the penultimate contact
(28). The A/B and 1/29 transform should be checked against a connector sample
and host assembly view before promoting this reference to the active design.

Next installation work is to choose direct attachment versus a short 1:1
extension, establish the carrier board face/rotation, complete the body and
fastener clearance envelope, and inspect interference with X1 and the enclosure.
A sample fit and unpowered continuity check then confirm the chosen part and
all 58 positions. None of this requires revisiting whether the pitch is 2.5 or
whether the card connector is female: those documentary questions are resolved.

Reproduce with `python3 tools/generate_efs58_reference.py` and
`make test-efs58`. Print the SVG at 100% and measure its 50 mm calibration line.
Tests detect accidental geometry changes, not mechanical fit. The source PDFs
remain in ignored `local/efs58`; hashes and retrieval URLs are in
[sources.json](sources.json). They are not redistributed or relicensed as MIT.
