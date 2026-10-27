# Remaining desk work and hardware plan

Status reviewed 2026-10-26. Completed desk work does not substitute for hardware
qualification. USB capture/download, controller status/eject, reserve-aware shutdown,
interrupt-chain modelling and firmware service-cost/fault suites are implemented.
The combined controller/analyzer carrier has a checked schematic and both FPGA
personalities; its PCB is partially routed. Physical backup-power circuitry and
qualification of the reset accessory remain planned.

| Area | Completed on the desk | Next unresolved work |
| --- | --- | --- |
| Controller/emulation | Stock ROM/SCP regressions, interrupt arbitration, storage faults, timing-cost and overload tests | Broader OS images; replay measured hardware costs |
| Analyzer | Capture, triggers, PSRAM transport, USB download, decode/compare | Module/USB/capture bench qualification |
| Reset | Standalone software and bounded pulse implementation | Isolated accessory circuit and physical reset test; carrier GP22 is SD CS |
| Shutdown | Safe eject, reserve gating, failure/deadline tests | Optional charger/reserve/supervisor circuit and measured budgets |
| Carrier | Schematic, pin profiles, 74 footprints, power distribution, local bypass routing and ground plane | 145 open connections, host/SD power entry and signal routing, SD drawing review, installation fit |
| Host connector | Original EFS dimensions and four-contact printed test fixture | Qualify modern socket grip, then full connector/adapter design |

The [compact trigger increment](analyzer-triggers.md) now adds configurable
event/address/data matching, rolling history and bounded post-trigger capture.
The [classic controller decoder](analyzer-decoder.md) now adds annotated timelines,
MFM field CRC checks and comparison against emulator reference captures.

## Explicit analyzer mode and remote reset

The [analyzer mode](analyzer-mode.md) now implements passive FPGA capture, local
buffering, USB download and host-side decoding. The combined carrier includes
its additional receivers and address/clock/refresh inputs.
Keep controller-plus-trace as a later extension with a measured bandwidth budget.

Remote CPU reset needs an optional reset-button connection: X1/X2 A20 exposes
`/RESET2`, separate from the CPU reset branch. Include arm-then-reset and bounded,
default-released reset control; do not drive A20 as a substitute for CPU reset.
The linked plan specifies desk acceptance and physical validation gates.

Completed desk increment: [standalone capture RTL and file export](analyzer-prototype.md),
with directed/randomized simulations and iCE40 synthesis; plus [compact cycle
capture and stock-boot verification](cycle-analyzer.md), including a 3.3 MiB filtered
I/O boot trace matching the full capture. The [FPGA–Pico transport and PSRAM
receiver](analyzer-transport.md) now pass workload replay and fault tests.
[USB control/download](analyzer-usb.md) also passes shared-handler/host tests.
The passive adapter and analyzer FPGA fit now complete the reference bench
integration on paper. The [remote-reset software increment](analyzer-reset.md) now provides token-checked
reset and arm-reset commands, a bounded PIO pulse and simulation tests. Assembly,
electrical/USB qualification and the isolated reset accessory remain open.

## 1. Shutdown firmware and simulation

Completed desk increment: [safe eject and reserve-aware shutdown](shutdown.md),
including terminal SAFE/UNSAFE states, worker/journal completion tracking,
read-only/experimental/protected policies, bounded dirty backlog, non-extendable
power-failure deadlines and fault tests. Protected boots start with absent reserve
and cannot silently fall back to experimental writeback.

Remaining integration: assign a qualified early-failure/reserve supervisor,
eject control and safe indicator; supply measured worst-case flush and reserve
budgets. [Controller USB](controller-usb.md) now supplies status and safe eject
through a bounded cross-core mailbox and host CLI. Power-fail/reserve inputs
remain core-0 APIs/SWD controls, without a guest port or USB override.
Physical energy reserve and SD durability remain
bench qualifications; simulation cannot establish either.

## 2. Optional backup-power schematic

- Keep the card functional with the capacitor circuit unpopulated. Retain
  read-only operation as the default. Experimental writeback without backup
  requires an explicit flush before shutdown and provides no guarantee against
  unexpected power loss.
- Provide current-limited slow charging to limit startup inrush, a separate
  full-current discharge path, and reverse-current blocking so the reserve
  cannot power the dead motherboard.
- Define early power-fail detection and safe bus isolation, including behavior
  while reserve is charging or exhausted.
- Target backup of Pico, PSRAM and SD. Investigate leaving the FPGA board outside
  the backed-up domain only if all crossing interfaces can isolate safely.
- Select charger/regulator topology, charge current and capacitor size after
  measuring load, worst-case SD flush latency, dirty backlog and recharge needs.
  If series supercapacitors are selected, include voltage balancing.

Desk acceptance: a reviewed draft circuit, power-domain/interface contract and
measurement plan. No capacitor value, component choice or guaranteed hold-up
time is selected yet. Validate charging, repeated outages and shutdown on the
bench before claiming protected writeback.

## 3. Motherboard interrupt-chain emulation

Completed desk increment: [card–CTC–SIO arbitration](motherboard-interrupts.md),
including simultaneous requests, vector selection, priority/nesting, ownership
on RETI, active-card isolation and reset. Tests include a synthetic Z80 IM2 guest
with the actual Pico1715 controller; CI runs the combined check.

The boot probe now enables this register-level CTC/SIO subset and uses its
receive FIFO for keyboard bytes; see [stock-software qualification](onboard-keyboard.md).
The index/mark collision is reproduced by a ROM-free phase sweep. A bounded
[two-byte firmware receive queue](receive-elasticity.md) passes all nine stock
firmware cases and 132 normal interrupt cases; overload controls still lose and
report bytes. Rotating-track modelling and physical timing remain unqualified.
Full serial waveforms, special receive conditions and X1 expansion remain open;
this does not qualify the physical chain's electrical timing.

## 4. Firmware service-cost qualification

Completed desk increment: [controlled firmware costs](service-costs.md), with
cooperative serving/storage cores, an owned image lock and continuously running
FPGA clocks. The ROM-free suite covers 153 cost, overload, watchdog, reset and
eject cases with concurrent delayed SD writes. It also found and fixed late
mailbox ACKs after request expiry. The stock-ROM/SCP suite passes all nine cases
with delayed writeback after that correction.

The measured brackets belong to the scripted workload, not physical Pico
execution. Bench measurements must supply actual PSRAM/CRC, polling and lock
costs. The [Z80 integration](cpu-service-costs.md) now replays combined hypothetical
costs through stock boot/SAVE/BDOS/reboot workloads, with ROM-free CPU regressions
for reset and overload. [Receive read-ahead](read-ahead.md) now prepares bytes
during idle mailbox time without enlarging receive capacity; bounded first-loss
traces distinguish throughput deficits from lock/interrupt stalls.
[Transmit staging](transmit-staging.md) overlaps byte processing with CPU work,
while gate-close, CRC, reset and power-fail checks retain data-integrity gates.
[Combined stress](combined-stress.md) exercises processing bursts with variable
SD latency and initial index offsets, preserving overload failures and checking
sector contents after a logical-image remount.
[Fault isolation](interrupt-fault-isolation.md) now removes a faulted card from
interrupt arbitration, bypasses its chain position while powered/ready, and
checks reset recovery at interrupt boundaries.
Replaying measured hardware costs remains future work;
a watchdog pass alone does not qualify byte-service timing.

## 5. Broader software compatibility

Expand beyond the current stock-ROM/OS regression set with additional documented
OS/disk variants and sustained mixed read/write workloads. Record exact input
identities, expected results and reproducible runs, including cold reopen and
recovery checks. Keep private ROM and disk contents out of the repository.

## 6. PCB preparation and physical gates

The [combined carrier draft A](../hardware/carrier/README.md) now includes
a checked KiCad schematic/netlist, draft BOM, compatible controller/analyzer FPGA
pin profiles, passive-mode interlock, module power isolation, SD and the PIM724
button/SAFE LED. Desk checks cover both synthesized personalities and negative
connectivity mutations. Complete connector/footprint selection and placement
studies with the [mechanical audit](../hardware/carrier/mechanics.md): the
vendor-numbered switch footprint and Pico/SD pad contracts are now checked.
The PCB places 74 electrical footprints and checks all 557 pads against exported
schematic nets. Eighteen IC bypass capacitors now have short supply traces and
ground vias, alongside module power routes and a bottom ground plane. The current
layout has 379 tracks and 134 vias; geometric DRC is clear with 145 connections still
open (previously 336). X2 remains unplaced; FPGA cables/header mating, SD drawing
exclusions and enclosure fit remain open. Identify the FPGA boards already owned before freezing module
connectors or final routing: the Olimex HX8K remains the reference option, not a
requirement to buy that exact board.

Then complete the [physical gates](../hardware/prototype.md#remaining-gates-before-a-pcb-order):
module bring-up, latency and bus measurements, actual X2 orientation/mechanics
and boot tests, followed by schematic/layout review and ERC/DRC. Order a small
prototype batch and qualify assembled devices before declaring RTM. Desk work
does not close those gates.
