# Rev A prototype order gates

Accepted configuration: five bare hand-assembled carrier boards for bring-up;
HX8K and Pico Plus 2; four-layer candidate; separate replaceable EFS58 adapter
and short keyed harness; optional reserve daughterboard. No PCB purchase or
production qualification is implied. Obtain a delivered Estonia quote after the
manufacturing package is reviewable. Preserve the existing two-layer baseline.

| Gate | Required evidence | Current state |
| --- | --- | --- |
| Combined mode | Real firmware/RTL, boot and verified writes, overflow and compatibility, FPGA fit | Desk checks pass, including classic guest write/cold verify; see combined-mode.md |
| Interface freeze | Single checked pin/direction/domain contract, reserve detection surviving FPGA loss | SP/CE GP32/33/36 allocated and supervisor desk-tested; Rev A J6/J7 electrical ECO applied; analog threshold review still open |
| Parts and mechanics | Exact BOM/mates, documented SD geometry, keyed host harness, module access | Open: final SD geometry approval and host-header mating review; Würth replacement drawing recovered |
| Schematic | Complete connectivity, isolation/power truth tables, hand-assembly review | Rev A ECO applied, fresh ERC zero; independent interlock/net-parity tests pass |
| Four-layer layout | Manufacturer stack-up, all connections routed, ERC/DRC zero opens, return-path review | Separate four-layer candidate routed except 12 held SD opens; zero DRC violations. Stack-up confirmation and final review open |
| Manufacturing package | Independently inspected Gerbers/drills, BOM, assembly/cables, hashes and test records | Hashed engineering review bundle implemented; fabrication exports blocked by previous gates |
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

## Implemented Rev A desk checkpoint

The new source is `hardware/carrier-reva`, preserving the two-layer baseline.
J6 carries the checked 58-contact assignment on a keyed 60-pin candidate header;
J7 separates ground, raw module power and backed Pico supply. The optional
reserve board remains outside the initial order. See its README for cable and
power precautions and the current exact part candidates.

All new non-SD connections are routed on the outer layers. The replacement
F_CLK copper is about 170 mm (formerly 205 mm); F_WR_N is about 183 mm
(formerly 260 mm). These routes use more vias: 11 and 10 respectively.
Fifty-two additional GND stitching vias give every supplemental signal via a
GND transition within 4 mm in the geometric check. This is a return-path
improvement, not timing/impedance or physical signal-integrity qualification.
`reports/carrier-reva-routing.json` includes adjacent-plane sampling and the
remaining full-board review flags. Manufacturing sign-off must consider the
via-count tradeoff, plane voids and the existing baseline signal transitions.

`make test-carrier-reva` checks exact copper preservation/additions, net parity,
harness mapping, reserve rails and mutation failures. `make test-carrier-reva-cad`
adds fresh KiCad ERC/DRC; its explicit review mode reports rather than hides
held opens. `tools/package_carrier_reva.py` produces a freshly checked review
ZIP with hashes and cable mapping, expressly not an orderable fabrication ZIP.

Next: finish SD footprint approval and routing; verify the exact host-header,
mate and cable mechanics; confirm the four-layer stack-up; review final return
paths and assembly access; independently inspect Gerbers/drills and freeze a
clean-source manufacturing manifest. Only then obtain the delivered Estonia
quote for five bare boards. No quote, purchase or physical qualification has
been claimed at this checkpoint.
