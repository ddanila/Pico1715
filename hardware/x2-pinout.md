# Classic PC1715 X2 contact assignment

The common bus contacts are assigned from the service manual (printed page 44),
cross-checked for the shared bus against the index-2B redraw and GUN X1 card.
These are electrical contact identifiers, **not a mating-face drawing**. No
mechanical footprint or physical motherboard orientation is qualified yet.
The machine-readable source is [x2-contacts.json](boards/x2-contacts.json).

## Interrupt-chain exception

The manual calls A10 IEI on X2 only and B10 IEO on X1 only. The index-2B
redraw labels IEI X1:A10. GUN on X1 calls A10 IEIO and wires B10; it does
not resolve the X2 discrepancy. Do not assume X1 and X2 are identical:
their A21 clock nets also differ. GUN is corroboration of shared contact
positions, not validation of our floppy interrupt or WAIT implementation.

X2 A10/B10 terminate only at J11 pins 1/2. J11 pins 3/4 are card IEI/IEO.
Leave J11 open by default. R15 pulls card IEI high through 10 kΩ to host 5 V;
IEO has no connection to either disputed contact. This default is for bench
tests, not a qualified stock-ROM interrupt-chain configuration. After tracing
the actual board chain, patch the confirmed upstream priority to J11.3 and
the confirmed downstream priority to J11.4. B10 may require no connection;
do not infer it is an X2 IEO from the X1 table. Record the board revision and
routing before a machine test. J1–J3 remain logical breakout headers.

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
