# Pico1715 bench prototype

Status: **buildable, untested on hardware; not RTM**. The architecture is
1715 X2 → TTL-compatible buffering → FPGA → parallel mailbox → Pico Plus 2
→ onboard PSRAM and SPI SD. The FPGA owns waits, data-bus output enables,
interrupt acknowledgement/vector delivery and RETI recognition. The Pico owns
controller state and disk contents. No host RAM expansion is implemented yet.

The [passive analyzer adapter](analyzer-interface/README.md) is a separate bench
variant with input-only receivers and its own 57-pin allocation. Use its wiring
guide and `build_fpga.py --analyzer`; the controller harness below is incompatible.

## Parts selected

Listings checked 2026-10-25; prices are vendor quotations, excluding delivery
and any additional local taxes. Nothing has been purchased.

| Part | Selection and reason | Listing |
| --- | --- | --- |
| FPGA | Olimex iCE40HX8K-EVB; sufficient exposed GPIO, open toolchain, 100 MHz oscillator | [€29.95, in stock](https://www.olimex.com/Products/FPGA/iCE40/iCE40HX8K-EVB/) |
| Pico/RAM | Pimoroni Pico Plus 2, PIM724, RP2350B with 8 MB PSRAM; full 819200-byte disk fits without SD traffic in the serving loop | [199 SEK including 25% VAT, 11 listed](https://www.electrokit.com/en/pimoroni-pico-plus-2-utvecklingskort-med-rp2350) |
| SD breakout | Adafruit 4682, direct 3.3 V SPI/SDIO; no resistor-divider level conversion | [$3.50, in stock](https://www.adafruit.com/product/4682) |
| SD card | Dedicated 8–32 GB SDHC from a normal retailer; existing spare acceptable | Exact vendor/card remains to be qualified |
| Programmer | A second RP2040 Pico is the low-cost candidate; also useful later for SWD | See qualification below |
| Interface | Three SN74LVC245A receiver groups at 3.3 V, SN74AHCT541 host data driver at 5 V; separate priority output and open-drain WAIT/INT circuitry | Circuit/package selection remains draft |

The current FPGA top uses 59 package pins including the oscillator. Smaller
boards exposing about 32 GPIO are not drop-in substitutes. The Olimex SRAM is
unused: the disk cache resides on the Pico board. This selection optimizes the
first bench build, not the eventual production component cost.

An RP2040 programmer candidate is [spi-flasher](https://github.com/aslak3/spi-flasher),
a separate GPL-2.0 tool. Its code is not included in Pico1715. Verify the actual
Olimex SPI flash part and programmer support before erasing anything; the Olimex
listing specifically warns that some older software lacks EN25Q16B support.
Programming and readback have not been tested. An FTDI SPI programmer supported
by the board's tools is an alternative if the Pico route proves unsuitable.

For instruments, borrow an oscilloscope for voltage, edge and setup/hold checks.
A spare Pico running [LogicAnalyzer](https://github.com/gusmanb/logicanalyzer)
can be an inexpensive digital capture tool, but cannot establish analog signal
quality. Probe only within the instrument's input voltage limits.

## What is verified

* Nine unchanged ROM/SCP regressions pass through Verilated normal-I/O and IRQ
  frontend logic: [report](../reports/rtl-compatibility.json).
* The physical-board top's shared mailbox, vector mirrors and IRQ notifications
  also run against the host-compiled production firmware service loop and
  journal code: [firmware co-simulation](../docs/firmware-cosim.md).
  The older `cosim_top` profile remains a C-controller reference comparison.
  Neither profile executes RP2350 instructions or models analog hardware.
* The HX8K target is fully pin-constrained, synthesized, placed and routed:
  [fit report](../reports/hx8k-fit.json). Internal clock timing passes; external
  asynchronous I/O timing, metastability probability and translators remain
  unqualified.
* Read-only and experimental writeback firmware compile with Pico SDK 2.2.0:
  [build report](../reports/firmware-build.json). Portable journal/CRC tests
  exercise failed writes, replay and corrupt records. No SD or PSRAM hardware
  has been exercised.
* A [concrete adapter schematic](interface/README.md) and
  [standalone mailbox fixture](bench-fixture.md) are now available.

## Build

Use Python 3.10+, C/C++ compilers, Icarus, Verilator, Yosys, nextpnr-ice40 and
IceStorm. No proprietary FPGA tools are needed.

```sh
make test test-store test-frontend test-irq test-pico-top lint-frontend
python3 tools/build_fpga.py --out build/hx8k
```

The script takes `--yosys`, `--nextpnr` and `--icepack` executable overrides.
It emits logs, netlist, placement/routing, bitstream and a hash-bearing report.
It never programs a board. The checked fit used Yosys 0.52 and nextpnr source
`22c5adf423ecb602dfc1250d10f740ccfff0786a`; internal 50 MHz logic was
conservatively checked at a 100 MHz constraint.

```sh
# External official SDK checkout at a1438dff1d38bd9c65dbd693f0e5db4b9ae91779
export PICO_SDK_PATH=/path/to/pico-sdk
# Set PICO_TOOLCHAIN_PATH if arm-none-eabi-gcc is not on PATH.
cmake -S firmware -B build/firmware -DPICO_NO_PICOTOOL=1
cmake --build build/firmware -j2
python3 tools/make_uf2.py --bin build/firmware/pico1715.bin --out build/firmware/pico1715.uf2
python3 tools/make_sd_image.py --disk /path/r1715.cpm --out local/card.img
```

Output image tools refuse to overwrite an existing file. The SD image is a raw
**dedicated-card** format, not a file to copy onto FAT. They create files only;
no device flashing is performed. Preserve SDK/toolchain notices if distributing
linked firmware. Project source remains MIT.

Experimental writes require a separate CMake build with `-DP1715_WRITEBACK=ON`.
The default read-only build is the first bring-up target. The UF2 family is
RP2350 Arm secure (`0xe48bff59`); do not flash an RP2040 with this firmware.

## Pico connections

All these links are **3.3 V**. `GP` numbers are GPIO numbers, not header positions.
The exact FPGA package/header allocation is in [hx8k-pins.json](boards/hx8k-pins.json)
and the [human-readable header table](boards/hx8k-wiring.md).

| Pico GPIO | Signal | Direction at Pico |
| --- | --- | --- |
| GP0–7 | pico_data[0–7] | Bidirectional shared byte |
| GP8–11 | pico_reg[0–3] | Input |
| GP12 | pico_write | Input |
| GP13 | pico_request | Input |
| GP14 | pico_ack | Output |
| GP15 | translated host_reset_n | Input; shared with FPGA reset input |
| GP16 | pico_index | Output |
| GP17 | pico_mark | Output |
| GP18 | ack_toggle | Input |
| GP19 | reti_toggle | Input |
| GP20 | ack_index | Input |
| GP21 | backend_ready | Output; low until RAM and media load pass |
| GP22 | SD CS | Output |
| GP26 | SD CLK | Output |
| GP27 | SD DI/MOSI | Output |
| GP28 | SD DO/MISO | Input |
| GP47 | PSRAM CS | Internal onboard connection |

Shared-data transfer is four phase: FPGA raises request with stable metadata;
Pico provides read data or consumes write data, then raises ACK; FPGA completes
the host cycle and lowers request; Pico releases data **before** lowering ACK.
IRQ vectors are cached in FPGA so IACK does not wait for a Pico transaction.
Hold reset/backend-ready low during configuration and initialization.

Pin mapping is checked against the manufacturer's Rev B1 netlist, commit
`dba688dedb3ae08d05e81a0f56a847f155622d21`. With that external file:

```sh
python3 tools/verify_hx8k_pins.py --netlist /path/to/RevB1.net
```

Use the [source-checked X2 table](x2-pinout.md) for contact numbering. Confirm the actual
motherboard revision, contact orientation, ground contacts and priority-chain
insertion before assigning an X2 connector footprint.

## Electrical interface still to qualify

Receive address, data and control through 5 V-tolerant, TTL-threshold LVC inputs
powered at 3.3 V. Use AHCT at 5 V for host outputs, with hardware-default disabled
OE. WAIT and INT require open-drain pull-down stages, not push-pull FPGA pins.
The host-data receive and transmit paths are separate; direction must never rely
on software turnaround alone. IEO needs its own appropriate host-level driver.
Check the exact purchased parts' datasheets, power-off behavior and delays before
freezing the schematic.

Provide a common ground and decoupling, but do not tie independent module 3.3 V
regulator outputs together. External gating must keep host drivers disabled
through FPGA configuration, missing Pico, reset, brownout and either supply
missing. `power_good` is supplied by the dual-rail supervisor logic in the
[bench adapter schematic](interface/README.md). Its dynamic behavior remains
unmeasured. `host_oe` is active high;
the driver interface must implement the appropriate inversion and fail-safe
pull-up at an active-low OE pin.

For RP2350 A2 silicon, follow the Pico Plus 2 manufacturer's
[E9 input-leakage note](https://shop.pimoroni.com/en-us/products/pimoroni-pico-plus-2):
internal pull-downs are insufficient for a guaranteed disconnected low input;
use an external pull-down of 8.2 kΩ or less where needed (4.7 kΩ is the proposed
bench value). All idle/reset defaults need fixture testing before X2 connection.

## Storage and latency limits

The PSRAM driver configures the onboard APS6404L through RP2350 QMI and tests
819200 bytes before loading the image. It is an original implementation based
on the SDK registers and [AP Memory datasheet](https://www.apmemory.com/wp-content/uploads/APS6404L-3SQR.pdf).
The SD driver supports block-addressed cards, command/data CRC and bounded
transport waits. It checks the post-write status before accepting a block write.

Raw SD layout: LBA0 contains `P1715SD1`, image base 2048, length 1600 blocks and
header CRC32. LBA1 is the redo header, LBA2 its payload; the disk starts at
LBA2048. A block write stores journal data, then a committed header, then the base
block, then clears the header. Reopen replays a valid journal; malformed journal
records fail closed. A failed write latches the store until reopen. This does
not prove SD internal-cache durability or atomic power-loss behavior.

Writeback runs on core 1 and snapshots dirty blocks under a short shared lock.
The host sees a RAM-backed write acknowledgement before SD persistence. The
[USB status and safe-eject interface](../docs/controller-usb.md) now exposes the
shutdown state. The [combined carrier](carrier/README.md) additionally supports
the PIM724 button and SAFE LED. These do not establish SD power-loss durability;
experimental writeback remains unqualified for irreplaceable data. Reset retains the loaded image and dirty queue.

The main unresolved performance risks are uncached PSRAM copying, field CRC
construction on the serving core, lock contention and interrupt notification
latency. The frontend watchdog is 4096 cycles at 50 MHz (81.92 μs); meeting it
alone does not prove byte-deadline compatibility. `p1715_status.max_service_us`
measures the accepted handler, not total request-to-ACK latency or tick work.
The [service-cost sweep](../docs/service-costs.md) now provides scripted
byte-loss/watchdog brackets and late-response regressions. Its injected costs
are not measured hardware limits. Use fixture traces to measure the complete
worst case. USB/UART logging is
intentionally disabled on the serving core; inspect diagnostics over SWD.

## Remaining gates before a PCB order

The [desk-work plan](../docs/roadmap.md) records the optional backup-power circuit,
shutdown firmware and simulation work that can proceed before hardware arrives.
Its circuit and energy budget must be validated alongside the physical gates
below; backup power is optional and is not implemented or qualified yet.

1. Program/read back FPGA and Pico separately; verify clock, reset defaults,
   PSRAM patterns, SD CRC/error paths and repeated cold starts with X2 disconnected.
2. Exercise the mailbox under maximum sector-copy, IRQ and SD-write load;
   capture request/ACK, shared-data turnaround, watchdog recovery and reset.
3. Fit translated bus fixture; measure voltage thresholds, contention, OE/data
   setup, WAIT assertion/release and IRQ/RETI at worst supply/load conditions.
4. Verify actual X2 pin orientation, mechanics, power and IEI/IEO chain. Then
   boot the stock ROM on the real 1715 and repeat all nine OS regressions.
5. Resolve measured failures, complete the schematic and layout, pass ERC/DRC,
   review BOM/footprints, and export reviewed Gerbers, drills and assembly files.
6. Order a small prototype batch, qualify it (including power cycling and storage
   recovery), and only then mark the manufacturing revision ready.

These physical gates are open. There are no Gerbers, order-ready PCB or hardware
qualification results hidden behind the software reports.
