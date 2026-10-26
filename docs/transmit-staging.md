# Bounded transmit staging

The stock BDOS workload previously failed with costs `1,4,1,8,4,8`
(poll, field, read, write, commit, snapshot in microseconds) and 5 ms SD writes.
The [baseline report](../reports/read-ahead-limits.json) records 5,952 transmit
underruns and 48 rejected sector writes; the
[first-loss trace](../reports/read-ahead-after-write8.csv) preserves the failure.
The old path waited for processing before acknowledging each byte, keeping that
work on the CPU's critical path.

## Admission and processing

Firmware copies an accepted transmit byte into one local staging slot and
acknowledges capture before processing it. Processing starts in the same service
iteration, letting the CPU execute between OUT instructions while that work
finishes. The service loop cannot accept another request until processing
returns. This preserves order for data bytes, configuration and gate closure.

Admission still waits for an empty serializer latch. There is no growing queue:
a byte occupies the staging slot while being processed, then the output latch.
A held request is acknowledged once and cannot overwrite the staged data. Data
processing uses core-0-owned controller state and does not take the image lock;
sector commit still takes the lock, rechecks write policy and validates CRC.

The controller clock catches up **after** processing and **before** loading the
serializer latch. Any missed deadlines therefore count as underruns; acknowledging
a byte early cannot erase them. Write-gate closure does not implicitly drain the
latch, postpone the serializer clock or append a missing CRC byte. The original
CRC and sector-length checks remain unchanged.

Reset clears staging, including a reset observed after processing was suspended.
A power-fail/shutdown command or storage error observed during processing drops
the staged byte before publication. Shutdown isolation cancels the partial write;
only a validated sector commit can dirty the image for storage writeback.

`max_service_us` stops at ACK and excludes earlier polling/readiness waits as
well as deferred transmit work. It is not end-to-end bus latency. Deferred work
remains charged by the WRITE cost hook and observable through service deadlines
and underrun counters. This distinction matters when interpreting timing evidence.

## Scope of the timing model

WRITE now represents work after byte capture, rather than arbitrary delay before
GPIO acknowledgement. The bytes are genuinely copied into bounded storage before
ACK, but the injected costs are still hypothetical. Hardware measurements must
separately establish capture/ACK time, processing time, polling gaps and shared-lock
stalls. This is not an RP2350 speed measurement or electrical qualification.

The synthetic media clock, microsecond scheduler and cooperative firmware contexts
retain the limitations described in [CPU cost experiments](cpu-service-costs.md).
The short-reset qualification limit is unchanged: reset must be observed by the
serving core. No guest, FPGA RTL, disk layout or writeback-policy change is needed.

## Reproduction

```sh
python3 tools/check_cpu_costs.py --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm \
  --out local/new-tx-profiles \
  --profile write8=1,4,1,8,4,8 \
  --profile write16=1,4,1,16,4,8 \
  --profile write32=1,4,1,32,4,8

python3 tools/check_classic.py --firmware-cosim --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm \
  --sd-write-delay-us 5000 --firmware-costs-us 1,4,8,8,4,8 \
  --out local/new-tx-stock
```

Named experiments preserve rejected profiles and their first-loss CSV windows;
experiment-runner success means the measurements completed, not that every
profile passed. The stock suite still requires exact persisted data and zero
byte loss; a BIOS retry cannot make a profile pass.


## Results

The [BDOS profile report](../reports/tx-staging-limits.json) uses the same stock
software, SD delay and receive configuration as the baseline:

| Write processing cost | Result | TX underruns | Rejected sectors |
| --- | --- | ---: | ---: |
| 8 µs, before staging | Rejected | 5,952 | 48 |
| 8 µs, after staging | Accepted | 0 | 0 |
| 16 µs, after staging | Accepted | 0 | 0 |
| 32 µs, after staging | Rejected | 36,469 | 48 |

Both accepted profiles perform five sector writes and match the independently
parsed 2,560-byte output file exactly. The 32 µs overload has no watchdog fault:
byte-loss and data-integrity checks catch what a watchdog alone cannot.
Its [bounded first-loss capture](../reports/tx-staging-write32.csv) is retained.
These are sampled profiles, not an exhaustive or monotonic hardware timing bound.

The [combined 8 µs read/write stock suite](../reports/tx-staging-stock.json) and
[zero-cost stock suite](../reports/tx-staging-zero.json) each pass all nine cases
with 5 ms SD writes: boot/DIR, SAVE and cold reopen, BDOS read/write/compare,
read after reboot, deletion and cold verification, write protection and absent
media. Exact persisted contents, firmware/RTL request accounting and zero byte
loss remain required.

## Regression coverage

- [Nine CPU profiles](../reports/tx-staging-public.json), using an original ROM:
  combined 8 µs receive/transmit work, reset during reads, writes and writeback,
  startup faults, overload and unchanged trace-on/trace-off results.
- [153 timing/fault cases](../reports/tx-staging-timing.json), including watchdog
  isolation and recovery. The scripted write bracket remains 26 µs clean / 27 µs
  first sampled failure; stock-CPU gains come from overlapping its execution,
  not from claiming that every consumer can tolerate a larger processing cost.
- [42 storage-fault cases](../reports/tx-staging-faults.json), with persistence and
  fault isolation preserved.
- [263 interrupt cases](../reports/tx-staging-interrupts.json), retaining receive
  behavior and deliberate overload detection.

The service unit test checks capture before processing, stable data under a held
request, backpressure, reset and power-fail cancellation, and honest underrun
accounting during long processing. Paired gate-close cases reject a captured but
unserialized CRC tail and accept the same valid sector after the tail crosses the
serializer. The service tests also pass UBSan. Both read-only and experimental
writeback RP2350 targets build successfully; the portable suite, including
shutdown-policy tests, passes with its existing optional skip.
