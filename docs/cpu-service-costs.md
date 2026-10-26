# Processing costs with the stock Z80 workload

The firmware/RTL bridge now uses cooperative contexts for **both** firmware cores.
The actual emulated Z80 continues executing, taking interrupts and waiting on the
FPGA mailbox while service work, image-lock contention and SD writes consume
simulated time. No guest instruction or BIOS call is replaced.

This extends the [scripted service-cost experiments](service-costs.md). Their
27/28-microsecond read bracket was specific to a scripted producer/consumer; it
must not be interpreted as a service budget for the stock BIOS.

## Configuration and evidence

The cost order is `poll,field,read,write,commit,snapshot`, in microseconds. The
same six host-only hooks in production service code are used. A zero vector
preserves the earlier zero-cost execution profile. For example:

```sh
python3 tools/check_classic.py --firmware-cosim \
  --dac ../dac-emulation --rom /path/r1715bt.bin --disk /path/r1715.cpm \
  --sd-write-delay-us 5000 --firmware-costs-us 1,4,1,1,4,8 \
  --out local/new-cpu-cost-suite
```

This runs the complete nine-case suite: boot/DIR, SAVE and cold reopen, the BDOS
read/write/compare workload, TYPE after reboot, deletion and cold verification,
write protection and absent media. It still requires exact file contents,
complete SIO keyboard delivery, clean storage drainage, matched firmware/RTL
request counts, zero lost bytes and no watchdog fault.

For named BDOS experiments, including intentionally excessive costs:

```sh
python3 tools/check_cpu_costs.py \
  --dac ../dac-emulation --rom /path/r1715bt.bin --disk /path/r1715.cpm \
  --out local/new-cpu-cost-experiments \
  --profile read4=1,4,4,1,4,8 --profile read8=1,4,8,1,4,8 \
  --profile write8=1,4,1,8,4,8
```

Each profile gets a new process, untouched input workload and exclusive output
directory. Raw stdout/stderr, screen output and pass/fail predicates are retained.
The checker independently parses the 2,560-byte output file. A profile is rejected
when any predicate fails, even if the BIOS recovers and displays success. The
experiment runner exits successfully when all experiments completed; **this does
not mean every profile was accepted**. Process crashes and malformed evidence
are errors, not valid timing failures.

Bridge diagnostics record configured costs, invocation counts, yielded work,
image-lock wait time, latched watchdog episodes and the first fault time. Direct
probe runs can set `PICO1715_COST_POLL_US`, `PICO1715_COST_FIELD_US`,
`PICO1715_COST_READ_US`, `PICO1715_COST_WRITE_US`, `PICO1715_COST_COMMIT_US` and
`PICO1715_COST_SNAPSHOT_US`. The full-suite checker clears inherited experiment
variables and installs only its explicit configuration.

## Recorded results before read-ahead

The following reports precede [receive preparation pipelining](read-ahead.md).
They remain as the historical baseline; the linked page records subsequent results.

Both the [zero-cost baseline](../reports/cpu-cost-zero.json) and the
[combined-cost suite](../reports/cpu-cost-combined.json) pass all nine cases with
5 ms SD writes. The combined vector is `1,4,1,1,4,8` microseconds.

The [BDOS stress experiments](../reports/cpu-cost-limits.json) change just the
listed charge from that combined vector, retaining the same 5 ms SD delay:

| Charge | Accepted | RX overruns | TX underruns | Rejected writes |
| --- | --- | ---: | ---: | ---: |
| Read 4 µs | Yes | 0 | 0 | 0 |
| Read 5 µs | No | 48 | 0 | 0 |
| Read 6 µs | No | 48 | 0 | 0 |
| Read 8 µs | No | 18,733 | 0 | 0 |
| Write 8 µs | No | 0 | 5,952 | 48 |

None of these five profiles trips the mailbox watchdog: byte loss and guest/file
checks detect failures that the watchdog alone cannot catch. The adjacent 4/5 µs
read results apply to this workload and fixed background costs. They are not a
universal latency budget or proof that every smaller cost combination passes.

## Scheduling, reset and end-of-run behavior

Core 0 is pumped on changes of the microsecond clock. A cost hook suspends that
context until its deadline; a completed service iteration starts another step
on a later polling instant. The image lock has one owner. A waiting core yields
instead of recursively entering the other core's service code. Core 1 retains its
existing delayed SD writes and periodic dirty-block scan.

Reset keeps both contexts intact and holds the simulated host reset until the
serving core has observed it. The worker can release a held snapshot lock or
finish an SD wait during this interval. Dirty RAM survives host reset. There is
a bounded reset-service deadline; this is **not qualification of arbitrary short
physical reset pulses**.

The writeback-reset regression exposed a bridge bookkeeping bug: resetting its
ACK edge tracker to low while firmware still held ACK high invented a new reply
on the first reset clock. The tracker now preserves the actual output level until
firmware releases it. This changes simulation bookkeeping, not FPGA behavior.
Reads while the backend is disabled or the mailbox is faulted return FF for the
undriven bus; fault episodes remain recorded and cannot pass qualification.
Bus contention still aborts the simulation.

At the CPU observation limit, the exporter completes any already exposed bus
transaction, stops starting new serving iterations, lets suspended iterations
release their locks, and drains the storage worker. It checks persisted SD
against PSRAM before exporting. Drain work has a bounded deadline and can add
wall-clock time after the CPU limit. It does not silently discard a suspended
stack or reset controller counters to make a report pass.

## Public regression

`tests/cpu_cost_smoke.py` generates an original 2 KiB ROM. Its Z80 program reads
ID/data fields, writes a CRC-protected sector, then reads more fields while the
worker journals the write. The host verifies exact persisted bytes. Seven cases
cover zero costs, combined costs, read-ahead costs, reset during reading, reset during writeback,
a 100-microsecond read overload and slow startup/polling. All cost sites and
actual lock contention must be observed in the combined case; its CPU WAIT count
must exceed the zero-cost case. Overload cases must report watchdog faults.

CI runs this test against the compiled CPU/firmware/RTL bridge, with no historical
ROMs or disk images. The [current public report](../reports/read-ahead-public.json) records
its source hashes and case counters. Reproduce the build and qualification with:

```sh
python3 tools/check_cpu_cost_smoke.py --dac ../dac-emulation \
  --out local/new-cpu-cost-smoke
```

## Limits and next optimization target

Costs remain **hypothetical aggregate delays**, not measured RP2350 instruction
times. The six charges are not interchangeable or additive latency budgets.
The bridge retains its microsecond scheduler, deferred-I/O abstraction, idle-clock
optimization and synthetic field/index scheduling. Real caches, QMI/SPI signals,
CPU half-cycle WAIT sampling and physical clock-domain behavior remain outside
this simulation.

The subsequent [read-ahead change](read-ahead.md) targets the per-byte serving path: the stock BIOS can
lose bytes at injected read/write costs far below the scripted-bus thresholds.
Measure polling gaps, GPIO service and shared-lock time before deciding which
code to optimize. Field construction and worker snapshots also contribute to the
combined workload; these experiments do not prove they are harmless at other
phases, sizes or cache conditions.
