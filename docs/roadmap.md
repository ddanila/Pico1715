# Remaining desk work and hardware plan

This is planned work, not implemented functionality or hardware qualification.
The next desk milestone is shutdown handling and its simulation, together with
defining the signals needed by an optional backup-power circuit.

## Explicit analyzer mode and remote reset

Add the [analyzer mode](analyzer-mode.md) as a first-class board feature: passive
FPGA capture, local buffering, USB download and host-side bus decoding. Plan its
additional receivers and full address/clock/refresh inputs before PCB freeze.
Keep controller-plus-trace as a later extension with a measured bandwidth budget.

Remote CPU reset needs an optional reset-button connection: X1/X2 A20 exposes
`/RESET2`, separate from the CPU reset branch. Include arm-then-reset and bounded,
default-released reset control; do not drive A20 as a substitute for CPU reset.
The linked plan specifies desk acceptance and physical validation gates.

## 1. Shutdown firmware and simulation

- Define an explicit flush/safe-eject command and a safe-to-power-off indication.
  Both must be useful with or without backup power.
- Model backup absent, charging, ready and insufficient-reserve/failure states.
  Enable protected writeback only with sufficient charged reserve; define how
  reserve loss stops new writes without silently entering an unsafe mode.
- On early power failure, stop accepting writes, isolate the host bus, drain
  dirty data and the journal, and wait for SD completion before reporting safe.
- Bound the dirty backlog against the measured available flush budget. The
  present RAM acknowledgement precedes SD persistence; a capacitor alone does
  not make arbitrary queued writes durable.
- Extend simulation with outages during each write/journal phase, insufficient
  reserve, repeated outages before recharge, and backup absent. Check that the
  safe indication cannot precede completion and document recovery limits.

Desk acceptance: an explicit state/handshake contract, implemented shutdown
handling, and reproducible fault tests. Physical energy reserve and SD durability
remain bench qualifications; simulation cannot establish either.

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

## 3. Full motherboard interrupt-chain emulation

Exercise the card alongside CTC/SIO interrupt sources, including priority,
interrupt acknowledgement, in-service/nested behavior and RETI propagation.
Acceptance requires regression cases demonstrating the expected ordering and
release behavior; card-only IRQ tests do not close this milestone.

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
