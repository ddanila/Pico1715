# Provisional X2 harness map

Component-side numbering is derived from the reference drawing; confirm A/B and both cable ends by continuity before host use. Header pins 59/60 are unconnected. Every breakout trace is isolated, including contacts that join GND on the host. This is a contact map, not a qualified high-speed ribbon-cable design.

| X2 | J1 pin | Host signal | Carrier net |
|---|---:|---|---|
| A1 | 1 | 0V | GND |
| B1 | 2 | 0V | GND |
| A2 | 3 | 0V | GND |
| B2 | 4 | 0V | GND |
| A3 | 5 | /PIOCS0 | NC on carrier |
| B3 | 6 | /PIOCS1 | NC on carrier |
| A4 | 7 | DB7 | H_D7 |
| B4 | 8 | DB6 | H_D6 |
| A5 | 9 | DB5 | H_D5 |
| B5 | 10 | DB4 | H_D4 |
| A6 | 11 | DB3 | H_D3 |
| B6 | 12 | DB2 | H_D2 |
| A7 | 13 | DB1 | H_D1 |
| B7 | 14 | DB0 | H_D0 |
| A8 | 15 | /WR | H_WR_N |
| B8 | 16 | /RD | H_RD_N |
| A9 | 17 | /MREQ | H_MREQ_N |
| B9 | 18 | /MEMDI | NC on carrier |
| A10 | 19 | IEI | H_PRIORITY_OUT |
| B10 | 20 | IEO | H_PRIORITY |
| A11 | 21 | AB14 | H_A14 |
| B11 | 22 | AB15 | H_A15 |
| A12 | 23 | AB12 | H_A12 |
| B12 | 24 | AB13 | H_A13 |
| A13 | 25 | AB10 | H_A10 |
| B13 | 26 | AB11 | H_A11 |
| A14 | 27 | AB8 | H_A8 |
| B14 | 28 | AB9 | H_A9 |
| A15 | 29 | 5N | NC on carrier |
| B15 | 30 | 12N | NC on carrier |
| A16 | 31 | AB6 | H_A6 |
| B16 | 32 | AB7 | H_A7 |
| A17 | 33 | AB4 | H_A4 |
| B17 | 34 | AB5 | H_A5 |
| A18 | 35 | AB2 | H_A2 |
| B18 | 36 | AB3 | H_A3 |
| A19 | 37 | AB0 | H_A0 |
| B19 | 38 | AB1 | H_A1 |
| A20 | 39 | /RESET | H_RESET_N |
| B20 | 40 | /BUSRQ | H_BUSRQ_N |
| A21 | 41 | TAKT-X2 | H_CLK |
| B21 | 42 | /LT107CS | NC on carrier |
| A22 | 43 | /IODI | NC on carrier |
| B22 | 44 | /CTCCS1 | NC on carrier |
| A23 | 45 | /NMI | NC on carrier |
| B23 | 46 | /INT | H_INT_N |
| A24 | 47 | /WAIT | H_WAIT_N |
| B24 | 48 | /IORQ | H_IORQ_N |
| A25 | 49 | /RFSH | H_RFSH_N |
| B25 | 50 | /KRF0 | NC on carrier |
| A26 | 51 | /M1 | H_M1_N |
| B26 | 52 | /SIOCS1 | NC on carrier |
| A27 | 53 | /BAO | H_BAO_N |
| B27 | 54 | NC | NC on carrier |
| A28 | 55 | 12P | NC on carrier |
| B28 | 56 | 12P | NC on carrier |
| A29 | 57 | 5P | V5_HOST |
| B29 | 58 | 5P | V5_HOST |
