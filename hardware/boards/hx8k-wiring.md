# HX8K bench header allocation

Generated from `hx8k-pins.json`; Rev B1 only. These are FPGA board headers,
not Robotron X2 contacts. All signals here use 3.3 V logic.

| Signal | Header / pin | FPGA ball | Board net |
| --- | --- | --- | --- |
| `clk100` | Onboard oscillator | J3 | `/SYSCLK` |
| `host_addr[0]` | EXT1 / 7 | C14 | `/PIO0_00` |
| `host_addr[1]` | EXT1 / 9 | B15 | `/PIO0_01` |
| `host_addr[2]` | EXT1 / 11 | D13 | `/PIO0_02` |
| `host_addr[3]` | EXT1 / 13 | B14 | `/PIO0_03` |
| `host_addr[4]` | EXT1 / 15 | C12 | `/PIO0_04` |
| `host_addr[5]` | EXT1 / 17 | E11 | `/PIO0_05` |
| `host_addr[6]` | EXT1 / 19 | C13 | `/PIO0_06` |
| `host_addr[7]` | EXT1 / 21 | A16 | `/PIO0_07` |
| `host_din[0]` | EXT1 / 23 | A15 | `/PIO0_08` |
| `host_din[1]` | EXT1 / 25 | B13 | `/PIO0_09` |
| `host_din[2]` | EXT1 / 27 | E10 | `/PIO0_10` |
| `host_din[3]` | EXT1 / 29 | C11 | `/PIO0_11` |
| `host_din[4]` | EXT1 / 31 | D11 | `/PIO0_12` |
| `host_din[5]` | EXT1 / 33 | B12 | `/PIO0_13` |
| `host_din[6]` | EXT1 / 35 | B10 | `/PIO0_14` |
| `host_din[7]` | EXT1 / 37 | B11 | `/PIO0_15` |
| `host_dout[0]` | EXT1 / 39 | C10 | `/PIO0_16` |
| `host_dout[1]` | EXT1 / 40 | A10 | `/PIO0_17` |
| `host_dout[2]` | EXT1 / 38 | A11 | `/PIO0_18` |
| `host_dout[3]` | EXT1 / 36 | D10 | `/PIO0_19` |
| `host_dout[4]` | EXT1 / 34 | C9 | `/PIO0_20` |
| `host_dout[5]` | EXT1 / 32 | E9 | `/PIO0_21` |
| `host_dout[6]` | EXT1 / 30 | D9 | `/PIO0_22` |
| `host_dout[7]` | EXT1 / 28 | A9 | `/PIO0_23` |
| `iorq_n` | EXT1 / 26 | F9 | `/PIO0_24` |
| `m1_n` | EXT1 / 24 | C8 | `/PIO0_25` |
| `mreq_n` | EXT1 / 22 | F7 | `/PIO0_26` |
| `rd_n` | EXT1 / 20 | B9 | `/PIO0_27` |
| `wr_n` | EXT1 / 18 | D8 | `/PIO0_28` |
| `iei` | EXT1 / 16 | B8 | `/PIO0_29` |
| `host_reset_n` | EXT1 / 14 | A7 | `/PIO0_30` |
| `power_good` | EXT1 / 12 | C7 | `/PIO0_31` |
| `host_oe` | EXT1 / 10 | B7 | `/PIO0_32` |
| `wait_pull_low` | EXT2 / 7 | B6 | `/PIO0_33` |
| `int_pull_low` | EXT2 / 9 | C6 | `/PIO0_34` |
| `ieo` | EXT2 / 11 | D7 | `/PIO0_35` |
| `fault` | EXT2 / 13 | A6 | `/PIO0_36` |
| `pico_data[0]` | EXT2 / 28 | P16 | `/PIO1_04` |
| `pico_data[1]` | EXT2 / 26 | M13 | `/PIO1_05` |
| `pico_data[2]` | EXT2 / 24 | M14 | `/PIO1_06` |
| `pico_data[3]` | EXT2 / 22 | L12 | `/PIO1_07` |
| `pico_data[4]` | EXT2 / 20 | N16 | `/PIO1_08` |
| `pico_data[5]` | EXT2 / 18 | L13 | `/PIO1_09` |
| `pico_data[6]` | EXT2 / 16 | L14 | `/PIO1_10` |
| `pico_data[7]` | EXT2 / 14 | K12 | `/PIO1_11` |
| `pico_reg[0]` | EXT2 / 12 | M16 | `/PIO1_12` |
| `pico_reg[1]` | EXT2 / 10 | J10 | `/PIO1_13` |
| `pico_reg[2]` | EXT3 / 7 | M15 | `/PIO1_14` |
| `pico_reg[3]` | EXT3 / 9 | J11 | `/PIO1_15` |
| `pico_write` | EXT3 / 11 | L16 | `/PIO1_16` |
| `pico_request` | EXT3 / 13 | K13 | `/PIO1_17` |
| `pico_ack` | EXT3 / 15 | K14 | `/PIO1_18` |
| `pico_index` | EXT3 / 17 | J15 | `/PIO1_19` |
| `pico_mark` | EXT3 / 19 | K15 | `/PIO1_20` |
| `ack_toggle` | EXT3 / 21 | K16 | `/PIO1_21` |
| `reti_toggle` | EXT3 / 23 | J14 | `/PIO1_22` |
| `ack_index` | EXT3 / 25 | J12 | `/PIO1_23` |
| `backend_ready` | EXT3 / 27 | J13 | `/PIO1_24` |
