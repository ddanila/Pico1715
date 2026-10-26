# Stock SCP with modeled motherboard peripherals

`tools/classic_probe.c` now always enables DAC's onboard CTC/SIO. The former
keyboard port stub is removed: no fixture supplies values for IN 0Ch/0Eh or
intercepts SIO register writes. The keyboard source submits completed E0/ASCII
bytes through `pc1715_sio_receive`; the modeled SIO handles receiver enable,
status/register selection, FIFO contents and guest data reads. The existing
card callbacks now serve only the external controller.

The functional and scheduled-byte stock ROM/SCP suites pass without modifying
the guest or the pinned emulator. The firmware/RTL suite exposes a receive
overrun described below and is **not cleanly qualified** with this input path.
These tests exercise the existing register subset, not every SIO mode.

## Input timing and scope

Input begins after 20 million CPU clocks. Prefix and character bytes are spaced
by 1,000 clocks; subsequent characters by 100,000 clocks; a carriage return allows
10 million clocks for command execution. The fixture waits while RX is disabled
or the three-byte FIFO is full. Reset restarts the command source and the guest
must re-enable the receiver. This is a deliberately paced completed-byte source,
not a keyboard MCU, serial line waveform or measurement of keyboard baud rate.

No instruction/register return values are injected and no BIOS/BDOS call is
bypassed. FIFO backpressure belongs to the test source; it does not claim the
physical keyboard can observe the SIO FIFO. The guest's normal data reads consume
bytes. The checker requires exactly two injected and consumed bytes per command
character, onboard mode enabled, observed SIO/CTC configuration writes and no
SIO receive error. Existing disk-content and screen expectations still apply.
A disabled receiver is separately tested and receives no queued input.

## Reproduce and regressions

ROM-free CI test (uses an original synthetic Z80 program):

```sh
python3 tools/check_onboard_keyboard.py --dac ../dac-emulation \
  --out local/new-onboard-keyboard
```

This compiles the **real boot probe** with UBSan and runs receive-enabled and
receive-disabled guests. The enabled guest programs the CTC and SIO, polls RR0,
reads eight bytes from the FIFO with IN, and stores the exact E0/D/I/R/CR sequence
in RAM. The disabled guest sees no bytes. Both leave the disk unchanged. The
existing firmware/RTL smoke also asserts onboard mode is enabled.

The private-image regression is unchanged in scope and now mandates the native
SIO path:

```sh
python3 tools/check_classic.py --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm --out local/new-onboard-classic
# Repeat with --timed or --firmware-cosim for the other execution paths.
```

Nine cases cover boot/DIR, SAVE, cold-reboot persistence, the generated BDOS
read/write/compare workload, TYPE after reboot, deletion and cold verification,
write protection, and absent media. Exact ROM/disk identities and source hashes
remain recorded; image payloads are not committed. The checker retains all
previous acceptance criteria and adds keyboard-path checks, so falling back to
the removed port stub or silently dropping input cannot pass.

Reports:

- [ROM-free keyboard regression](../reports/onboard-keyboard.json).
- [Functional stock workloads](../reports/onboard-classic.json).
- [Scheduled-byte stock workloads](../reports/onboard-timed.json).
- [Shared firmware and RTL diagnostics — not accepted](../reports/onboard-firmware.json).

The stock software consumes keyboard input by polling. These tests qualify its
SIO usage and onboard register programming, not every interrupt mode. Separate
[card–CTC–SIO tests](motherboard-interrupts.md) exercise vectored interrupts and
nesting. Full serial timing, special receive conditions, modem-line behavior,
CRT emulation, X1 expansion and physical validation remain open.

## Firmware timing failure exposed by migration

The changed keyboard delivery phase exposes a collision between index and mark
interrupts in the firmware/RTL BDOS workload. The local diagnostic trace shows:

```text
27037951 IW 8104 81   arm field acquisition
27038015 IA 0000 10   index interrupt
27038093 IA 0000 12   mark interrupt
27038143 IR 8102 a1   first data read
```

Temporary instrumentation located the overrun at CPU clock 27,038,109, PC E98Bh:
the second byte of a ten-byte ID field arrived with the first still unread.
The guest retries and prints `PICO READ WRITE OK`, but recovery does not satisfy
the zero-overrun acceptance criterion. No input delay, FIFO depth or controller
behavior has been changed to avoid the collision.

All nine firmware cases completed their screen, keyboard and disk-content checks.
The BDOS case has one overrun; the other eight have zero timing faults.

The checker preserves raw probe output and completes the remaining cases after
a timing fault, writes `accepted: false` with per-case `timing_failures`, and
**exits nonzero**. Other compatibility failures still stop immediately. Historical
firmware passes used the old keyboard stub and do not supersede this result.

Next desk milestone: make the index/mark collision a ROM-free firmware regression,
then sweep acquisition/index phase and determine whether the synthetic field/index
model or interrupt service needs correction. The current model schedules index
and field acquisition independently; this trace does not establish that physical
hardware will lose a byte. Serial waveforms and bench timing remain separate work.
