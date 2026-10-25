# First ordinary-PC1715 boot-ROM observations

Evidence inspected on 2026-10-25: the external 2048-byte `r1715bt.bin` with
SHA-256 `51cb80639b5667f2611da71ce7305061566cf3474bda7db6fc82709d08e46d01`.
A cached disassembly credits Christian Corti, Computermuseum Stuttgart, 2002;
its SHA-256 is recorded in `local-evidence.json`. Neither file is redistributed.
The original download provenance and relationship to the owner's ROM still need
confirmation. This is a concrete reference revision, not an identified specimen.

These instruction observations were checked directly against bytes in that ROM:

| ROM address | Observation | Consequence for modelling |
|---|---|---|
| 0018h / 001Ah | LDIR followed by OUT (28h),A | The boot code copies itself before disabling ROM; preserve writes to underlying RAM. |
| 0309h | OUT (04h),A | Controller control-port writes must be observed. |
| 0318h | OUT (20h),A | Include the drive-selection/control latch in the contract. |
| 037Ch | OUT (06h),A | Port 06h has a write role as well as status reads. |
| 03CBh | IN A,(06h) | The seek path polls controller status. |
| 040Ch / 041Eh | OUT (05h),A | Model the PIO control path; do not treat every port as a byte FIFO. |
| 0488h | OUT (04h),A | Field reading also changes controller control state. |
| 0490h–0496h | IN A,(06h), test bit 1, loop, then IN A,(C) | Readiness/address-mark state gates data consumption. |

The accompanying disassembly describes track buffering, address marks and CRC
checks in the guest. This suggests a byte/field-level controller model, not just
a sector-read mailbox. It is a working interpretation to verify against the
controller schematic and the rest of the ROM. Software names such as `WaitRDY`
are disassembler annotations, not proof of the physical signal driving them.

The functional contract below and the newer [timing contract](timing-contract.md)
record the subsequent PIO, write-path and handshake investigation.

The W/M baseline at ports 40h/41h and its DMA cannot validate this interface.

## Functional contract qualified on 2026-10-25

The independent implementation is `model/controller.c`, connected to DAC's
plain `pc1715` CPU/memory model. It never reads or writes guest memory and does
not recognize instruction addresses. The runner observes RAM to collect the
screen and test results; it does not patch ROM, BIOS, or BDOS.

Additional evidence: the locally held *PC-1715-Schaltplaene.pdf*, PDF page 14,
contains the old controller schematic `56-330-0102-1`, drawing
`1.93.300102.3/04`. Q301 A1:1 is the data PIO; Q301 A1:2 is the control PIO.
The U8282 drive-select latch routes its D4 input to /SE0. Thus SCP's `EFh`
selects drive A, even though the ROM uses `EEh`. Requiring both nibbles to be
active would incorrectly pass ROM boot but fail SCP. The drawing variant is
recorded evidence, not a determination of the owner's missing controller.

| Port | Implemented contract | Evidence / qualification |
|---|---|---|
| 00h | Write byte stream; collect MFM sync/FB/payload/CRC while /WE is active | SCP write routine ED2Fh-EDAEh in the pinned image, exercised by SAVE and BDOS workload |
| 01h,03h | Data PIO setup is observed, but no generic PIO implementation | ROM initializes 01h=0Fh (output), 03h=4Fh (input); the latter is **not** bit-control mode |
| 02h | Read mark bytes, ID/data, CRC, then gap bytes | ROM ReadField and SCP interrupt handler EC00h onward |
| 04h | Control-output readback, step/direction, head, mark arming, write gate | ROM 03CBh-03F3h; SCP reads the output latch before modifying bits |
| 05h | Control-PIO A interrupt vector and enable/disable | ROM IM1 index count; SCP IM2 vector 10h |
| 06h | PIO1B mixed status/output register | Bits 0 ready, 1 mark, 5 protect, 6 fault, 7 track zero; output bits 2-4 include format selection |
| 07h | Mode-3 direction follows CFh; mask follows interrupt control; vector/enable | E3h is the **direction mask**, not an interrupt-enable command. SCP 37h,FDh selects mark bit 1; vector 12h, enable 83h |
| 20h-23h | Aliased drive-control latch; /SE0 is bit 4 active low | Mainboard decode and controller latch; ROM EEh and SCP EFh |

In the implemented status image, ready, write-protect, fault, and track-zero
are active low. Mark status bit 1 is high when a field is available. The model
retains output bits 2-4 when composing status. The normal ROM format writes 04h;
SCP also writes 84h. MFM 250 kbit/s is the only qualified format.

The ROM seeks inward eight steps and outward until track zero. It enables
PIO1A interrupts and requires three index events. The model supplies a 300 rpm
index period (491,600 CPU clocks at the current 2.458 MHz profile), prioritizes
index over mark interrupts, and suppresses another interrupt until RETI.
This is functional sequencing, not measured rotational phase or Z80 daisy-chain
qualification. Only the programming sequences used by the pinned ROM/SCP are
implemented; this is not a complete UB855 PIO.

Read fields contain three A1 bytes, FE + CHRN or FB + data, followed by the
big-endian CRC-16/CCITT (polynomial 1021h, seed FFFFh, including all three A1s).
For C=0,H=0,R=1,N=3 the ID CRC is DA4Eh. The ROM checks the received CRC itself.
Raw image order is cylinder/head/sector, with IDs starting at one. The qualified
image is 80 cylinders, two heads, five 1024-byte sectors per track.

Writes start on /WE assertion (04h bit 0 low). A full MFM data field with a valid
CRC updates the model-owned image when the gate closes. Short, malformed and
protected writes do not update it. Formatting, deleted data marks, exotic ID
layouts and other densities are not supported. Unlike a real disk, this model
rejects a bad write CRC atomically; it cannot model partially damaged tracks.

## Reproducible results

`tools/check_classic.py` checks the exact external ROM and disk identities and
the clean, pinned DAC dependency. It compiles the model, uses fresh output
directories, and verifies input hashes after execution. Its nine scenarios are:

1. Cold boot, SCP 0006 prompt, and DIR of the original image; zero writes.
2. SAVE 1 PICO.BIN and DIR; independent CP/M parsing compares all 256 saved
   bytes with the guest's memory.
3. Cold boot of the saved copy and DIR confirms persistence.
4. Load the original project's generated PICOTEST.COM from a disposable image.
   Through stock BDOS/BIOS it creates PICOTEST.TXT, writes twenty 128-byte records,
   closes, resets the disk system, reopens, and compares every byte read back.
   A separate host-side CP/M parser verifies all 2,560 on-image bytes too.
5. Cold boot of that resulting image, then TYPE PICOTEST.TXT through stock SCP.
6. ERA and DIR confirm deletion.
7. Another cold boot confirms deletion persists.
8. SAVE on write-protected media produces the BIOS error prompt and leaves the
   entire image unchanged. This SCP reports a generic BIOS error, not a specific
   write-protection message.
9. With no media present, the bounded run performs no disk-field transfers or
   writes, receives no index interrupts, and never reaches the ROM handoff.

Only scenario 4 adds a new executable to a *copy* of the historical image; all
ROM/OS bytes remain untouched. The fixture reserves a verified free directory
entry and allocation block, and refuses collisions. Its source is
`tools/classic_workload.py`. External binaries and generated media are ignored.

`tests/controller_test.c` independently checks the known ID CRC, data/head
selection, seek limits, full-address I/O aliases, IRQ vectors/enable/ack/RETI,
mode-direction parsing, reset during an incomplete write, absent selection,
unsupported density, and
rejection of short, protected and corrupt-CRC writes.

## Scheduled-byte follow-up and remaining scope

The [timing milestone](timing-contract.md) now adds independent byte clocks,
transaction waits, delay sweeps, missed bytes, CRC failures and mid-transfer
reset recovery while preserving all nine software cases. Its report is separate
from the historical functional report above.

Remaining gaps include continuous track rotation/flux, full PIO modes and nested
interrupt chains, damaged-track writes, other drives/geometries/ROMs/OS versions,
and full motherboard peripherals. Confirm the owner's board revision, X2
orientation, specimen interrupt-chain continuity, electrical levels and reset
behavior before PCB manufacture. The [hardware requirements](../hardware/timing-requirements.md)
identify the next prototype and measurement gates.
