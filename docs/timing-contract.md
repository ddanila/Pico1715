# Scheduled-byte qualification — 2026-10-25

The timed profile passes all nine stock-ROM/SCP compatibility cases and 36
latency/fault experiments. This closes the scheduled-byte modelling milestone,
not electrical qualification or complete reproduction of the controller gates.
Results: [timed baseline](../reports/timed-compatibility.json) and
[timing experiments](../reports/timing-qualification.json).

## Evidence and interpretation

The old controller schematic, drawing `56-330-0102-1` /
`1.93.300102.3/04`, is PDF page 14 (printed sheet 11) of the locally held
`PC-1715-Schaltplaene.pdf` (SHA-256
`9d020e9dd41662f85b6a9a44e300cc9800ef20284c2a689e005f69a84f6e3fd3`).
Data PIO Q301 A1:1 ARDY/BRDY feed handshake logic connected to **/WAIT,
X2:A24**. /IORQ is X2:B24, /RD X2:B8, and /PIOCS0 X2:A3 in this drawing.
These are drawing references; connector orientation and specimen revision still
require physical confirmation before assigning PCB contacts.

The [service manual](https://xepb.org/robotron/docs/pc_serv.pdf) describes a
9.832 MHz source divided by four: use **2.458 MHz**, not 2.4576 MHz. It also
warns that long waits must not compromise DRAM refresh. At the qualified
250 kbit/s rate, bytes arrive at 31,250 bytes/s: **32 us or 78.656 CPU ticks**.
The ROM's INI + seven NOPs + JR loop takes 56 nominal ticks, so byte timing
cannot be inferred just by counting completed input instructions.

[Zilog CPU manual UM0080](https://www.zilog.com/docs/z80/um0080.pdf), PDF
pages 23–24 (printed 10–11), describes the automatic I/O wait state and /WAIT
sampling. [Zilog peripherals manual UM0081](https://www.zilog.com/docs/z80/um0081.pdf),
PDF pages 211–213, describes the PIO input/output ready and strobe handshakes.
They support modelling a receive latch and transmit register. Our overrun policy
(retain the unread byte, discard the arriving one) and empty-transmitter policy
(repeat the previous byte) are explicit model choices, not a gate-level proof
of every failure mode in the Robotron controller.

## Implemented timing contract

Enable with `tools/check_classic.py --timed`, or run the whole suite below.
Functional demand-driven mode remains available for comparison.

- Field acquisition starts from the existing control sequence. First byte and
  mark arrive after one byte period plus optional mark delay. Subsequent bytes
  arrive independently of CPU input, using a rational clock accumulator rather
  than rounding every byte to 79 ticks. This is still synthetic field acquisition,
  not a rotating-track/flux simulation.
- The default receive capacity is one byte. Empty reads wait; a full latch loses
  arriving field bytes and counts overruns. Gap-byte loss is not counted as a
  field error. Experiments can enlarge the receive queue to 16 bytes.
- The transmitter has one output register and an independent byte clock while
  /WE is active. Full-register writes wait. An empty register at a serialization
  deadline repeats its last byte and counts an underrun. A complete valid-CRC
  field is committed atomically at gate close; damaged physical tracks are not
  represented.
- Mark status becomes visible with the first byte. Optional IRQ delay postpones
  the mark interrupt, not the byte stream. The observed index/mark vectors are
  10h/12h; pending service is suppressed until RETI. Arming cancellation and reset
  cancel queued mark work. Full PIO modes and external interrupt chains remain
  outside the model.
- Reset cancels waits, input queues, output registers and incomplete writes while
  retaining the mounted image. End-to-end tests reset during a read and a write,
  check the image immediately, reboot and complete the BDOS workload. Reported
  transfer counters restart at reset.

DAC's appended `card.wait` callback defers **normal I/O transactions**, not
interrupt acknowledgements or memory transactions. Card time continues while
CPU microsteps stop; the read/write side effect and trace occur once. Its CPU
adapter holds an exposed transaction before the data-consuming microstep.
This is a T-state transaction abstraction: it cannot validate physical /WAIT
assertion setup, falling-edge sampling, data hold, or output-enable timing.

## Experimental boundaries

The workload creates, writes and rereads twenty 128-byte records through stock
BDOS/BIOS; the host independently checks the resulting 2,560 bytes. A *clean*
pass additionally requires zero lost bytes, underflows and rejected writes.

| Injected delay | Adjacent clean point | Adjacent failing point | Meaning |
|---|---:|---:|---|
| Minimum read-transaction latency | 12 ticks / 4.882 us | 13 ticks / 5.289 us | Receive overrun; workload fails |
| Minimum write-transaction latency | 15 ticks / 6.103 us | 16 ticks / 6.509 us | Transmitter underrun; workload fails |
| Mark IRQ delivery delay | 16 ticks / 6.509 us | 17 ticks / 6.916 us | Workload still succeeds via recovery, but bytes are lost |

Read/write delay is measured from the exposed I/O request and overlaps a wait
for readiness; it is **not** extra delay added after a ready byte. Each sweep
varies one delay at a time. These are local adjacent boundaries in this model
and workload, not globally monotonic limits, tolerances for every OS, or a
physical Pico service budget.

Two-byte buffering with read delay 16 and sixteen-byte buffering with read
delay 64 both fail: queues do not fix sustained excess latency. Removing waits
causes stale/empty reads and failure. Dropping field byte 50, corrupting field
CRC, and delaying mark acquisition by 1,000,000 ticks each expose failure without
changing media. Both mid-transfer reset cases recover cleanly. Full results
include options and error counters, including cases where software retries hide
loss; success text alone is deliberately insufficient.

## Reproduce

```sh
make test
python3 tools/check_timing.py \
  --dac ../dac-emulation --rom /path/r1715bt.bin \
  --disk /path/r1715.cpm --out local/timing-check
```

The checker enforces the pinned clean DAC revision and historical input hashes,
creates disposable images and exclusive output directories, and preserves input
files. `baseline/report.json` records all nine cases; `report.json` records the
36 experiments and source hashes. Historical binaries and traces are not
redistributed. See [hardware timing requirements](../hardware/timing-requirements.md)
for the implications and remaining bench gates.

Validation also includes C controller/timing unit tests, Python capture tests,
DAC's regression suite and runtime sanitizers, and an AddressSanitizer/
UndefinedBehaviorSanitizer run of the timed BDOS workload with independent
2,560-byte output verification. Leak detection was disabled for the standalone
Pico1715 sanitizer run. These checks qualify memory and model behavior, not the
unimplemented firmware or electrical interface.
