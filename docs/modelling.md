# Modelling Pico1715

## Plain PC1715 integration

The pinned DAC revision provides `machines/robotron1715`: a headless Z80,
64 KB RAM, a 2 KB read-only ROM overlay with writes reaching underlying RAM,
and an external-card callback interface. Pico1715's `model/controller.c`
implements the card through that interface. It receives full I/O addresses,
read/write cycles, ticks, reset, IRQ acknowledgement and RETI, but has no access
to guest memory or instruction addresses. No DAC changes were needed for this
controller milestone.

`tools/classic_probe.c` composes that motherboard with the card and a minimal
SIO receive fixture. Keyboard E0/ASCII frames arrive through I/O, and the
runner observes this SCP revision's screen RAM at F800h. It never patches guest
instructions, injects return values into registers, or bypasses BIOS/BDOS calls.
It records controller reads/writes/interrupt acknowledgements, exports a separate
disk copy, and captures RAM for inspection. Outputs use exclusive file creation.

`tools/check_classic.py` enforces the pinned clean DAC revision and exact ROM/SCP
hashes. Nine scenarios cover cold boot/DIR, SAVE, saved-file persistence, a
2,560-byte BDOS write/read/compare, TYPE after cold boot, deletion and its
persistence, write protection, and absent media. All writes use private copies.
It verifies hashes and independently parses the created files; a successful
process exit or an observed ROM jump alone is not the acceptance criterion.
See [the report](../reports/classic-compatibility.json) and
[controller contract](classic-controller.md).

## What the functional model deliberately abstracts

Each I/O callback is delivered once per bus cycle. An input consumes one field
byte; neither disk rotation nor PIO handshakes determine when that byte appears.
A valid completed write updates a sector atomically. IRQ handling implements
the sequences exercised by the qualified ROM/SCP, not every UB855 mode.

This is a usable stock-software regression model, not a cycle-accurate FDC.
The next layer must explicitly model mark/byte availability, read overruns,
PIO strobes and interrupt edges, CPU wait deadlines, and abort/reset behavior.
Do not carry demand-driven byte generation directly into Pico firmware and
assume the real Z80 will wait for it.

DAC's card seam currently has no /WAIT, external-memory inhibition or DMA.
SIO/CTC/CRT are not fully modelled on the plain motherboard. The keyboard fixture
and screen observer make headless software tests possible without claiming
complete peripheral emulation. Physical bus timing, connector identity,
voltage translation and power sequencing remain separate qualification gates.

## W/M baseline remains separate

`tools/dac_capture.c` observes the existing `robotron1715m` model running S550 and
TOS/M. The wrapper `tools/capture_dac.py` verifies dependency identity and input
hashes and records CPU/DMA-aware traces. This uses the W/M 8272 controller and
cannot validate the ordinary 1715's custom two-PIO controller.

The earlier [classic startup report](../reports/classic-startup.json) is retained
as a no-controller negative baseline. It reaches the ROM's controller-ready wait;
[the newer compatibility report](../reports/classic-compatibility.json) supplies
the positive evidence with the functional card attached.
