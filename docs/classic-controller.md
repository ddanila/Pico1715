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

Next: identify all PIO initialization words, status-bit producers, interrupt
conditions and field/CRC data sequences. Establish whether repeated reads stall
through /WAIT or depend on handshake timing. Check OS writes independently:
successful boot-ROM reads would not qualify formatting or disk writes.

The W/M baseline at ports 40h/41h and its DMA cannot validate this interface.
