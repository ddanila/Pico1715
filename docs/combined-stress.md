# Combined burst, storage and interrupt-phase stress

The CPU/firmware/RTL co-simulation can now inject deterministic bursts on top of
its six processing costs, cycle SD block-write latencies, and vary the initial
index-interrupt phase. This tests sampled combinations of processing and storage
stalls while the stock CPU continues executing. It is not an exhaustive worst-case
proof, an ARM execution-time measurement or physical timing qualification.

## Reproducible schedules

Pass `--stress-profile path.json` to `check_classic.py --firmware-cosim` or
`check_cpu_costs.py`. Unknown fields, malformed vectors and out-of-range values
are rejected. With no profile, bursts are disabled and previous fixed-cost
behavior is retained.

For each cost kind independently, zero-based invocation `n` receives the extra
charge when `(n + phase) % period < width`. Charges add to the existing base
cost; they never replace it. Consecutive invocations inside a burst may be
separated in wall-clock time. The schedule counters persist through host reset
within one process and restart for each new case. There is no random seed.

`sd_delays_us` cycles once per SD block-write operation, including journal writes.
A nonempty sequence overrides the fixed SD delay. The existing report's
`sd_write_delay_us`/`Storage delay_us` therefore describes the fallback, while
`stress.sd_min_us`, `sd_max_us` and `sd_calls` describe the exercised schedule.
SD reads and startup remain outside this write-latency injection.

`index_phase_us` offsets the initial 200 ms index deadline after each host reset.
Later index events follow the existing controller model, including its service
quantization and suppression of index events while in service. This does not
phase-lock every mark or emulate rotating tracks.

| Profile | Burst period / width / phase | Extra costs, µs | SD writes, µs | Index offset |
| --- | --- | --- | --- | --- |
| [Early](../tests/stress/combined.json) | 257 / 2 / 0 | 1,2,4,4,4,4 | 200,5000,20000 | −64 µs |
| [Late](../tests/stress/combined-late.json) | 257 / 2 / 127 | 1,2,4,4,4,4 | 20000,200,5000 | +64 µs |
| [Overload](../tests/stress/overload.json) | 17 / 2 / 0 | 1,2,0,80,4,4 | 200,5000,20000 | 0 µs |

Costs are ordered poll, field, read preparation, write processing, commit,
snapshot. The stock runs use base costs `1,4,8,8,4,8`. The early/late maxima are
therefore `2,6,12,12,8,12` µs. Those maxima are not an additive latency budget or
a guarantee that every relative phase is clean.

Bridge diagnostics record the normalized configuration, exact per-kind burst
hit counts, SD extrema and operation count, and the index deadline applied at
reset. Checkers independently recompute burst counts and observed SD extrema;
a configured delay that was never exercised is visible in the evidence. The
first-loss CSV window remains available for rejected runs.

## Fault-time interrupt boundary

The following records the finding before the subsequent
[RTL fault-isolation correction](interrupt-fault-isolation.md). Original reports
remain preserved; the linked qualification describes current behavior.

The first stock overload run aborted in the simulation's `cosim_ack()` callback.
GDB identified an assumption that every interrupt acknowledgement had driven
data. The current RTL can leave an interrupt pending while a mailbox fault gates
off the host data output. The bridge now returns the modeled undriven value FF
**only while fault is asserted**, and counts `fault_iacks`. An undriven IACK
without fault still aborts. Faulted runs remain rejected; this is not a workaround
that makes them pass and does not change the FPGA or firmware.

The [original abort record](../reports/burst-initial-abort.json) and
[first-loss capture](../reports/burst-initial-abort.csv) are retained. A new
original-ROM regression enables IM1 interrupts and exercises this fault state.
The result describes current hardware logic: it does not promise a valid vector
or continued operation after a fault. Host reset remains the recovery boundary.

## Integrity and recovery checks

The ROM-free regression injects both ordinary write bursts and a larger burst
that faults the mailbox while interrupts are enabled. It requires byte loss or
a watchdog fault to remain observable. The exported logical disk must be either
unchanged or contain exactly the intended complete 1 KiB sector; every other
byte must remain unchanged. A cold remount with the overload removed must then
complete a clean write with exact persisted contents. The input disk is checked
again to ensure the recovery run did not mutate it.

This verifies sector contents for the tested fixture and logical-image remount.
It does not establish CP/M filesystem transaction atomicity, power-cut journal
recovery, arbitrary SD failure behavior or survival of real power loss. Existing
storage-fault qualification remains separate. In a stock overload run, successful
writes before failure may legitimately leave an incomplete filesystem operation;
that run is rejected rather than declared corruption-free from its exit status.

The ordinary burst profile is also replayed with tracing disabled: counters,
RAM, disk and screen must match exactly. Reset during writing and during delayed
writeback retains the existing image-preservation checks. No timing or integrity
acceptance predicate has been relaxed.

## Recorded results

The [early profile](../reports/combined-stress-early.json) and
[late profile](../reports/combined-stress-late.json) each pass all nine stock-ROM
cases: **18/18**, with zero byte loss and zero watchdog faults. SAVE, BDOS writes
and deletion exercise SD delays from 200 to 20,000 µs; cold reboots independently
check persisted file contents and deletion. Read-only and absent-media cases
remain unchanged. Every report records the exercised burst counts and source
hashes; sites without a burst hit are visible as zero counts.

The [public regression](../reports/combined-stress-public.json) passes all 14
cases, including burst/reset combinations, trace-disabled equivalence and two
overload sector-integrity/remount checks. The IRQ-enabled overload observes two
fault-time undriven acknowledgements, so the bridge correction has a regression.
`make test` also passes 52 tests with one optional test skipped.

The [stock overload report](../reports/combined-stress-overload.json) remains
rejected: one watchdog fault, one receive overrun, 986,170 transmit underruns,
one rejected write and zero completed writes. It reaches the ROM handoff but
fails guest completion and file-content checks. Its configured SD sequence is
not exercised because no block writes occur. The
[first-loss window](../reports/combined-stress-overload.csv) preserves the failure.

## Reproduction

```sh
python3 tools/check_cpu_cost_smoke.py --dac ../dac-emulation --out local/new-burst-public
python3 tools/check_classic.py --firmware-cosim --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm \
  --firmware-costs-us 1,4,8,8,4,8 --stress-profile tests/stress/combined.json \
  --out local/new-burst-early
python3 tools/check_classic.py --firmware-cosim --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm \
  --firmware-costs-us 1,4,8,8,4,8 --stress-profile tests/stress/combined-late.json \
  --out local/new-burst-late
python3 tools/check_cpu_costs.py --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm --profile overload=1,4,8,8,4,8 \
  --stress-profile tests/stress/overload.json --out local/new-burst-overload
```

Each output directory must be new. The experiment runner preserves rejected
profiles and exits successfully if experiments completed; inspect each profile's
`accepted` field. Crashes and malformed evidence remain execution errors.
