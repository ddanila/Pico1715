# Rev A prototype order gates

Accepted configuration: five bare hand-assembled carrier boards for bring-up;
HX8K and Pico Plus 2; four-layer candidate; separate replaceable EFS58 adapter
and short keyed harness; optional reserve daughterboard. No PCB purchase or
production qualification is implied. Obtain a delivered Estonia quote after the
manufacturing package is reviewable. Preserve the existing two-layer baseline.

| Gate | Required evidence | Current state |
| --- | --- | --- |
| Combined mode | Real firmware/RTL, boot and verified writes, overflow and compatibility, FPGA fit | Desk checks pass, including classic guest write/cold verify; see combined-mode.md |
| Interface freeze | Single checked pin/direction/domain contract, reserve detection surviving FPGA loss | SP/CE GP32/33/36 allocated and supervisor desk-tested; connector/power ECO and analog threshold review still open |
| Parts and mechanics | Exact BOM/mates, documented SD geometry, keyed host harness, module access | Open: SD engineering evidence, host harness and daughterboard connectors |
| Schematic | Complete connectivity, isolation/power truth tables, hand-assembly review | Existing baseline only; Rev A ECO not applied |
| Four-layer layout | Manufacturer stack-up, all connections routed, ERC/DRC zero opens, return-path review | Not started; two-layer review layout remains canonical |
| Manufacturing package | Independently inspected Gerbers/drills, BOM, assembly/cables, hashes and test records | Blocked by previous gates |
| Quote/order | Same released files/stack-up, quantity five, shipping/taxes, reviewed delivered price | Not requested |
| Physical qualification | Current-limited bring-up, isolation, connector fit, passive host observation, boot/write/capture | Requires ordered parts/boards and instruments |

Do not label the carrier fabrication-ready merely because placed components
have no airwires: the baseline has 12 held SD connections and an unplaced X2.
The separate adapter removes connector mating from carrier-only bench bring-up,
not from the eventual host-insertion gate. No direct RESET2 CPU-reset shortcut.
Reserve omission must preserve normal operation without implying protected
writeback; measured energy and journal timing remain mandatory for that claim.

The first board is assembled and validated before populating the rest. Record
faults as Rev B changes. Broader emulator/application work is not an order gate
unless it exposes a hardware interface defect.
