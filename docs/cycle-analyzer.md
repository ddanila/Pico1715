# Compact cycle capture and emulator verification

The analyzer now has a second standalone RTL personality for long diagnostic
traces: `cycle_capture_top.v` combines `cycle_encoder.v` with a FIFO holding 255 records.
The [raw analyzer](analyzer-prototype.md) remains available for sampled waveforms.
The compact personality now has a tested [FPGA–Pico link and PSRAM receiver](analyzer-transport.md). [USB control/download](analyzer-usb.md) is also implemented; board integration and physical qualification remain open.

## What a cycle record means

The encoder consumes the same 40-bit sample layout as the raw analyzer. It groups
consecutive samples with the same active bus operation into an interval. It emits
one 16-byte record when the operation ends or changes, recording:

- Operation: opcode fetch, memory read/write, I/O read/write, interrupt
  acknowledgement, refresh, reset interval, or invalid control combination.
- Full 16-bit address from the first active sample and data from the last active
  sample. Idle-bus data is never substituted for the last asserted-window data.
- Start timestamp, interval duration, and the number of samples with `/WAIT` low.
- Sequence number and flags for partial start, truncated end, saturated counters
  and an address change while the operation remained asserted.

A fetch followed directly by refresh becomes two records. `/M1 + /IORQ` is an
interrupt acknowledgement, not an opcode fetch. Contradictory memory/I/O requests
or simultaneous read/write strobes become invalid-operation intervals. Reset
interrupts an active operation with its truncated flag set and produces a separate
reset interval when released. Capture stop also emits the pending interval with
the truncated flag. Starting acquisition in an active operation marks it partial.

These are **sampled bus intervals**, not a claim that every observed operation
completed successfully. WAIT-low samples are elapsed acquisition-clock units,
not a count of Z80 Tw states. Refresh data and IACK address are observational
fields, not meaningful transferred bytes/addresses. Data can change during a read;
the last in-window sample is used. Address changes remain one flagged interval;
they are not silently split into apparently valid transactions. Consecutive
same-kind cycles require an observed inactive/different-kind sample between them.
Sub-sample transitions and half-clock setup/hold are outside this abstraction.

## FIFO and filter contract

All controls are synchronous to `clk`. `enable` starts acquisition; its falling
edge stops and flushes a pending interval. `idle` means the encoder and its
one-event pipeline have drained; it does **not** mean the FIFO is empty. Drain
`queued` before changing capture sessions/configuration. Card reset clears
metadata, counters and timestamp; observed host reset does not clear them.

`capture_mask[9:0]` is latched on the rising edge of `enable`; bit N accepts kind
N from the table below. Changes while enabled do not affect the current session.
`0x3fe` captures every operation, `0x170` captures I/O, IACK and reset, and zero
filters everything. Intentionally excluded records increment `filtered`.

Assert `read_enable` to dequeue one record on a clock edge. `read_valid` then
qualifies `read_record`; an empty read has no response. Simultaneous dequeue and
enqueue from a full FIFO returns the old head and accepts the new event. One RAM
slot is always reserved, so reads and writes never target the same address on
the same edge; this avoids relying on device-specific RAM collision behavior. Host bus
activity is never stalled. When the FIFO is full without a dequeue, the new event
is dropped, `overflow` latches and `dropped` increments. Filtered records do not
set overflow. The counters saturate at 0xffffffff; at saturation their values
are lower bounds. Sequence numbers advance before filtering/dropping, so gaps
remain visible; aggregate counters distinguish filtering from accidental loss.

All host drive requests, including reset, are tied inactive; IEO follows IEI.
Physical output isolation during power sequencing/configuration still needs the
adapter design. This prototype has no FPGA pin constraints or electrical timing
qualification. It does not switch the production controller top into analyzer mode.

## Compact file format, version 1

This has its own magic, separate from raw captures. Little-endian header
`<8sHHIIIII` (32 bytes): `P1715CY` plus NUL, version 1, record size 16, sample
clock Hz, record count, dropped count, filtered count, capture mask. A file starts
at a card-reset capture session. Files are frozen exports, not USB framing.

A record is `<BBHHHII` (16 bytes): tag, data, address, WAIT-low sample count,
duration samples, tick32, sequence32. The tag's high nibble is kind and low nibble
is flags. RTL packs these into `{sequence,tick,duration,wait,address,data,kind,flags}`.

| Kind | Meaning |
| --- | --- |
| 1 | Opcode fetch |
| 2 / 3 | Memory read / write |
| 4 / 5 | I/O read / write |
| 6 | Interrupt acknowledgement |
| 7 | Refresh |
| 8 | Reset interval; address/data/WAIT count are zero |
| 9 | Invalid control combination |

Flags bits 0–3 respectively mean partial start, truncated end, counter saturation
and changed address. The 16-bit duration/WAIT counters saturate at 65535 samples
rather than wrap. A saturated duration is a lower bound. Tick and sequence wrap
modulo 2**32; absent observations spanning a complete timestamp wrap cannot be
uniquely timed from tick32 alone. CSV preserves ticks and sample counts rather
than inventing sub-cycle waveform transitions.

`tools/cycle_trace.py` validates records incrementally, so a whole boot file need
not be loaded into RAM. It rejects unknown formats, malformed fields, truncation,
extra bytes, overlapping intervals, duplicate sequences and unexplained gaps.
Trailing filtered/dropped records are represented by aggregate counters; their
individual payloads and times cannot be recovered.

```sh
python3 tools/cycle_trace.py capture.p1715 --csv cycles.csv
# Validate without exporting:
python3 tools/cycle_trace.py capture.p1715
```

## Independent emulator comparison

`tools/build_analyzer_cosim.py` compiles the existing classic probe with an
optional passive observer and Verilates the actual compact capture RTL. It uses
the pinned, unchanged DAC CPU/motherboard and Pico1715's C controller model. It
observes CPU pins after each T-state; it does not construct captured records from
the expected callback log. Four bus-level samples per CPU tick give a deterministic
9.832 MHz fixture. Clock levels within a T-state are illustrative, not a physical
U880 waveform. Native I/O waits use DAC's transaction-wait seam.

The independent oracle is DAC's memory/I/O/interrupt-acknowledgement callback
stream. Each callback must fall inside the appropriate captured interval and
match address/data/type; each captured transfer must have a matching callback.
Memory reads may be fetches or ordinary reads; directed HDL tests distinguish
those two. IACK address is intentionally not compared with DAC's placeholder
address. Refresh counts are separately checked against observed CPU refresh
intervals, and WAIT totals against the transaction-wait state. Traces are drained
by an ideal host sink; this does not qualify Pico/USB bandwidth.

The checker runs baseline, full capture and I/O-only capture from identical inputs.
Execution counters and hashes of final RAM, screen, disk and I/O log must match
the baseline exactly. Every retained I/O-only record, including sequence and
timestamp, must match the corresponding full-capture record. External inputs
are checked before/after; copyrighted ROM, disk and captured payloads stay local.

## Results and reproduction

[Recorded qualification](../reports/cycle-analyzer.json) passes 90 directed HDL
checks, format/export tests, lint, iCE40 synthesis, a small original Z80 program,
and an unmodified stock ROM/SCP boot through the OS prompt. The boot runs
20,000,000 CPU ticks (about 8.14 seconds) and supplies 80,000,000 samples.

| Boot capture | All operations | I/O + IACK + reset |
| --- | ---: | ---: |
| Records | 7,252,874 | 215,848 |
| File bytes | 116,046,016 | 3,453,600 |
| DAC callbacks matched | 4,584,701 | 215,848 |
| WAIT-low samples | 1,982,720 | 1,982,720 |
| Interrupt acknowledgements | 8 | 8 |
| Intentionally filtered | 0 | 7,037,026 |
| Overflow drops | 0 | 0 |

The full trace has one flagged boundary interval; the filtered trace has none.
Neither has saturation or changed-address flags. The I/O trace is about 3.3 MiB,
small enough in capacity for the proposed 8 MiB PSRAM alongside the disk image.
The later [transport increment](analyzer-transport.md) allocates that RAM and
replays this workload through the production FIFO/link and shared receiver;
physical throughput remains unqualified. The full trace
still needs much more storage; compact encoding is not unlimited capture.

Default synthesis uses eight iCE40 RAM blocks and 461 LUT4s with the recorded
toolchain, without placement/routing. The FIFO has 4,080 usable bytes; useful retention
needs a downstream consumer. Directed tests cover last-sample data, adjacent
fetch/refresh, WAIT duration, timestamps, partial/truncated cycles, reset,
invalid strobes, saturation, filtered sequences, FIFO loss, full simultaneous
read/write and passive host outputs.

ROM-free checks (also run by CI):

```sh
python3 tools/check_cycle_analyzer.py --dac ../dac-emulation --out local/cycle-check
```

Stock boot qualification, requiring the externally supplied reference hashes:

```sh
python3 tools/check_cycle_analyzer.py --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm --out local/cycle-stock-check
```

Output directories must be new. [FPGA–Pico transport and PSRAM buffering](analyzer-transport.md)
now pass workload replay with bounded consumer stalls. [USB control/download](analyzer-usb.md)
also passes shared-handler tests. Board receiver/pin revisions and bench timing remain
separate gates. Compact pre/post-trigger capture is also still future work; the
existing raw personality provides that feature today.
