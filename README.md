# Pico1715

An independent Pico-based replacement/expansion card for the Robotron PC 1715:
SD-backed virtual floppies, external RAM and a buffered X2 bus interface.
Original project code and design files are MIT licensed; see [LICENSE](LICENSE).

## Status

The scheduled-byte card model boots the unchanged classic ROM into SCP 0006 and
passes nine software regressions plus 36 latency/fault experiments.
See the [timing results](docs/timing-contract.md) and
[hardware requirements derived from them](hardware/timing-requirements.md).
The FPGA normal-I/O and interrupt frontend now passes all nine ROM/OS cases
in RTL co-simulation, including a shared-firmware profile with journaled SD
writeback. A 59-pin Olimex HX8K bench target is placed and routed,
and Pico Plus 2 firmware builds with PSRAM, SD CRC checking and optional journaled
writeback. See the [prototype build, wiring and parts guide](hardware/prototype.md).

**Bench prototype, not ready to manufacture:** no firmware has run on hardware,
no X2 electrical measurements have been made, and no qualified PCB exists.
The firmware co-simulator compiles the same service loop and journal code for
host execution and connects them to the board-level RTL. GPIO, time, PSRAM and
SD blocks are simulated; this does not execute RP2350 instructions or qualify
physical timing. See [firmware co-simulation](docs/firmware-cosim.md) and
[delayed storage, reset and recovery qualification](docs/firmware-storage-faults.md).

The standalone [analyzer transport](docs/analyzer-transport.md) now joins passive
FPGA cycle capture to a CRC-protected Pico link and a bounded 7 MiB PSRAM buffer.
Shared-firmware/RTL tests cover stalls, corruption, retry and buffer exhaustion;
stock-boot replay retains all 215,848 selected records. USB control/download and
analyzer board integration remain open.

The first compatibility target is the **ordinary PC 1715**, retaining its boot
ROM and operating-system floppy routines. It must not be confused with the
**1715W/M**: the existing DAC emulator and available S550/TOS/M reference boot
exercise the latter's 8272-based controller. They are useful infrastructure,
not evidence that the ordinary 1715 controller has been implemented.
The owner's MB001 inventory identifies an ordinary 1715. Its board revision,
connector orientation and electrical behavior still require physical verification.

## Run the existing emulator baseline

Requirements: Python 3.10+, a C11 compiler, Git, and the external
[dac-emulation](https://github.com/ddanila/dac-emulation) checkout at the revision
recorded in [sources.json](docs/sources.json). No Python packages are required.

```sh
python3 tools/capture_dac.py \
  --dac ../dac-emulation \
  --rom ../dac/public/media/robotron/s550.bin \
  --prom ../dac/public/media/robotron/cas.bin \
  --disk ../dac/public/media/robotron/tosm10.img \
  --out local/wm-baseline
python3 -m unittest discover -s tests -v
```

The tool builds its adapter and the external emulator in this project's ignored
`build/` directory. It requires the pinned revision and clean tracked dependency
files. Inputs are read-only; the output directory must not already exist.
It records input hashes, emulator identity, I/O and interrupt-acknowledge events,
a text screen, and a report. It exits unsuccessfully if the boot prompt is absent,
inputs change, or the trace is truncated. ROM and disk contents are not committed.
Even the local trace can contain guest data: it stays ignored by default.

This is an **observational W/M baseline**, not co-simulation with Pico1715.
Read/write events can repeat on consecutive emulated CPU ticks; they are not
necessarily distinct bus transactions. Timestamps are emulator scheduling ticks,
not qualified physical X2 signal edges.

## Next milestones

The [remaining desk-work plan](docs/roadmap.md) starts with shutdown firmware,
safe-eject simulation and an optional current-limited backup-power circuit that
also permits operation without a capacitor. It then covers full interrupt-chain
emulation, broader software compatibility and PCB preparation. These are planned
items, not completed features.

The [bus-analyzer prototype](docs/analyzer-prototype.md) now provides passive RTL
capture, triggers and CSV/VCD export with simulated verification. The separate
[compact cycle analyzer](docs/cycle-analyzer.md) adds filtering and passes stock
ROM/SCP boot comparisons against the emulator, retaining an I/O boot trace in
about 3.3 MiB. The full
[USB bus-analyzer mode](docs/analyzer-mode.md) remains planned,
including full-address capture and an optional remote reset-button connection.
X1/X2's reset contact alone does not reset the CPU on the documented motherboard.

Physical milestones remain:

1. Assemble the selected bench modules and verify PSRAM, SD and FPGA programming.
2. Measure worst-case Pico mailbox latency and translated bus timing on a fixture.
3. Verify X2 orientation, priority-chain wiring and mechanics on the actual 1715;
   boot the unchanged ROM and repeat the read/write/persistence tests.
4. Freeze the schematic, route the PCB, run ERC/DRC, and review manufacturing
   outputs; qualify assembled prototypes before declaring RTM.

See [hardware requirements](hardware/requirements.md),
[modelling plan](docs/modelling.md), [classic controller contract](docs/classic-controller.md)
and [licensing/provenance](NOTICE.md). The initial passing W/M run is recorded in
[reports/wm-baseline.json](reports/wm-baseline.json); local reference identities
are listed in [docs/local-evidence.json](docs/local-evidence.json).

## Plain PC1715 model

The pinned DAC revision supplies `machines/robotron1715` (runtime kind 3) with
64 KB RAM, the original ROM overlay and native card callbacks. This repository's
`model/controller.c` attaches to it without changing the emulator or guest code.
The runner adds a headless keyboard fixture and reads the text screen from RAM.

```sh
make test
python3 tools/check_classic.py \
  --dac ../dac-emulation \
  --rom /path/r1715bt.bin \
  --disk /path/r1715.cpm \
  --out local/classic-check
```

The checker requires the ROM and SCP image hashes recorded in
[local-evidence.json](docs/local-evidence.json), and a fresh output directory.
Inputs are read-only; writes affect disposable copies. It tests original-image
boot/DIR, SAVE, persistence, a disk-loaded BDOS read/write workload, TYPE after
cold boot, deletion/persistence, write protection, and absent media. Model-only
contract tests also cover malformed writes and interrupt/reset behavior.

See [reports/classic-compatibility.json](reports/classic-compatibility.json) and
[the controller contract and remaining gaps](docs/classic-controller.md).
Use `--timed` for scheduled bytes, or `tools/check_timing.py` with the same
arguments for the full timing suite.
**Scheduled bytes are not an electrically qualified hardware design.** Generic
PIO modes, full motherboard peripherals, other formats and physical bus behavior
remain outside this qualification.

## Bench adapter and fixture

The [buffered adapter schematic](hardware/interface/README.md) includes hardware
output gating and dual-rail supervision. The [standalone FPGA/Pico fixture](hardware/bench-fixture.md)
checks 515 mailbox transactions, IRQ/vector/RETI and returns a UART result.
Both are bench artifacts: [X2 common contacts](hardware/x2-pinout.md) are now
source-checked and assigned, including original-controller IRQ direction. Physical
validation and connector footprint selection remain pending.

## Prototype validation

```sh
make test test-store test-frontend test-irq test-pico-top lint-frontend
python3 tools/check_classic.py --cosim --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm --out local/rtl-check
```

RTL co-simulation requires Verilator and a C++ compiler. See
[reports/rtl-compatibility.json](reports/rtl-compatibility.json) for the nine-case
result and source hashes, and [the prototype guide](hardware/prototype.md) for
FPGA and firmware builds. ROMs and disk images remain external.
