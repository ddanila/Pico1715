# Receive buffering across index/mark interrupts

Pico firmware now uses a **two-byte receive queue**. The standalone controller
model keeps its one-byte default as a reference. This is an intentional custom
card design choice, not a correction to a claimed gate-level PIO emulation.
The queue uses the existing controller ring; no extra FPGA memory or hardware
is required.

## Why it changed

The [onboard-keyboard migration](onboard-keyboard.md) exposed one lost sync byte
in the stock BDOS workload. An index interrupt immediately preceded the mark
interrupt. Servicing index delayed the first read until the second field byte
had arrived. The guest recovered by retrying, but the zero-loss check failed.

Synthetic field acquisition and periodic index are scheduled independently in
our model. A rotating-track model could change which overlaps occur; this test
cannot establish the timing of a physical floppy controller. Nonetheless, a
finite receive queue is useful for a custom card: it absorbs a short interruption
without changing interrupt priority, postponing arrivals, moving index, or
patching the guest. Two bytes are sufficient for the bounded cases below. This
is not a universal CPU-latency guarantee.

`P1715_RX_FIFO_DEPTH` in `firmware/service.h` sets the production depth to two.
Service initialization applies it for read-only and writable configurations.
Host reset retains the configured depth while clearing queued data. Arming
cancellation and new field acquisition also clear the queue through the existing
controller behavior. A full queue still discards arriving bytes and counts
field-byte overruns; it never grows dynamically. Empty reads still wait.

At 250 kbit/s one byte arrives every 32 microseconds. Two queued bytes can bridge
one additional byte period of temporary delay. They cannot compensate for a
consumer that is consistently slower than the byte stream. Transmit buffering,
SD policy and guest ports are unchanged.

## ROM-free reproduction and phase sweep

```sh
python3 tools/check_firmware_interrupts.py --out local/new-interrupt-check
```

The test compiles production service/storage/controller code and the board-level
FPGA RTL. It drives scripted bus transactions and real IACK/ED-4D RETI sequences;
it does not execute Z80 instructions. Only disk phase and the one-byte diagnostic
capacity are injected directly into controller state. All configuration, data
reads, vector selection and interrupt service notifications use the normal
firmware/RTL paths.

The test varies index phase from -64 through +64 microseconds in one-microsecond
steps around nominal first-byte/mark arrival. Each record includes the actual
index-minus-mark offset in CPU ticks, including acquisition-mailbox latency.
A deliberate 96-microsecond acquisition delay gives the harness time to place
index before or after mark; it applies equally to both queue configurations.
The index handler has a 28-microsecond delay in addition to its scripted ACK/RETI
transactions, and the mark handler delays 16 microseconds before beginning data
reads. These are bounded test stimuli, not a measured instruction trace.

The [phase-sweep report](../reports/receive-elasticity.json) records 263 cases:

- 129 one-byte reference phases: 26 expose lost bytes and mismatched fields.
- 129 production phases: all ten-byte ID fields match, with zero overruns.
- Three production phases transfer full 1,030-byte data fields without loss.
- A 160-microsecond index-handler delay exceeds the queue's capacity and fails.
- A reader pausing 40 microseconds after each read also loses data, demonstrating
  that finite buffering cannot hide a sustained throughput deficit.

Every case checks data against the generated field, mailbox completion, IRQ
ownership through the real vector path, absence of underflows/transmit errors,
and unchanged disk contents. The existing model suppresses index edges while
in service; phases in which mark wins may therefore acknowledge no index.
These tests do not qualify the original PIO's pending-edge or nesting semantics.
The overload cases must report overruns **and** mismatched data to pass the test.

The stock-ROM/SCP check remains separate and requires exact persisted file
contents, complete SIO keyboard delivery, and zero RX/TX faults. Its report
includes the actual `rx_capacity`; a recovered BIOS retry alone cannot pass.
The [buffered stock report](../reports/buffered-firmware.json) passes all nine
cases with zero RX/TX faults, including the previously failing BDOS workload.
All 42 [storage-fault cases](../reports/buffered-storage-faults.json) also pass.
Both read-only and experimental-writeback Pico builds compile successfully.
The prior failed [one-byte run](../reports/onboard-firmware.json) remains as
historical evidence. Physical bus timing, firmware execution time, electrical
validation and other interrupt phases remain bench gates.
