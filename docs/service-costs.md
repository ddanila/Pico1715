# Firmware service-cost experiments

The [ROM-free timing harness](../tests/firmware_timing.cpp) charges controlled
wall-clock costs to production firmware while the FPGA continues clocking. It
also runs the storage worker with delayed SD writes and an owned image lock.
This exposes throughput failures, watchdog expiry and stale-response races that
zero-cost host function calls cannot reveal.

These are **injected costs, not measured Pico execution times**. The host bus is
scripted, not a Z80 instruction stream. Results are workload-specific brackets
for bench experiments, not a certified service budget or a replacement for the
stock-software tests.

## Scheduler and cost sites

Two cooperative contexts run the actual serving and storage loops. A suspended
context retains its stack and resumes after its charged time. Every microsecond,
the scheduler samples GPIO, runs eligible cores and advances 100 FPGA input-clock
edges. Normal service iterations have a minimum one-microsecond polling interval;
the worker waits 100 microseconds between scans. Core 0 runs first when both are
eligible. The image lock has one owner: the other core waits while wall time and
RTL continue. There are no recursively re-entered service calls.

Host-only hooks in `platform.h` and `host_hal.*` charge these sites:

| Site | Charged work | Location |
| --- | --- | --- |
| Poll | Base service-loop execution | Before command/reset/tick processing |
| Field build | PSRAM field copy and CRC preparation | Before an arming control write, under the image lock |
| Read | Receive service work | Before consuming port 02h |
| Write | Transmit service work | Before supplying port 00h, under the image lock |
| Commit | CRC verification and sector-copy work | Before closing a write gate, under the image lock |
| Snapshot | Copying a 512-byte block for writeback | While the worker holds the image lock |

The hook is an aggregate charge before the operation's effects. It does not
simulate individual memory accesses, actual CRC instruction counts or interrupt
preemption inside those operations. The controller keeps its real service-loop
behavior: it catches up to elapsed time on its next tick. No second thread calls
controller ticks behind the serving core's back. In particular, these tests are
not a continuously clocked physical floppy data separator.

Pico builds compile the work hooks to no-ops and use the real SDK critical
section. Existing host fixtures leave hooks null and retain their prior behavior.
The measurement harness alone installs the scheduler and lock callbacks.

Each sweep first writes a valid sector through the mailbox. It then enables the
worker with **5 ms per SD write operation** and varies one cost at a time. Read
workloads compare an ID field and a full 1,030-byte data field; write workloads
submit a distinct sector payload and require successful commit and matching RAM.
The worker is doing real journal operations, not merely incrementing a counter.
Costs are not additive budgets, and this sweep does not cover every combination
of costs, cache misses, interrupt phase or storage latency.

## Observed limits

[Report and source hashes](../reports/service-costs.json), 153 cases:

| Added cost | Last clean sample before failure | First failing sample |
| --- | ---: | ---: |
| Read service | 27 µs | 28 µs |
| Base polling | 15 µs | 16 µs |
| Write service | 26 µs | 27 µs |
| Field construction | 80 µs | 96 µs |
| Worker snapshot / lock hold | 64 µs | 80 µs |
| Sector commit | 80 µs | 96 µs |

The first three use one-microsecond increments. The latter three are coarser
brackets, not exact boundaries. Receive/transmit failures can occur before the
81.92-microsecond FPGA watchdog. A passing watchdog check therefore says nothing
by itself about preserving disk bytes. Each report retains byte-loss counters,
content comparisons, successful request-to-WAIT-release latency, fault release
time, lock waits, SD waits and cost-site invocation counts.

A clean point requires correct contents, completed mailbox transactions, no
RX/TX fault and no storage error. The negative points are expected to fail these
criteria; the regression passes only if it observes both the required clean
envelope and overload behavior. The public CI job runs the whole sweep.

## Late-response correction

The new held-read test failed before the firmware fix: a 100-microsecond service
stall outlived the FPGA watchdog, but firmware still raised ACK when it resumed.
The FPGA had already released WAIT and disabled host data, so this was a stale
mailbox reply, not a valid transaction completion.

Firmware now rechecks request presence and host reset after acquiring the image
lock, after the injected work before consuming data/changing controller state,
and after controller work before driving read data or ACK. A withdrawn request
releases the response pins and receives no new ACK. Tests verify:

- A delayed read expires around 82 µs and cannot emit a late ACK.
- A delayed sector commit is abandoned before the mutation in the injected-cost
  model; the earlier committed sector remains unchanged.
- A 128-microsecond worker lock hold also expires the mailbox without a late reply.
- Reset clears the latched fault and permits a new ID-field read.
- Reset held during the delayed read cancels stale service and preserves dirty
  data; subsequent selection and field reads work again.
- Eject during a contended worker snapshot isolates the bus, drains all eight
  journal write operations, and reports SAFE only with persisted bytes matching
  RAM and no dirty/in-flight work.

This does not make request withdrawal atomic with controller work or GPIO
publication. Work already committed before a reset cannot be rolled back by the
final check. The regression holds reset through the delayed operation (120 µs
for a 100 µs charge); arbitrary short pulses while the serving core is stalled
remain unqualified. Physical asynchronous sampling and output-enable timing
still require measurements.

## Reproduce and follow-up

```sh
python3 tools/check_firmware_timing.py --out local/new-service-costs
```

No private ROM, OS image or hardware is needed. The checker creates an exclusive
output directory, builds the production firmware/RTL harness, verifies the case
matrix and source hashes, and retains raw stdout/stderr plus a JSON report.

The historical [stock software regression](../reports/service-cost-stock.json) separately
runs the real Z80 ROM/SCP workload with 5 ms SD-write delays and zero injected
service costs. It validates compatibility of the request-liveness correction;
it does not establish the scripted cost boundaries for that CPU workload.
The subsequent [Z80 cost integration](cpu-service-costs.md) now runs combined
nonzero costs through the stock software and records stricter limits.
Existing [storage faults](../reports/service-cost-storage.json) and
[interrupt phase tests](../reports/service-cost-interrupts.json) remain passing.
Both read-only and experimental-writeback Pico firmware builds compile.

For bench qualification, measure complete request-to-ACK time, service-loop gaps,
PSRAM/CRC durations and image-lock hold times under concurrent SD writes. Replay
those measured costs, including combinations, through this harness and a CPU
workload before choosing a timing margin. ARM instruction execution, real cache
behavior, electrical CDC and SD durability remain outside this report.
