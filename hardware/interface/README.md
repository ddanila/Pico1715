# Buffered bench adapter, revision B

Editable source: [bench-interface.kicad_sch](bench-interface.kicad_sch), with
project and original symbol library beside it. Open the project in KiCad 10.
[SVG preview](preview/bench-interface.svg), [BOM](bom.tsv), and
[pin/net manifest](connections.json) are generated from
[generate_interface.py](../../tools/generate_interface.py).

**Schematic draft for bench assembly, not a released 1715 card.** There is no PCB
layout. X2 now uses the documented A1–A29/B1–B29 contacts; J1–J3 remain
logical breakout headers on those nets. The [contact table](../x2-pinout.md)
records the sources and the A10/B10 interrupt-chain exception. J11 isolates
those two contacts until configured; R15 holds card IEI high while unpatched.
The connector footprint still needs mechanical and orientation verification.

## Circuit

U1–U3 receive A0–A7, D0–D7 and seven control signals at 3.3 V through
[SN74LVC245A](https://www.ti.com/lit/ds/symlink/sn74lvc245a.pdf). DIR is high
and OE is low: all three always receive from A to B. The unused input has a
pull-down and its output is explicitly unconnected.

U4 is a **SN74AHCT541**, replacing the earlier proposed AHCT245 transceiver.
Only the direction towards the host is needed, so separate input-only pins avoid
exposing an unused bidirectional output stage on the Pico/FPGA side. OE1 is tied
low, OE2 is disabled by a 1 kΩ pull-up to the host 5 V supply. AHCT provides TTL
input thresholds for 3.3 V control. U5 is the corresponding single-channel IEO
buffer. See the [541 specification](https://www.ti.com/product/SN74AHCT541) and
[1G125 specification](https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf).

U6/U7 compute:

```
POWER_GOOD = PG3 & PG5
ARMED = POWER_GOOD & CDONE & BACKEND_READY & F_RESET_N & ARM
```

U8 NAND gates and U9 open-drain buffers then implement:

```
DATA_OE_N = !(ARMED & F_HOST_OE)
WAIT_N    = !(ARMED & F_WAIT)
INT_N     = !(ARMED & F_INT)
IEO_OE_N  = !ARMED
```

U9's [SN74LVC07A](https://www.ti.com/lit/ds/symlink/sn74lvc07a.pdf) outputs
accept host-level pull-ups and support Ioff when their supply is absent. No
push-pull output drives WAIT or INT. Their pull-ups belong to the host; add
1 kΩ pull-ups to 5 V on an isolated bench fixture only, and remove them before
connection if the motherboard already supplies suitable pull-ups. IEO is high
impedance while disarmed; this is **not** an automatic daisy-chain bypass.

U10/U11 are TLV803E supervisors with nominal 3.08 V/4.63 V thresholds and 200 ms
release delay. The [datasheet naming and pin table](https://www.ti.com/lit/ds/symlink/tlv803e.pdf)
defines standard DBZ as pin 1 GND, 2 RESET, 3 VDD. Do not substitute R/V pinout
variants. These are proposed exact options; distributor stock and substitutes
must be checked before buying. Each PG output is pulled up to its own supply
and down to ground, so an absent 5 V source does not become a floating logic high.
Supervisor propagation delay and behavior during fast supply collapse still need
measurement; ERC does not establish fail-safe behavior at arbitrary ramp rates.

R7–R13 provide default-low arm/configuration/readiness/drive requests. C1–C11
are one 100 nF ceramic per corresponding IC, at the supply pins. Use local bulk
capacitance appropriate to the module supply wiring and measure rail droop.

## Harness mapping

Use the manifest for every physical header pin. These net names map to the
production FPGA top and its [verified Olimex headers](../boards/hx8k-wiring.md):

| Adapter net | FPGA top signal |
| --- | --- |
| F_A0…7 | host_addr[0…7] |
| F_DI0…7 | host_din[0…7] |
| F_DO0…7 | host_dout[0…7] |
| F_IORQ_N, F_M1_N, F_MREQ_N, F_RD_N, F_WR_N | iorq_n, m1_n, mreq_n, rd_n, wr_n |
| F_IEI, F_IEO | iei, ieo |
| F_RESET_N | host_reset_n; also Pico GP15 |
| F_HOST_OE, F_WAIT, F_INT | host_oe, wait_pull_low, int_pull_low |
| POWER_GOOD | power_good |
| BACKEND_READY | Pico GP21 / FPGA backend_ready |
| CDONE | Olimex PGM1 pin 5, board configuration-done signal |

J9 pin 1 is the FPGA board's 3.3 V rail; pin 2 is the host/fixture 5 V rail;
pin 3 is common ground. Supply rails are not generated here. Never parallel
independent module regulator outputs. The Pico-FPGA mailbox is wired directly
as in the prototype guide; this adapter does not isolate it when one module is
unpowered. Power both modules before linking them and do not hot-plug that cable.

## Repeatable adapter checks (no 1715 attached)

1. Disconnect FPGA and Pico signals from the adapter. Remove JP1. Supply J9 from
   a current-limited source, verify rail polarity, then check PG3/PG5 release.
   Confirm DATA_OE_N/IEO_OE_N rise to 5 V and WAIT/INT remain released with fixture
   pull-ups. Record supply current and rail voltages.
2. For manual static checks, drive J3 reset high through 1 kΩ from 5 V. Drive J8
   CDONE and BACKEND_READY high through 1 kΩ from 3.3 V. Close JP1. Use 1 kΩ
   stimulus resistors for logic inputs; do not inject a source into receiver
   outputs or connect a powered FPGA during these manual checks.
3. Drive J6 data inputs with 00, FF, AA, 55, each walking one and walking zero.
   Raise F_HOST_OE via J7 pin 8. Compare H_D at J2 and F_DI at J5. Lower F_HOST_OE;
   temporary 10 kΩ pull-ups on J2 should read FF, and temporary pull-downs should
   read 00. This checks release as well as data, with no other active bus driver.
4. Toggle F_WAIT/F_INT via J7 pins 9/10 and verify active-low J3 pins 8/9. Verify
   IEO follows F_IEO (J7 pin 11 to J3 pin 10) only when armed.
5. In turn remove JP1, lower CDONE, lower readiness, assert host reset, and remove
   each supply. Record disabled host outputs. Supply-ramp tests must include
   scope captures; a static logic test does not qualify brownouts.
6. Remove the manual sources and fixture pull-ups. Connect the production FPGA
   mapping and Pico only after the standalone mailbox test below passes. Keep
   the 1715 disconnected until physical orientation, IRQ routing and timing are reviewed.

## Timing measurements still required

| Measurement | Probe points | Required decision |
| --- | --- | --- |
| WAIT assertion | host IORQ/RD/WR, H_WAIT_N | Meet actual CPU sampling setup, including receiver + FPGA + U8/U9 delays |
| Data-enable/release | F_HOST_OE, DATA_OE_N, representative H_D | Data stable before WAIT release; no contention after deselection |
| WAIT/INT rising edge | H_WAIT_N/H_INT_N with actual pull-up/load | Measure RC rise to the CPU input threshold, not just digital edge time |
| IACK vector | M1, IORQ, H_D, DATA_OE_N | Valid vector within the real IACK window |
| RETI sampling | M1, MREQ, RD, data | FPGA must sample valid memory data; emulator fetch timing is not proof |
| Power faults | rails, PG3/PG5, OE, H_D | No unintended drive through measured power sequences |

The existing frontend provides a nominal 20 ns data-settle stage. Additional
adapter delays may require increasing that interval. Do not treat the fitted
FPGA clock report as closure of these paths. No measurements have been recorded.

## Reproduce checks

```sh
python3 tools/generate_interface.py
kicad-cli sch erc hardware/interface/bench-interface.kicad_sch \
  --exit-code-violations --output build/interface-erc.rpt
kicad-cli sch export netlist hardware/interface/bench-interface.kicad_sch \
  --format kicadxml --output build/interface.net.xml
python3 tools/check_interface.py --netlist build/interface.net.xml
```

The current design has zero ERC errors/warnings. The exported netlist is also
checked for pin/rail/direction connectivity and all 512 combinations of the six
qualifiers plus three drive requests. These checks are digital/connectivity
checks; neither is an analog simulation or hardware result.
