# FPGA–Pico analyzer transport and PSRAM capture

The standalone compact analyzer now connects the production encoder/FIFO to a
CRC-protected parallel link and a shared C receiver. The `pico1715_analyzer`
RP2350 firmware target stores captures in PSRAM. This is a tested desk prototype:
the later [passive adapter](../hardware/analyzer-interface/README.md) now supplies
the FPGA pad map and routed timing. Physical qualification remains open. The later [USB increment](analyzer-usb.md) adds
control/download to this transport.

## Link and capture lifecycle

`hardware/rtl/analyzer_transport_top.v` combines the existing passive cycle
capture with `analyzer_link.v`. The intended acquisition clock is 50 MHz. All
host drive/control outputs stay inactive and the interrupt-chain input is passed
through. The controller and analyzer are separate firmware/FPGA personalities.

The logical Pico GPIO assignments are:

| GPIO | Direction from Pico | Signal |
| --- | --- | --- |
| 0–7 | input | frame byte |
| 8–12 | input | byte index, 0–21 |
| 13 | input | request |
| 14 | output | acknowledgement |
| 16 | output | link synchronization, active low |
| 17 | output | capture clear, active high |
| 21 | output | capture enable |

These interface assignments are now mapped in the separate
[passive adapter harness](../hardware/boards/hx8k-analyzer-wiring.md); bench
qualification is pending. Each byte uses four
phases: FPGA request high, Pico ACK high, FPGA request low, Pico ACK low. Data and
index remain stable until acknowledged. FPGA inputs ACK/synchronization/enable
are synchronized; capture reset asserts asynchronously and releases synchronously.
The parallel data bus is held for the handshake rather than independently
synchronized bit by bit. Actual GPIO sampling/setup/hold must be bench-qualified.

Every frame is 22 bytes:

| Bytes | Content |
| --- | --- |
| 0 | type: 1 record, 2 terminal status |
| 1 | protocol version 1 |
| 2 | flags: record 0; status bit 0 done, bit 1 FPGA loss |
| 3 | reserved, zero |
| 4–19 | payload |
| 20–21 | little-endian CRC16-CCITT over bytes 0–19, polynomial 0x1021, initial 0xffff |

Record payload is the unchanged 16-byte [compact cycle record](cycle-analyzer.md).
Terminal payload is four little-endian uint32 values: FPGA dropped, filtered,
acknowledged records, kind mask. Firmware currently requires mask `0x170`
(I/O read/write, interrupt acknowledge and reset intervals).

The FPGA retains one staged frame across link resynchronization. The receiver
validates CRC/index, stores the record, fences the PSRAM write, then acknowledges
the final byte. A replay of the last identical sequence is acknowledged without
appending it again. Conflicting duplicates and backward sequences are rejected.
Sequence ordering assumes a bounded session with fewer than 2^31 sequence steps
between retained records. A partial-handshake timeout is 10 ms. Recovery holds
synchronization low for 100 us; four consecutive errors stop the service with
all controls low. An idle running capture has no timeout.

Stopping lowers capture enable, finishes the current encoded interval and drains
the FIFO/link before accepting terminal status. Firmware checks the terminal
record count. A capture clear starts a new session; link synchronization alone
preserves queued and staged data. The FIFO has 255 usable entries and counts
filtered records separately from overflow losses.

## PSRAM and firmware

The first 1 MiB remains reserved for disk/cache use. Analyzer storage occupies
the following 7 MiB at uncached address `0x15100000`: a 32-byte compact header
and up to 458,750 records. PSRAM initialization tests only the requested region.
The existing controller initializer continues to request its original 819,200
bytes. Reserving space does not yet implement simultaneous controller/trace mode.

When another record would exceed capacity, firmware stops acquisition, drains
and counts the discarded tail, and adds these losses to FPGA losses in the file
header. It never wraps or overwrites previous records. Only `P1715_LA_DONE`
authorizes exporting a successful capture; ERROR or an unfinished capture must
not be exported as complete, even if header bytes are present.

The standalone target now starts idle after PSRAM initialization; use the
[USB host utility](analyzer-usb.md) to arm, stop and download. SWD still exposes
`p1715_analyzer_status` for diagnostics. The original transport report predates
USB integration; its polling profiles do not measure the current USB loop.

```sh
cmake -S firmware -B build/firmware -DPICO_NO_PICOTOOL=1
cmake --build build/firmware --target pico1715_analyzer pico1715 -j2
```

Use the project's existing Pico SDK/toolchain setup. Both targets were compiled
for RP2350; neither has been run on a board.

## Reproducible verification

```sh
python3 tools/check_analyzer_transport.py --out build/transport-check
```

Requires Python 3.11+, C/C++, Icarus Verilog, Verilator and Yosys. Output directories
must be new. The check runs the native cycle-to-packet test, existing cycle
regression, lint, synthesis and nine shared-firmware/RTL fault scenarios. These
cover normal/slow reception, CRC and index corruption, lost final acknowledgement,
short and overflowing consumer stalls, full PSRAM and permanent corruption.
Assertions check ordering, exact record content, loss accounting, memory bounds,
reserved-memory preservation and handshake stability. Capture files are also
validated by the existing host decoder. CI runs these ROM-free checks.

Optional stock-boot replay uses the prior full capture and filtered reference:

```sh
python3 tools/check_analyzer_transport.py --out local/transport-stock \
  --workload local/cycle-analyzer-final/stock-boot-all/cycles.p1715 \
  --reference local/cycle-analyzer-final/stock-boot-io-only/cycles.p1715
```

The [recorded report](../reports/analyzer-transport.json) includes source hashes,
tool versions and scenario results. Both receiver profiles retain all 215,848
selected boot records, byte-identical to the filtered reference, with 7,037,026
intentionally filtered events and no overflow. The output is 3,453,600 bytes.
The replay injects already encoded records into the same production FIFO/link at
their original completion times. It does not rerun the ROM or encoder at 50 MHz;
the original 9.832 MHz timestamps remain intact. Native top-level simulation
separately checks encoder/link integration, late read data and WAIT counting.

The modeled FPGA clock is 50 MHz, receiver polling intervals are 100/200 ns, and
each memory commit delays acknowledgement by 1 us. These assumptions establish a
testable throughput budget, not achieved RP2350/QMI performance. Synthesis uses
908 LUT4s and eight block RAMs; placement/routing and board timing remain open.
If measured polling is too slow, PIO/DMA reception can replace GPIO polling while
preserving this frame format and receiver validation contract.
