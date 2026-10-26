# HX8K passive analyzer harness

Generated from hx8k-analyzer-pins.json. Rev B1 only; this is NOT the controller harness.

| FPGA signal | Adapter net | Header / pin | FPGA ball | Pico GPIO |
| --- | --- | --- | --- | --- |
| `clk100` | — | Onboard oscillator | J3 | — |
| `bus_sample[0]` | F_A0 | EXT1 / 7 | C14 | — |
| `bus_sample[1]` | F_A1 | EXT1 / 9 | B15 | — |
| `bus_sample[2]` | F_A2 | EXT1 / 11 | D13 | — |
| `bus_sample[3]` | F_A3 | EXT1 / 13 | B14 | — |
| `bus_sample[4]` | F_A4 | EXT1 / 15 | C12 | — |
| `bus_sample[5]` | F_A5 | EXT1 / 17 | E11 | — |
| `bus_sample[6]` | F_A6 | EXT1 / 19 | C13 | — |
| `bus_sample[7]` | F_A7 | EXT1 / 21 | A16 | — |
| `bus_sample[8]` | F_A8 | EXT1 / 39 | C10 | — |
| `bus_sample[9]` | F_A9 | EXT1 / 40 | A10 | — |
| `bus_sample[10]` | F_A10 | EXT1 / 38 | A11 | — |
| `bus_sample[11]` | F_A11 | EXT1 / 36 | D10 | — |
| `bus_sample[12]` | F_A12 | EXT1 / 34 | C9 | — |
| `bus_sample[13]` | F_A13 | EXT1 / 32 | E9 | — |
| `bus_sample[14]` | F_A14 | EXT1 / 30 | D9 | — |
| `bus_sample[15]` | F_A15 | EXT1 / 28 | A9 | — |
| `bus_sample[16]` | F_D0 | EXT1 / 23 | A15 | — |
| `bus_sample[17]` | F_D1 | EXT1 / 25 | B13 | — |
| `bus_sample[18]` | F_D2 | EXT1 / 27 | E10 | — |
| `bus_sample[19]` | F_D3 | EXT1 / 29 | C11 | — |
| `bus_sample[20]` | F_D4 | EXT1 / 31 | D11 | — |
| `bus_sample[21]` | F_D5 | EXT1 / 33 | B12 | — |
| `bus_sample[22]` | F_D6 | EXT1 / 35 | B10 | — |
| `bus_sample[23]` | F_D7 | EXT1 / 37 | B11 | — |
| `bus_sample[24]` | F_MREQ_N | EXT1 / 22 | F7 | — |
| `bus_sample[25]` | F_IORQ_N | EXT1 / 26 | F9 | — |
| `bus_sample[26]` | F_RD_N | EXT1 / 20 | B9 | — |
| `bus_sample[27]` | F_WR_N | EXT1 / 18 | D8 | — |
| `bus_sample[28]` | F_M1_N | EXT1 / 24 | C8 | — |
| `bus_sample[29]` | F_RFSH_N | EXT1 / 10 | B7 | — |
| `bus_sample[30]` | F_CLK | EXT2 / 7 | B6 | — |
| `bus_sample[31]` | F_RESET_N | EXT1 / 14 | A7 | — |
| `bus_sample[32]` | F_WAIT_N | EXT2 / 9 | C6 | — |
| `bus_sample[33]` | F_INT_N | EXT2 / 11 | D7 | — |
| `bus_sample[34]` | F_BUSRQ_N | EXT3 / 21 | K16 | — |
| `bus_sample[35]` | F_BAO_N | EXT2 / 13 | A6 | — |
| `bus_sample[36]` | F_PRIORITY | EXT1 / 16 | B8 | — |
| `card_power_good` | CARD_PG | EXT1 / 12 | C7 | — |
| `pico_data[0]` | P_DATA0 | EXT2 / 28 | P16 | GP0 |
| `pico_data[1]` | P_DATA1 | EXT2 / 26 | M13 | GP1 |
| `pico_data[2]` | P_DATA2 | EXT2 / 24 | M14 | GP2 |
| `pico_data[3]` | P_DATA3 | EXT2 / 22 | L12 | GP3 |
| `pico_data[4]` | P_DATA4 | EXT2 / 20 | N16 | GP4 |
| `pico_data[5]` | P_DATA5 | EXT2 / 18 | L13 | GP5 |
| `pico_data[6]` | P_DATA6 | EXT2 / 16 | L14 | GP6 |
| `pico_data[7]` | P_DATA7 | EXT2 / 14 | K12 | GP7 |
| `pico_index[0]` | P_INDEX0 | EXT2 / 12 | M16 | GP8 |
| `pico_index[1]` | P_INDEX1 | EXT2 / 10 | J10 | GP9 |
| `pico_index[2]` | P_INDEX2 | EXT3 / 7 | M15 | GP10 |
| `pico_index[3]` | P_INDEX3 | EXT3 / 9 | J11 | GP11 |
| `pico_index[4]` | P_INDEX4 | EXT3 / 11 | L16 | GP12 |
| `pico_request` | PICO_REQUEST | EXT3 / 13 | K13 | GP13 |
| `pico_ack` | PICO_ACK | EXT3 / 15 | K14 | GP14 |
| `link_sync_n` | LINK_SYNC_N | EXT3 / 17 | J15 | GP16 |
| `capture_clear` | CAPTURE_CLEAR | EXT3 / 19 | K15 | GP17 |
| `capture_enable` | CAPTURE_ENABLE | EXT3 / 27 | J13 | GP21 |

EXT1/EXT2/EXT3 ground contacts 2, 4 and 8 connect to common GND.
J1 uses GPIO identifiers, not Pico physical header numbers. J2 supplies V3P3 from the FPGA rail.
Leave GP15, GP18–20 and SD pins disconnected from this analyzer harness.
Host /RESET2 is sampled; it is not connected to card reset or Pico GP15.
All module signal wiring is 3.3 V. Never connect X2 directly to FPGA or Pico.
