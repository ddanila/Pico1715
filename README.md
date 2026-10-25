# Pico1715

An independent Pico-based replacement/expansion card for the Robotron PC 1715:
SD-backed virtual floppies, external RAM and a buffered X2 bus interface.
Original project code and design files are MIT licensed; see [LICENSE](LICENSE).

## Status

The scheduled-byte card model boots the unchanged classic ROM into SCP 0006 and
passes nine software regressions plus 36 latency/fault experiments.
See the [timing results](docs/timing-contract.md) and
[hardware requirements derived from them](hardware/timing-requirements.md).
No PCB, Pico firmware or electrical/timing qualification is claimed yet.

The first compatibility target is the **ordinary PC 1715**, retaining its boot
ROM and operating-system floppy routines. It must not be confused with the
**1715W/M**: the existing DAC emulator and available S550/TOS/M reference boot
exercise the latter's 8272-based controller. They are useful infrastructure,
not evidence that the ordinary 1715 controller has been implemented.
The owner's earlier specimen inventory also leaves exact machine identity
unresolved. Resolve this from the existing hardware records before committing
the electrical design; it does not prevent starting the model.

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

1. Prototype deterministic bus decode, /WAIT, data gating and IRQ handling using
   the [timing requirements](hardware/timing-requirements.md).
2. Implement Pico firmware and SD/RAM caching; measure latency on a bus fixture.
3. Confirm connector identity, electrical behavior and mechanics on the machine.
4. Freeze schematic and layout only after those checks pass.

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
