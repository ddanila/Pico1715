# Standalone FPGA/Pico mailbox fixture

This diagnostic bitstream creates synthetic host transactions inside the HX8K
and talks to the **real Pico firmware** over the existing parallel cable. It
needs no 1715 and no extra stimulus microcontroller. A 3.3 V USB-UART adapter is
used only to read its summary. The logic and UART have passed simulation, and
the bitstream is placed/routed; **no physical run has happened yet**.

The fixture checks the cable, mailbox direction/handshake and interrupt path.
It does not exercise the 5 V adapter, CPU timing or sustained disk-sector
traffic. Use the [adapter procedure](interface/README.md) separately.

## Wiring

**Disconnect every host/adapter connection before loading this bitstream.** It
changes the production reset pin from input to output. Leave only the Pico
mailbox cable, common ground and the diagnostic connections listed here.

| Fixture signal | Olimex header | Connection |
| --- | --- | --- |
| pico_data, pico_reg, write/request/ack, pending and IRQ notifications | Same as production mapping | Same Pico GP0–14, GP16–21 cable |
| test_reset_n | EXT1 pin 14 | Pico GP15; FPGA now drives reset |
| fixture_reset_n | EXT1 pin 12 | 4.7 kΩ to board 3.3 V; momentary switch to GND to restart |
| passed | EXT1 pin 10 | Scope/logic input; high after successful completion |
| failed | EXT2 pin 7 | Scope/logic input; high after failure |
| uart_tx | EXT2 pin 13 | 3.3 V USB-UART RX only, 115200 8N1 |
| GND | Board ground | Common with Pico and UART adapter |

Do not connect the UART adapter's power or TX pins. Do not connect its RS-232
voltage-level equivalent. Both Pico and FPGA modules must be powered; their
mailbox has no unpowered-module isolation. Follow the prototype guide for the
SD breakout and image. Default read-only firmware is sufficient.

## Build and run

```sh
make test-bench-fixture lint-bench-fixture
python3 tools/build_fpga.py --fixture --out build/fixture
# Program build/fixture/design.bin using the separately verified programmer.
# Load the ordinary read-only Pico firmware and dedicated raw SD image.
python3 tools/read_fixture.py --port /dev/ttyUSB0 --out local/bench-001.json
```

Programming is intentionally a separate operation: confirm the actual flash
part and read back the programmed bitstream using the chosen programmer. The
build tool does not flash devices. Use nextpnr with generic `--sdc` support;
the tested nextpnr source revision is recorded in the fit report. The input
clock is 100 MHz, production frontend is 50 MHz, and diagnostic sequencer is
25 MHz. No clock constraint is relaxed below its implemented clock rate.

The fixture holds reset low briefly, then releases it **before** waiting for
Pico readiness. This avoids deadlocking the firmware's reset handler. It allows
20 seconds for PSRAM/SD initialization, then performs:

1. 256 writes and matching reads of port 4, using A5/E5/B5/F5 safe control
   patterns. No media write command is issued.
2. Three writes: vector 10h, drive select EFh, index interrupt enable 83h.
3. Wait up to 300 ms for index IRQ; perform IACK and verify vector/source.
4. Issue synthetic ED/4D memory fetches and require the RETI notification.
5. Stop issuing transactions and repeat the UART result frame.

A successful report contains **515 completed normal-I/O transactions**, plus
IRQ/RETI checks. The complete synthetic fetch data is driven throughout each
fetch; this does not test real motherboard memory-data setup time.

The result's `max_cycle_us` is sampled from host I/O assertion to observation of
WAIT release, with a minimum 2 μs fixture hold. It is an upper-bound cycle
measurement quantized to 40 ns, not a CPU WAIT-setup measurement or the Pico
handler's internal duration. Check request-to-ACK separately with a scope under
real sector processing and SD-write load before attaching the machine.

## Results and faults

The frame is nine bytes: A5, failure code, completed count (little-endian 16-bit),
maximum cycle ticks (little-endian 32-bit, 25 MHz), XOR of the preceding eight
bytes. The reader resynchronizes after noise, rejects bad checksums/incomplete
pass counts, refuses to overwrite a report, and exits nonzero on failure.
It can also decode `--capture /path/raw-uart.bin`; such a report is explicitly
marked as an unverified capture, not new hardware evidence.

| Code | Meaning |
| --- | --- |
| 00 | Pass |
| 01 | Backend readiness lost or frontend fault |
| 02 | Pico initialization timeout |
| 03 | Readback or read output-enable mismatch |
| 04 | Output enabled during a write |
| 05 | Transaction timeout |
| 06 | Mailbox did not return idle |
| 07 | Index interrupt timeout |
| 08 | Wrong IACK vector/source/notification |
| 09 | Missing RETI notification |
| FF | Invalid diagnostic state |

On the bench, record at least ten cold starts and ten reset runs. Then remove
Pico readiness to verify a bounded failure and restart. Do not short driven ACK
or data signals to inject faults; stuck ACK and corrupt replies are already
covered by simulation and require a controlled test backend on hardware.
Preserve UART reports and scope captures under `local/` until their provenance
has been reviewed. Do not turn a synthetic test report into a hardware pass.
