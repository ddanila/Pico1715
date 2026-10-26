# Interrupt isolation on mailbox fault

Combined stress exposed a mismatch: the controller top gated data drive on a
mailbox fault but left interrupt arbitration active. A pending interrupt could
therefore ask the CPU for an acknowledgement with no driven vector. The earlier
bridge fix allowed this failed state to be measured; this change fixes the RTL
source of those requests.

## Contract

A latched mailbox fault holds the interrupt frontend in reset. The card releases
`/INT`, host data drive and `/WAIT`, withdraws the mailbox request, and clears
interrupt ownership, acknowledgement tracking and partial ED/RETI decoding.
While the board remains powered and ready, IEO follows IEI so the faulted card
cannot block downstream interrupt devices. ACK/RETI notification toggles stop
changing; they are not reset by the fault, avoiding an artificial notification.

The fault remains latched despite late backend replies or new index/mark edges.
Host/backend reset clears the fault and notification state. The backend must
observe reset and release its ACK before normal traffic resumes. Power loss and
backend-not-ready retain their existing gating, including IEO low; this change
is not an unpowered electrical bypass.

An IACK already sampled by the CPU cannot be undone. If a fault interrupts a
cycle, the card releases its outputs without inventing a successful response.
Chain bypass permits downstream arbitration but does not guarantee that the
current guest program can continue. Reset is the supported recovery boundary.
The simulator's counted FF response for a fault-time undriven IACK remains as a
diagnostic fallback for boundary cases, rather than asserting such a race is
physically impossible.

## Directed regression

`make test-pico-top` now runs 302 checks. Eight fault scenarios combine mailbox
withdrawal or watchdog expiry with a pending interrupt, IACK entry, in-service
ownership, or a partial RETI prefix. Withdrawal into IACK exercises the same
clock boundary as fault assertion. The watchdog cases keep a normal I/O request
active until expiry. No internal fault or interrupt state is forced.

Each scenario verifies released outputs, chain propagation for both IEI values,
frozen notification toggles, rejection of late ACK/new interrupt edges and RETI,
and reset recovery through a real mailbox write, vector acknowledge and RETI.
The new test failed against the previous RTL at “fault releases bus and interrupt”
and passes with the correction. Existing frontend, IRQ and bench-fixture tests
and RTL lint also pass.

The ROM-free CPU overload regression now requires a watchdog fault and **zero**
fault-time IACKs, while retaining sector-integrity and clean-remount assertions.
Its prior report recorded two such acknowledgements. Intentional overloads
remain failures; no byte-loss or persistence acceptance gate is relaxed.

## Evidence

Both full stock-ROM stress suites pass: [early](../reports/irq-isolation-early.json)
and [late](../reports/irq-isolation-late.json), **18/18 cases**, with zero byte loss,
watchdog faults or fault-time IACKs. They cover boot, SAVE, BDOS writes, exact
contents after cold reboot, persistent deletion, write protection and absent media.

- [Directed RTL regression](../reports/irq-isolation-rtl.json): 302 integrated
  checks, plus existing IRQ/frontend/bench-fixture suites and lint.

- [Public CPU regression](../reports/irq-isolation-public.json): 14 cases,
  including one watchdog fault and zero fault-time IACKs in the IRQ overload.
- [Interrupt sweep](../reports/irq-isolation-interrupts.json): 263 cases,
  retaining 132 clean production cases and the two expected overload controls.
- [Service timing](../reports/irq-isolation-timing.json): 153 cases with existing
  acceptance limits and negative controls preserved.
- [Storage faults](../reports/irq-isolation-faults.json): 42 cases.
- [Stock overload](../reports/irq-isolation-overload.json): still rejected for
  guest/content/write/byte/watchdog checks, with zero fault-time IACKs. Its
  [first-loss capture](../reports/irq-isolation-overload.csv) remains preserved.
- [HX8K fit](../reports/irq-isolation-fit.json): synthesis, placement, routing and
  packing pass; the frontend clock achieves 148.26 MHz against the report's
  100 MHz constraint. This is internal timing, not a pad-to-pad bus certificate.

`make test` passes 52 tests with one optional skip; storage and firmware-service
unit suites also pass. Source hashes in the linked reports identify the tested
implementation. Earlier combined-stress reports remain historical evidence.

## Reproduce

```sh
make test-pico-top test-irq test-frontend test-bench-fixture lint-bench-fixture
python3 tools/check_cpu_cost_smoke.py --dac ../dac-emulation --out local/new-isolation-public
python3 tools/check_firmware_interrupts.py --out local/new-isolation-interrupts
python3 tools/check_firmware_timing.py --out local/new-isolation-timing
python3 tools/check_firmware_faults.py --out local/new-isolation-faults
```

Use the two stock-suite commands in [combined stress](combined-stress.md) with
new output directories to repeat the early/late profiles. These checks use
simulation and routed internal timing; external bus timing, reset propagation,
translator behavior and chain electrical characteristics still need bench tests.
