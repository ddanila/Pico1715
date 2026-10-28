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
| Parts and mechanics | Exact BOM/mates, documented SD geometry, keyed host harness, module access | SD and J6/J7 drawing geometry checked; harness mating-view drawing added; physical fit untested |
| Schematic | Complete connectivity, isolation/power truth tables, hand-assembly review | Rev A ECO applied, fresh ERC zero; independent interlock/net-parity tests pass |
| Four-layer layout | Manufacturer stack-up, all connections routed, ERC/DRC zero opens, return-path review | All connections routed, fresh ERC/DRC zero violations and opens. Seven return-via outliers and final review remain |
| Manufacturing package | Independently inspected Gerbers/drills, BOM, assembly/cables, hashes and test records | Hashed review bundle and independent Gerber/drill export inspection implemented; prototype release gate fails closed |
| Quote/order | Same released files/stack-up, quantity five, shipping/taxes, reviewed delivered price | Pending final release and address-dependent delivery quote |
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

All SD and host/reserve connections are now routed. Würth 693071010811 replaces
the held Hirose footprint only in Rev A. Exact J6 holes/body and J7 geometry are
independently checked against manufacturer drawings. The harness drawing shows
both top and mating-face views; every conductor still needs continuity testing.

The clock/write paths remain 169.863/183.176 mm with 11/10 vias. The whole-board
return review now includes all 391 signal vias. An additional 126 ground vias
were added during this pass (178 supplemental ground vias in total). Seven
signal vias remain beyond the 4 mm target; their coordinates are recorded in
`hardware/carrier-reva/release-review.json`. A denser candidate search was tried;
no clearance-safe 0.6/0.3 mm stitching position was found for those locations.
A further 0.1 mm grid reroute trial for F_A3, restricted to vias within 4 mm
of existing GND transitions, exhausted 4,625,688 states without a path while
other nets stayed fixed. Closing these exceptions therefore requires a broader
local routing change; no candidate from that failed trial was adopted. Inner planes now extend
to 0.5 mm from the outline, correcting long ground-reference gaps under F_A0/F_A5.

Fresh ERC/DRC report zero violations and zero opens. Drawing geometry mutation
checks, baseline electrical/interlock regression and release-gate tests are
available through the Makefile. `tools/export_carrier_reva.py` exports candidate
Gerbers and separate drills, independently parses/renders them with gerbv and
checks the 60 header holes, three reserve holes and four mounting holes.
An initial overview inspection is recorded; detailed export/assembly review
remains open. Neither candidate exports nor an engineering ZIP are order approval.

`tools/package_carrier_reva.py --mode fabrication` requires a clean source tree,
source-matched reviews, zero opens/violations and the return-path/routing budgets.
It currently refuses release. Ordinary review mode includes local footprints,
drawing evidence, source hashes and the harness mapping. The four-layer stack-up
matches the manufacturer's catalog; actual order acceptance and finished-hole
tolerance still require supplier confirmation. See `manufacturing.md` for the
five-board quote specification. No purchase or physical qualification is claimed.

Remaining desk work is local return-path rerouting, detailed plane/assembly and
fabrication-export review, and the final delivered quote. EFS58 physical fit,
current-limited power/isolation checks, passive host capture, boot/write tests and
reserve-energy measurement remain later hardware qualification stages.
