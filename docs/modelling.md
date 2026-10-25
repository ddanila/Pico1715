# Using the existing emulator

## What we have

`dac-emulation/machines/robotron1715m` runs an unpatched S550 ROM and TOS/M disk.
It has CPU/DMA-aware I/O traces, disk adapters, device tests and native/browser
runners. The local `robotron-s642-e2e` environment is also a W/M setup. These are
valuable host-side tools, but neither establishes ordinary-1715 floppy behaviour.

The ordinary 1715 MAME source maps two Z80 PIOs at ports 00h–03h and 04h–07h,
and a floppy enable write at 20h. Its ordinary floppy-enable handler is a stub;
the W/M 8272 implementation is not a replacement. These are source observations
to cross-check with primary schematics, not a completed controller specification.

## Current adapter

`tools/dac_capture.c` attaches an observer to DAC's public trace sink. It records
IR, IW and IA with full address, data, scheduling tick and CPU/DMA identity. It
does not replace any device, intercept guest PCs or patch guest ROM. A bounded
run produces a final text screen and counters. The Python wrapper pins the
external source revision, hashes inputs and records whether the prompt appeared.

The adapter only accepts the explicit W/M reference profile. Supplying a classic
1715 ROM to it is not a way to emulate a classic 1715. The built-in device remains
the producer of read values; replaying this trace alone would not independently
validate a new implementation. Repeated callbacks can describe one held cycle.
Cycle stamps must not be treated as logic-analyser edge timings.

## Controller-model boundary

Implement the future card core independently from host file I/O and Pico SDK:
bus read/write requests, elapsed emulated time, reset, interrupt state and backing
storage callbacks. No invented port interface should replace the stock interface.
Derive register, PIO handshake, status, transfer and interrupt expectations from
the ROM/manual, and test them independently of the emulator's device model.

The ordinary-1715 headless profile now supplies CPU, flat RAM and ROM overlay,
with native external-card callbacks. Onboard peripherals are still unimplemented;
the card core will supply controller responses through that seam. The same core
can later run behind a Pico bus frontend. CPU/display timing, controller status
deadlines and physical electrical qualification remain distinct checks.

## Evidence required before calling it compatible

- Reset and stock-ROM boot with identified ROM/media hashes.
- Directory/read plus write/export/reboot checks with unchanged source images.
- Correct no-disk, write-protect, reset-during-transfer and malformed-command
  behaviour, including status polling and interrupts used by the ROM/OS.
- Independent response expectations and bounded-time failures rather than hangs.
- Separate reports for classic 1715 and W/M; no extrapolated family-wide success.
- Physical bus timing and voltage tests before plugging a fabricated card in.

## Implemented integration foundation

DAC commit `5dc3ab52dec0e8c647a3fbeebb74e04cd1f18d4f` adds runtime kind 3,
verification name `robotron1715`, and `dac_pc1715_attach` for native card models.
I/O callbacks and interrupt acknowledgements are delivered once per bus cycle;
RAM trace events retain DAC's per-tick convention. IRQ, RETI, reset and tick
callbacks are available; /WAIT, external memory inhibition and DMA are not.

Synthetic tests cover overlay writes, ROM disable, FIFO-read delivery, IRQ/RETI,
reset, split-run equivalence and runtime rejection of unsupported devices.
The external classic ROM runs for 10 million ticks and reaches PC 0412h in the
controller-ready wait. No original controller is attached, and no disk boot or
physical timing qualification is claimed. The W/M profile stays separate.
