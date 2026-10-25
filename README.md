# Pico1715

An independent Pico-based replacement/expansion card for the Robotron PC 1715:
SD-backed virtual floppies, external RAM and a buffered X2 bus interface.
Original project code and design files are MIT licensed; see [LICENSE](LICENSE).

## Status

Research and host modelling have started. No PCB, working controller replacement,
Pico firmware or electrical qualification is claimed yet.

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

1. Establish the ordinary 1715 PIO/controller contract from schematics, boot ROM
   and SCP routines, with explicit differences from W/M.
2. Attach a portable card model to DAC's new ordinary-1715 profile with
   independent expected responses. Run the original boot sequence against it.
3. Boot, read, write and reboot an SD-image equivalent without changing guest ROM
   or BIOS. Test absent media, write protection, reset and timing boundaries.
4. Choose Pico, RAM and bus logic from measured/modelled requirements, then create
   schematics and a PCB. Validate voltages and bus timing on hardware.

See [hardware requirements](hardware/requirements.md),
[modelling plan](docs/modelling.md), [first classic-ROM findings](docs/classic-controller.md)
and [licensing/provenance](NOTICE.md). The initial passing W/M run is recorded in
[reports/wm-baseline.json](reports/wm-baseline.json); local reference identities
are listed in [docs/local-evidence.json](docs/local-evidence.json).

## Plain PC1715 model

The pinned DAC revision now includes `machines/robotron1715`, runtime kind 3,
with 64 KB RAM, the original ROM overlay and native card callbacks. The stock
reference ROM reaches its controller-ready wait without patching. This is a
headless motherboard foundation; PIO/controller, onboard peripherals, display
and OS boot are still unimplemented.

```sh
make -C ../dac-emulation build/pc1715-probe test-pc1715
python3 ../dac-emulation/tools/check_pc1715_rom.py /path/r1715bt.bin \
  --report local/plain-rom-check.json
```

The checker requires the specific ROM hash documented in
[the classic-controller notes](docs/classic-controller.md). It never interprets
startup progress as successful floppy boot. See
[the recorded startup result](reports/classic-startup.json).
