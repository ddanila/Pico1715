# Remaining desk work and hardware plan

The sections below distinguish completed desk increments from remaining plans;
none substitutes for hardware qualification. USB control/download is now implemented and tested at the protocol seam.
The [passive analyzer adapter](../hardware/analyzer-interface/README.md) now has
a checked receiver schematic, pin binding and routed timing. Bench assembly and
physical qualification are next; combined controller/analyzer hardware and PCB
layout remain future work. The [shutdown firmware contract](shutdown.md) now has desk-tested safe eject and
reserve gating. Physical backup-power signals and circuitry remain planned.

The [compact trigger increment](analyzer-triggers.md) now adds configurable
event/address/data matching, rolling history and bounded post-trigger capture.
The [classic controller decoder](analyzer-decoder.md) now adds annotated timelines,
MFM field CRC checks and comparison against emulator reference captures.

## Explicit analyzer mode and remote reset

Add the [analyzer mode](analyzer-mode.md) as a first-class board feature: passive
FPGA capture, local buffering, USB download and host-side bus decoding. Plan its
additional receivers and full address/clock/refresh inputs before PCB freeze.
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
budgets. Current controls are core-0 APIs and an SWD command mailbox, not a guest
port or USB user interface. Physical energy reserve and SD durability remain
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
The firmware/RTL run exposes an index/mark collision and one receive overrun;
clean firmware qualification remains open. Reproduce it without private ROMs
and sweep interrupt/acquisition phase before changing controller timing.
Full serial waveforms, special receive conditions and X1 expansion remain open;
this does not qualify the physical chain's electrical timing.

## 4. Broader software compatibility

Expand beyond the current stock-ROM/OS regression set with additional documented
OS/disk variants and sustained mixed read/write workloads. Record exact input
identities, expected results and reproducible runs, including cold reopen and
recovery checks. Keep private ROM and disk contents out of the repository.

## 5. PCB preparation and physical gates

Prepare schematics, connector definitions, footprint checks and placement studies
at the desk. Identify the FPGA boards already owned before freezing module
connectors or final routing: the Olimex HX8K remains the reference option, not a
requirement to buy that exact board.

Then complete the [physical gates](../hardware/prototype.md#remaining-gates-before-a-pcb-order):
module bring-up, latency and bus measurements, actual X2 orientation/mechanics
and boot tests, followed by schematic/layout review and ERC/DRC. Order a small
prototype batch and qualify assembled devices before declaring RTM. Desk work
does not close those gates.
