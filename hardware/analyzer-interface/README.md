# Passive analyzer bench adapter, revision A

This is a separate receive-only adapter for the Olimex HX8K analyzer personality.
It is a concrete schematic and routed FPGA target, **not a PCB or qualified
machine interface**. Do not connect the controller harness to this bitstream:
several former host-output FPGA pins are now receiver inputs.

- [Editable KiCad 10 schematic](analyzer-interface.kicad_sch) and [SVG preview](preview/analyzer-interface.svg)
- [BOM](bom.tsv) and [pin/net manifest](connections.json)
- [FPGA/header/Pico wiring table](../boards/hx8k-analyzer-wiring.md)
- [Connectivity report](../../reports/analyzer-interface.json) and [FPGA fit report](../../reports/analyzer-hx8k-fit.json)

The original [controller adapter](../interface/README.md) remains unchanged.
Mode selection for this bench revision means selecting the matching adapter,
FPGA bitstream and Pico firmware while disconnected from the motherboard. There
is no runtime switch between floppy controller and analyzer. A passive analyzer
will observe a missing floppy controller's boot attempt, but will not supply a disk.

## Receive-only circuit and supplies

U1–U5 are SN74LVC541ADWR input-only octal receivers powered from FPGA 3.3 V. Their
A pins face the host; Y pins face the FPGA. Both active-low OE pins are grounded.
Unlike a bidirectional transceiver, there is no DIR input whose state could turn
a host input into a driven output. [TI's datasheet](https://www.ti.com/lit/ds/symlink/sn74lvc541a.pdf)
specifies 5.5 V-tolerant inputs and partial-power-down Ioff support. Three unused
channels have grounded inputs and explicitly unconnected outputs. Use the exact
part/package or review substitutes against its thresholds, pinout and power-off
behavior. This digital topology is not a measurement of analog loading or supply
transients.

The receivers cover A0–A15, D0–D7, /MREQ, /IORQ, /RD, /WR, /M1, /RFSH, TAKT-X2,
connector /RESET2, /WAIT, /INT, /BUSRQ, /BAO and the priority-chain input.
U1/U2 receive addresses, U3 data, U4 the first eight control signals, U5 the
remaining five. C1–C6 are 100 nF local decouplers for U1–U6 respectively.
The connectors are logical bench/header connections; their footprints and the
Robotron mating connector mechanics remain unresolved. IC/passive package
footprints are specified, but no PCB placement or DRC is claimed.

J2 takes 3.3 V from the FPGA board and common ground. Do not join the Pico's
3.3 V regulator output to that rail. X2 host +5 V feeds only R2, the 10 kΩ
priority pull-up. Host negative rails and +12 V remain unconnected. The two
module supplies must be present before attaching their direct 3.3 V harness;
this revision does not isolate an independently powered USB Pico from an
unpowered FPGA. Do not hot-plug that harness. Power sequencing/backfeed tests
remain mandatory before connecting the 1715.

U6 is TLV803EA30DBZR with the same reviewed standard DBZ pinout as the controller
adapter: pin 1 ground, 2 open-drain reset, 3 supply. R3/R4 pull its output up/down.
`CARD_PG` goes to the FPGA capture reset input. It supervises the card's 3.3 V
rail only; its propagation/ramp behavior is not qualified here. It is independent
of observed host reset. R5 pulls CAPTURE_CLEAR high by default; R6–R8 pull capture
enable, link synchronization and ACK low, all 4.7 kΩ. A missing/uninitialized
Pico therefore leaves acquisition cleared, without relying on internal pulls.

## Interrupt chain and isolation

R1 is a fitted 0 Ω physical bypass from X2 B10 to X2 A10. R2 biases its upstream
side from host +5 V, following the existing classic-X2 chain profile. This keeps
the observed slot out of interrupt arbitration during FPGA configuration,
card reset, firmware failure, USB disconnect and an unpowered card. It does not
provide any independent IEO output; the two sides are the same passive chain.
The FPGA's sample IEI/IEO bits therefore use the same received level.

This wiring is specifically for documented classic X2. Do not substitute an X1
harness: see the original-sheet [contact review](../x2-pinout.md). The selected
machine revision and physical mating-face orientation still need verification.

No data driver, open-drain host-control transistor, host-reset driver or
FPGA-controlled IEO stage is fitted. All host-facing semiconductor signal pins
are receiver inputs. Thus firmware or reconfiguration cannot enable a host-output
path in this schematic. No control signal, including USB/DTR, is connected to
the motherboard reset generator. A20 is observed /RESET2, not CPU /RESET1.
A future remote-reset accessory remains separate work.

## FPGA personality and timing

Build `analyzer_hx8k` with the analyzer-specific constraints:

```sh
python3 tools/build_fpga.py --analyzer --out build/analyzer-hx8k
make test-analyzer-hx8k lint-analyzer-hx8k
```

Executable overrides `--nextpnr`, `--yosys`, `--icepack` work as for the controller.
The local tool setup may need `--nextpnr local/nextpnr-build/nextpnr-ice40` and
`--icepack local/fpga-tools/usr/bin/icepack`. The script produces `design.bin`,
source hashes, route logs and a report; it never programs hardware.

The onboard 100 MHz oscillator divides to a constrained 50 MHz acquisition
clock. The reported fit uses 1,535/7,680 logic cells, 8/32 RAM blocks, 57 I/O and
7/8 global buffers. Routed acquisition Fmax is 89.95 MHz against 50 MHz;
the 100 MHz divider also passes. This closes only internal synchronous paths.
There are no external setup/hold guarantees for asynchronous host or Pico signals.

All 37 host input pads feed matched two-stage sampling registers. These are kept
in synthesis, including clock/INT/BUSRQ/BAO/priority channels that the current
compact encoder does not export. The two-stage delay is nominally 40 ns at
50 MHz; it reduces propagation of metastability but cannot make simultaneous
multibit transitions coherent. Sampling uncertainty, short pulses, receiver
skew, translator delay and loading must be measured. Do not interpret the
internal Fmax result as host-bus timing closure.

The existing compact USB firmware uses mask 0x170 (I/O, IACK and reset). Full
address inputs are now available, but this revision does not add USB raw-window
capture or change filtering. Clock and other additional levels are routed for
future raw capture; the current cycle files do not contain their waveforms.
Host /RESET2 is an observed interval, never capture reset. The board-level test
checks full 16-bit address/data, WAIT samples, packet framing, host-reset sequence
continuity, and separate card-power reset.

## Bench wiring and acceptance

1. Keep X2 disconnected. Assemble receivers, decoupling and supervisor on the
   bench adapter, using the manifest's numbered IC pins. Verify grounds, rails,
   receiver direction and absence of any path from FPGA outputs to host inputs.
2. Fit R1 and verify continuity from X2 B10 to A10 with all power removed. Confirm
   the source drawing orientation before wiring the actual connector; these
   names are electrical contacts, not a guessed mating-face view.
3. Power the FPGA and Pico independently with common ground. Supply J2 from the
   FPGA 3.3 V rail. Check CARD_PG release and the four control defaults with the
   Pico harness detached. Keep GP15 and GP18–20 disconnected; GP18's former FPGA
   pin is now a BUSRQ observation input.
4. Follow the [generated harness table](../boards/hx8k-analyzer-wiring.md) for
   EXT1/EXT2/EXT3 and Pico GPIOs. J1 identifiers are **GPIO names**, not Pico header
   pin numbers. Use short wiring and adjacent grounds; header grounds 2/4/8 are
   connected on each used Olimex header. No FPGA pin accepts a direct 5 V signal.
5. Program/read back the analyzer FPGA bitstream and `pico1715_analyzer` firmware
   with the host still disconnected. Exercise the [USB commands](../../docs/analyzer-usb.md),
   feed a controlled translated bus pattern, stop and download. Compare expected
   addresses, data, WAIT and reset intervals with the decoded file.
6. Scope receiver outputs and supply sequencing. Measure setup/hold, loading and
   worst-case capture backlog with USB traffic. Verify chain continuity and that
   host lines remain undriven through configuration, USB disconnect and rail loss.
7. Only after these checks, connect the verified X2 harness and observe the real
   machine. Record whether clock/reset/IRQ behavior matches the source drawings.

No physical steps above have been performed. The result is ready for bench
assembly review, not manufacture or an unconditional connection to the machine.

## Reproduce schematic and pin checks

```sh
python3 tools/generate_analyzer_interface.py
kicad-cli sch erc hardware/analyzer-interface/analyzer-interface.kicad_sch \
  --exit-code-violations --output build/analyzer-interface-erc.rpt
kicad-cli sch export netlist hardware/analyzer-interface/analyzer-interface.kicad_sch \
  --format kicadxml --output build/analyzer-interface.net.xml
python3 tools/check_analyzer_interface.py --netlist build/analyzer-interface.net.xml \
  --design build/analyzer-hx8k/design.json
python3 tools/verify_hx8k_pins.py --mapping hardware/boards/hx8k-analyzer-pins.json \
  --netlist local/olimex-hx8k/HARDWARE/REV-B1/iCE40HX8K-EVB_Rev_B1.net
```

KiCad 10 ERC reports zero errors/warnings. The exported-netlist checker verifies
all X2 contacts, fixed receiver direction, physical bypass, defaults, and every
PCF/header/Pico connection. Official-board checking uses the pinned manufacturer's
Rev B1 netlist hash and checks that chosen GPIO nets are unshared. RTL tests/lint
run in CI; KiCad and routed-fit checks were run locally with recorded evidence.
