# Receive preparation outside the CPU read wait

The first-loss trace identifies a sustained receive-rate deficit in the stock
SCP BIOS at the `1,4,5,1,4,8` cost vector. In the 256-microsecond window before
the first overrun, reads remove bytes every 33 microseconds while media supplies
a byte every 32 microseconds. At simulated time 9,051,026 microseconds the next
field byte arrives with both receive slots occupied. The CPU is at EDEB, reading
port 02; the image lock is free, and interrupt ownership remains unchanged
throughout the window. The seven accumulated microseconds of lock waiting occur
earlier, not at this loss.

The [baseline report](../reports/read-ahead-before.json) and bounded traces for
[read5](../reports/read-ahead-before-read5.csv) and
[write8](../reports/read-ahead-before-write8.csv) preserve the rejected results. Baseline service/controller sources match commit
`89b26ea`; the additional host instrumentation only observes execution.
Increasing the queue depth would postpone this sustained deficit rather than
remove it.

## Change

Firmware now prepares one queued receive byte after releasing an idle mailbox.
The preparation cost runs while the CPU can execute between I/O requests. A read
of a prepared byte consumes it without repeating preparation. If the slot is
empty, the normal demand path still does the work before replying.

The prepared slot counts toward the **same two-byte capacity**. Preparation does
not acknowledge a CPU read, increment the byte count, clear the read-pending
state or change interrupt ownership. Consumption records age from the original
arrival, including time spent prepared. Reset, acquisition cancellation and new
field acquisition discard prepared data together with the receive queue. No
FPGA, guest code, disk format or writeback policy changes are required.
After a withdrawn request, speculative preparation stays disabled until host
reset. This prevents background work on a faulted link from delaying recovery;
the timing regression checks watchdog isolation and reset recovery.

This is specifically a receive-preparation pipeline. The injected READ cost now
covers preparation on either path; it must not be interpreted as an arbitrary
GPIO/ACK delay that can always be moved before a request. Actual hardware must
establish how much work is preparable and the residual mailbox response cost.

## Bounded diagnostic capture

`PICO1715_LOSS_TRACE=/new/path.csv` enables host-only sampling. The path must not
already exist. The bridge records up to 256 microsecond service samples ending
at the first observed RX overrun or TX underrun and up to 64 following samples.
A run without byte loss leaves only the CSV header. The trace captures CPU PC,
I/O address and direction, mailbox GPIOs, receive occupancy (`rx + prepared`), field position,
interrupt state, lock owner, remaining service delay and error counters.

This is a scheduler-level diagnostic, not an electrical logic-analyzer trace.
It observes losses when service next runs; it does not reconstruct every FPGA
clock edge. Lock owner 2 means unlocked; 0 and 1 identify the serving and storage
cores. Baseline traces predate the prepared slot and store all occupancy in `rx`.
PC/address values are decimal in the CSV. Forced service calls during reset may share a microsecond timestamp. A stale address with active=0
is the previous transaction, not a current CPU I/O request.

The named experiment runner writes `first-loss.csv` for every profile alongside
stdout, stderr, screen, disk and JSON evidence. Source hashes in the baseline
report identify the pre-change implementation, not the current firmware.


## Measured simulation results

These results precede [transmit staging](transmit-staging.md), which addresses
the write-side limit while preserving the receive pipeline.

The [post-change BDOS profiles](../reports/read-ahead-limits.json) retain the same
background vector `1,4,R,1,4,8`, 5 ms SD writes, stock software and two-byte
capacity. Every accepted case requires exact persisted contents and zero lost
bytes, independently of whether the guest prints success.

| Profile | Before | After |
| --- | --- | --- |
| Read preparation 5 µs | 48 RX overruns; BIOS error | Pass, zero RX/TX faults |
| Read preparation 8 µs | 18,733 RX overruns | Pass, all nine stock cases |
| Read preparation 16 µs | Not sampled | Pass, zero RX/TX faults |
| Read preparation 24 µs | Not sampled | Pass, zero RX/TX faults |
| Read preparation 32 µs | Not sampled | Rejected; byte loss prevents boot handoff |
| Write preparation 8 µs, read 1 µs | 5,952 TX underruns; 48 rejected writes | Same failure counters |

The [32 µs overload report](../reports/read-ahead-overload.json) and
[first-loss window](../reports/read-ahead-after-read32.csv) retain the failure.
The [write-side window](../reports/read-ahead-after-write8.csv) shows the remaining
separate producer deadline. These are sampled profiles, not a proof of a global
monotonic latency bound. The 8 µs pre-change numbers are in the earlier
[stock cost report](../reports/cpu-cost-limits.json).

Reproduce the accepted and rejected BDOS experiments in a new directory:

```sh
python3 tools/check_cpu_costs.py --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm \
  --out local/new-read-ahead \
  --profile read5=1,4,5,1,4,8 --profile read16=1,4,16,1,4,8 \
  --profile read24=1,4,24,1,4,8 --profile read32=1,4,32,1,4,8 \
  --profile write8=1,4,1,8,4,8
```

The [8 µs read-preparation stock suite](../reports/read-ahead-stock.json) and
[zero-cost stock suite](../reports/read-ahead-zero.json) each pass all nine cases,
including SAVE/cold reopen, BDOS exact-content checks, read after reboot,
deletion/cold verification, write protection and absent media. Both retain
5 ms SD writes and require zero byte loss. Reproduce the higher-cost suite with:

```sh
python3 tools/check_classic.py --firmware-cosim --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm \
  --sd-write-delay-us 5000 --firmware-costs-us 1,4,8,1,4,8 \
  --out local/new-read-ahead-stock
```

## Regression coverage

- [Seven CPU cases](../reports/read-ahead-public.json): generated ROM, all cost
  sites, higher read cost, writeback, resets and watchdog overload. A repeated
  combined run checks that enabling capture leaves counters, RAM, disk and
  screen identical to an untraced run.
- [153 timing/fault cases](../reports/read-ahead-timing.json): the scripted read
  bracket improves from 27/28 to 29/30 microseconds; this remains distinct from
  the stock BIOS workload. Watchdog isolation and recovery remain mandatory.
- [263 interrupt cases](../reports/read-ahead-interrupts.json): all 132 bounded
  production cases remain clean, with the same two-byte capacity; deliberate
  prolonged-interrupt and slow-consumer cases still lose data.
- [42 storage-fault cases](../reports/read-ahead-faults.json): persistence and
  failure isolation remain intact.

Controller tests also check that preparation is idempotent, consumes existing
capacity, preserves arrival age, counts bytes only at CPU reads, and clears on
cancellation/reset. The service unit test checks preparation inhibition after
request withdrawal. Both run under UBSan. Read-only and experimental-writeback
RP2350 firmware targets compile successfully.
