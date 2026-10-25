# Classic PC1715 X2 contact assignment

The common bus contacts are assigned from the service manual (printed page 44),
cross-checked for the shared bus against the index-2B redraw and GUN X1 card.
These are electrical contact identifiers, **not a mating-face drawing**. No
mechanical footprint or physical motherboard orientation is qualified yet.
The original assembly drawing orientation is established below.
The machine-readable source is [x2-contacts.json](boards/x2-contacts.json).

## Interrupt chain resolved from the original sheets

The original ZRE sheet (PDF page 7, drawing 1.93.300101.5/04, index 2B)
labels **X2:A10 IEI**, connected to CTC A30 pin 13. CTC IEO pin 11 feeds
SIO A29 IEI pin 6; SIO IEO pin 7 exits at **X1:B10**. The 2009 redraw's
X1:A10 label is inconsistent with this original. X2 B10 is not shown driven
on this motherboard sheet.

The original floppy-controller sheet (PDF page 14, printed sheet 11,
1.93.300102.3/04) independently shows **X2:B10 -> PIO A1:2 IEI pin 24**,
with R1:3 = 1 kΩ to 5P, and **PIO IEO pin 22 -> X2:A10**. Thus motherboard
IEI means an input to the motherboard chain, driven by the card's IEO.
The former assumption that A10 should feed card IEI was incorrect.

Revision C fits removable 0 Ω links R16 (X2 A10 to H_IEO) and R17
(X2 B10 to H_IEI). R15 retains the 10 kΩ input pull-up appropriate to our
CMOS receiver; it does not copy the original bipolar PIO's 1 kΩ value.
This gives the floppy controller priority ahead of CTC, then SIO, then
X1 expansion. J11 remains a probe/override header: pins 1/2 are A10/B10;
pins 3/4 are card IEI/IEO. Remove R16/R17 before applying alternative
patch routing. Do not add opposite-direction links with them fitted.
An unpowered/disarmed card releases IEO; the motherboard's R10.2 3.3 kΩ
pull-up biases CTC IEI high. This is not an active chain bypass.

GUN is an X1 card and is not a substitute for the X2 controller drawing.
Its connector's A10 naming does not establish an X2 input direction.
These conclusions apply to the documented classic board, not W/M machines.

## Drawing orientation

Original assembly drawing 1.93.300101.5/09 (PDF page 5) is a component
placement view. Orient it with keyboard X3 at left, external X4/X5/X6 at
right, and X1 along the bottom edge. X2 is immediately above X1. Its pin-1
end is left; B1 is on the CPU-facing row, A1 on the X1-facing row. Numbering
increases toward the right. This resolves the motherboard drawing orientation.
A card mating-face view and a solder-side PCB view can be mirrored relative
to it: preserve A/B contact names rather than reinterpreting numeric headers.

A footprint still requires the selected mating connector's pitch, row spacing,
mounting holes, pin-tail geometry and view convention. The placement scan is
not a dimensioned connector drawing. The specimen revision and fit remain
physical checks; the source orientation is no longer unknown.

## Contacts

Unused contacts are explicitly NC on this card; the table still records their
motherboard functions. A22 uses the /IODI spelling in the redraw. Negative
supplies and +12 V are not connected to the card.

| Contact | Documented function | Card net |
| --- | --- | --- |
| A1 | 0V | GND |
| A2 | 0V | GND |
| A3 | /PIOCS0 | NC |
| A4 | DB7 | H_D7 |
| A5 | DB5 | H_D5 |
| A6 | DB3 | H_D3 |
| A7 | DB1 | H_D1 |
| A8 | /WR | H_WR_N |
| A9 | /MREQ | H_MREQ_N |
| A10 | IEI (X2 only) | X2_A10_CONTACT |
| A11 | AB14 | NC |
| A12 | AB12 | NC |
| A13 | AB10 | NC |
| A14 | AB8 | NC |
| A15 | 5N (-5V) | NC |
| A16 | AB6 | H_A6 |
| A17 | AB4 | H_A4 |
| A18 | AB2 | H_A2 |
| A19 | AB0 | H_A0 |
| A20 | /RESET | H_RESET_N |
| A21 | TAKT-X2 | NC |
| A22 | /IODI | NC |
| A23 | /NMI | NC |
| A24 | /WAIT | H_WAIT_N |
| A25 | /RFSH | NC |
| A26 | /M1 | H_M1_N |
| A27 | /BAO | NC |
| A28 | 12P (+12V) | NC |
| A29 | 5P (+5V) | V5_HOST |
| B1 | 0V | GND |
| B2 | 0V | GND |
| B3 | /PIOCS1 | NC |
| B4 | DB6 | H_D6 |
| B5 | DB4 | H_D4 |
| B6 | DB2 | H_D2 |
| B7 | DB0 | H_D0 |
| B8 | /RD | H_RD_N |
| B9 | /MEMDI | NC |
| B10 | IEO (X1 only) | X2_B10_CONTACT |
| B11 | AB15 | NC |
| B12 | AB13 | NC |
| B13 | AB11 | NC |
| B14 | AB9 | NC |
| B15 | 12N (-12V) | NC |
| B16 | AB7 | H_A7 |
| B17 | AB5 | H_A5 |
| B18 | AB3 | H_A3 |
| B19 | AB1 | H_A1 |
| B20 | /BUSRQ | NC |
| B21 | /LT107CS | NC |
| B22 | /CTCCS1 | NC |
| B23 | /INT | H_INT_N |
| B24 | /IORQ | H_IORQ_N |
| B25 | /KRF0 | NC |
| B26 | /SIOCS1 | NC |
| B27 | NC | NC |
| B28 | 12P (+12V) | NC |
| B29 | 5P (+5V) | V5_HOST |

## Sources

- [printed page 44, X1/X2 contact table](https://xepb.org/robotron/docs/pc_serv.pdf)
- [Zander index-2B redraw (2009); IEI labelled X1:A10](https://www.sax.de/~zander/pc1715/pc_zres.pdf)
- [GUN ST1 on X1; A10 labelled IEIO; B10 wired](https://www.robotrontechnik.de/downloads/GUN/GUN_Sch.pdf)
- [GUN project and connector assembly notes](https://www.robotrontechnik.de/html/eigenbau/gun.htm)

Source hashes are recorded in the JSON. External drawings are referenced, not
redistributed; the card schematic and symbols remain original MIT work.

Original scanned source: `PC-1715-Schaltplaene.pdf`, SHA-256 recorded in the JSON;
PDF pages 5, 7 and 14 take precedence over the later redraw.
