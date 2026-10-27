# Combined carrier A — schematic review draft

One wiring contract for controller and passive analyzer operation, using the
Olimex iCE40HX8K-EVB **Rev B1** and Pimoroni Pico Plus 2 **PIM724** as references.
This is an original MIT-licensed design. **No PCB is ready to order.**

[KiCad schematic](carrier.kicad_sch), [SVG preview](preview/carrier.svg),
[exported netlist](carrier.net.xml), [draft BOM](bom.tsv),
[connection manifest](connections.json).
The older controller and analyzer bench adapters remain separate targets;
neither old analyzer bitstream nor old analyzer harness fits this carrier.

## Operating modes

| Selector | FPGA / Pico firmware | Electrical behavior |
| --- | --- | --- |
| PASSIVE | carrier analyzer / analyzer | 37 input-only receivers; data, WAIT and INT outputs disabled; priority bypassed physically |
| CONTROLLER | carrier controller / controller | Data, WAIT, INT and IEO enabled only after all qualifiers pass |

**Change the selector and firmware only with host, module supply and USB power
off.** This design does not support live mode switching or hot insertion.
SW1 now selects C&K **JS202011JCQN**, with an original vendor-numbered
footprint. Its commons are terminals **2 and 6**: PASSIVE connects 1–2 and 5–6;
CONTROLLER connects 2–3 and 6–7. Passive grounds the mode qualifier and connects
X2 B10 directly to A10, physically disconnecting the IEO driver. A missing switch
still disarms drivers but does not provide priority continuity. The installed
KiCad footprint uses different second-pole numbering and must not be substituted.
Confirm actuator direction/labels and continuity on a sample before assembly.
See the [footprint audit and allocation study](mechanics.md).

The passive interlock is external logic and remains effective even with the
controller FPGA image loaded. A separate FPGA personality output is LOW for the
analyzer and HIGH for the controller, additionally disarming analyzer firmware
when the selector is accidentally left in controller position. This is not
protection against arbitrary faulty bitstreams while deliberately in CONTROLLER.
Always pair the matching Pico and FPGA personalities.

The eight host-drive qualifiers are FPGA 3.3 V good, host 5 V good, Pico 3.3 V
good, configuration done, controller personality, backend ready, host /RESET2
released, and physical controller selection. Data/WAIT/INT requests are then
gated independently; IEO has the same global enable. WAIT/INT remain open-drain
and use the motherboard's pull-ups. /RESET2 is **sampled only**, not CPU reset.
The optional GP22 reset accessory cannot be enabled: GP22 is SD chip select.

## Wiring and power

Five SN74LVC541A receivers capture A0–A15, D0–D7 and all 13 selected control
signals. Added analyzer inputs use spare HX8K pins rather than controller output
pins. [Controller](../boards/hx8k-carrier-controller.json) and
[analyzer](../boards/hx8k-carrier-analyzer.json) maps contain physical header
contacts and FPGA balls; the generator emits their PCFs. Both are checked against
the pinned manufacturer Rev B1 netlist. J1 pin 1 taps **PGM1 pin 5 (CDONE)** and J1 pin 2 is ground; J1 is a separate carrier header. Other
programming contacts are not connected by the carrier. Carrier CDONE pull-down
is 100 kΩ, avoiding a large divider with the board's existing 2.2 kΩ pull-up.

J2 uses actual Pico physical header positions, not GPIO identifiers. J3 defines
standard microSD contact numbers for SPI1: GP26 clock, GP27 MOSI, GP28 MISO,
GP22 CS. The selected socket is Hirose DM3AT-SF-PEJM5, **not** an arbitrary breakout
header. Its extra card-detect footprint pads 9/10 are explicitly NC; all four
shield lands share SH/GND. The current engineering drawing remains a release gate.
DAT1/DAT2/CS have pull-ups; the card shares Pico 3.3 V and ground. The PIM724 socket-pair footprint uses the standard 40-pin header geometry and a
conservative module envelope. Exact socket height and mating checks remain open.

J4 takes regulated 5 V from an external current-limited bench supply. It feeds
HX8K EXT1 pin 1 and Pico VSYS through D1; **do not simultaneously feed the HX8K
barrel jack or another 5 V header**. D1 prevents USB-powered Pico VSYS from feeding
the FPGA supply. EXT1 pin 3 supplies receiver/gate logic from the FPGA's 3.3 V
rail. Pico pin 36 supplies SD and its own supervisor from the separate Pico rail.
No regulator outputs are paralleled. X2 5 V powers only the host drivers,
priority pull-up and host supervisor; module current is not taken from the 1715.
All grounds are common; USB is not galvanically isolated.

Three SN74CB3Q3245 bus switches isolate all 22 Pico/FPGA GPIO connections when
configuration or either 3.3 V supervisor is not ready. They support bidirectional
mailbox traffic without firmware-controlled direction. Their Ioff feature covers
power-off; supervisor delays, falling rails, startup glitches, leakage and
injection current remain **analog bench gates**, not proven by Boolean tests.
The FPGA analyzer's power-good comes from the module/link domain, independently
of host reset and host 5 V, so host reset/power transitions remain observable.
The Pico-side GP15 host-reset input is unused by analyzer firmware.

Place one 100 nF capacitor at each IC supply and SD, and the bulk capacitors at
module/card entry points. Verify module rail capacity, total loading, SD peaks,
USB/external supply behavior, connector current and grounding before layout.
The optional shutdown reserve/slow-charge circuit stays in the existing plan;
this draft has no supercapacitor and no protected-writeback hardware claim.

## Eject and status

Build with `-DP1715_CARRIER=ON` for the PIM724 panel. Hold its existing BOOT/user
button (GP45, active-low) for at least 500 ms **while firmware is running** to
request eject. The onboard GP25 LED is off during normal use/draining/failure,
and lights only after a completed status snapshot reports SAFE, no dirty blocks,
no storage operation and no storage error. Use USB status to distinguish states
when the LED is off. No automatic remount occurs; restart to use the media again.
Holding BOOT during startup retains the module's normal bootloader behavior.

The panel and USB client serialize requests through the same bounded core-1 to
core-0 mailbox. A button request persists through contention; an acknowledgment
alone never lights SAFE. USB status/eject remains available with the panel option
off. Physical GPIO behavior and USB operation still need hardware testing.

## Reproduce the desk checks

```sh
python3 tools/generate_carrier.py
make test-carrier-schematic test-carrier test-carrier-rtl
python3 tools/build_fpga.py --carrier
python3 tools/build_fpga.py --carrier --analyzer
python3 tools/check_carrier.py --netlist build/carrier.net.xml \
  --controller-design build/hx8k-carrier/design.json \
  --analyzer-design build/analyzer-hx8k-carrier/design.json
cmake -S firmware -B build/carrier-firmware -DP1715_CARRIER=ON -DPICO_NO_PICOTOOL=1
cmake --build build/carrier-firmware -j2
```

Pass `--nextpnr`/`--icepack` to select local tools, and set the Pico SDK/toolchain
paths for firmware. `PICO_NO_PICOTOOL=1` produces compile-only ELF/BIN artifacts,
not a tested flashing package. `P1715_CARRIER` rejects another Pico board and the
conflicting GP22 reset accessory. Experimental/protected writeback remain
separate, explicit options with their existing qualification requirements.

The checker inspects real exported nets, all 58 X2 contacts, 37 receive paths,
22 isolation channels, module rails, priority switch wiring, PCFs and 2,048 gate
combinations. Mutation controls intentionally alter both manifest and netlist to
ensure unsafe wiring changes do not pass by agreeing with each other. With
synthesis output supplied it also checks constant personality straps and that
the analyzer exposes no host-driving ports. Internal FPGA timing passes are not
external bus timing measurements. CI checks the reviewed netlist snapshot and
regeneration and both synthesized port contracts; `test-carrier-schematic` requires KiCad 10 and exports fresh nets.

## Remaining gates

The [partially routed review board](carrier.kicad_pcb) has 74 electrical footprints,
four provisional mounting holes and pad-to-net checks. Eighteen IC bypass capacitors
have short supply/ground connections; 2,206 track segments, 426 vias and front/back
ground pours connect all placed non-SD terminals. Geometric DRC is clear; all 12
remaining connections involve the held J3 socket. See [routing evidence](routing.md).
X2 remains unplaced; the FPGA
cable/header candidates and exact SD exclusions still need qualification. See
[mechanics](mechanics.md) for selection evidence, the preview and remaining gates.
Verify mating parts, cable continuity, X2 installation geometry and board fit. Complete load/startup/falling-rail
analysis and power measurements, input/driver timing and priority-chain tests,
then placement/routing, ERC/DRC, assembly review and a small prototype order.
The existing board inventory may change module connectors before that freeze.

Primary design references: [TI LVC541A](https://www.ti.com/lit/ds/symlink/sn74lvc541a.pdf),
[TI CB3Q3245](https://www.ti.com/lit/ds/symlink/sn74cb3q3245.pdf),
[TI TLV803E](https://www.ti.com/lit/ds/symlink/tlv803e.pdf),
[Pimoroni PIM724](https://shop.pimoroni.com/products/pimoroni-pico-plus-2),
[Olimex Rev B1](https://github.com/OLIMEX/iCE40HX8K-EVB/tree/dba688dedb3ae08d05e81a0f56a847f155622d21/HARDWARE/REV-B1).
Host contacts retain the [source audit](../boards/x2-contacts.json).

Recorded results: [desk summary](../../reports/carrier-desk.json),
[connectivity](../../reports/carrier-connectivity.json),
[controller fit](../../reports/carrier-controller-fit.json),
[analyzer fit](../../reports/carrier-analyzer-fit.json),
[ERC](../../reports/carrier-erc.rpt).
