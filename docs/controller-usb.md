# Controller USB status and safe eject

The controller firmware now exposes USB CDC status and orderly eject. Analyzer
firmware remains a separate target/protocol. This interface neither changes
write policy nor asserts backup readiness, power failure or motherboard reset.
The default controller build remains read-only.

## Host use

Install Python's `pyserial` package in your host environment, then use:

```sh
python3 tools/controller_usb.py --port /dev/ttyACM0 status
python3 tools/controller_usb.py --port /dev/ttyACM0 --eject-timeout 30 eject
```

Commands print JSON. `state=2` means initialized; E1/E2/E3/E4 hex values identify
PSRAM, SD/open, image-read, or protected-budget initialization failure. USB still
runs after initialization failure, while the bus backend stays disabled. No
status request can turn a failed backend on.

`shutdown` is 0 RUNNING, 1 DRAINING, 2 SAFE, 3 UNSAFE. Eject requests the existing
shutdown path, isolates the card, and waits for SAFE with zero dirty blocks,
no storage operation in flight and no storage error. It exits unsuccessfully on
UNSAFE or timeout. A timeout or disconnect does **not** cancel a submitted eject:
keep power on and query status. Repeating eject is idempotent. There is no remount
or resume command; firmware restart is required after terminal shutdown.

Request timeouts default to five seconds. Storage core USB processing may be
delayed by a journal transaction, including real SD busy time. Increasing a host
timeout changes neither firmware deadlines nor the meaning of SAFE. SAFE has the
same SD durability limitations as the [shutdown contract](shutdown.md).

Status also includes write policy, reserve state/budget, storage errors,
maximum observed mailbox service time, completed requests/writes, rejected writes,
and receive/transmit loss counters. The current Pico wiring has **no FPGA fault
input**: these counters are not a direct read of the FPGA watchdog latch. Receive
and transmit counters belong to the controller model and may reset with the host.

## Core ownership and bounded work

TinyUSB is initialized and serviced exclusively on core 1, which also performs
storage work. SDK stdio USB's worker is not started; USB reset-via-baud and vendor
reset interfaces are disabled. Core 1 visits USB before each storage scan and
between completed journal block transactions, outside the image lock. Read-only
builds run USB without scanning for dirty blocks. Failed initialization runs a
USB-only worker. No USB callback waits for the host to read a response.

The application consumes at most 16 request bytes and sends at most 64 response
bytes per visit, with one fixed request buffer and one fixed response buffer.
It submits through a single-slot C11 acquire/release mailbox. Core 0 examines this
mailbox every 256 service iterations and processes at most one command. It
captures diagnostics and controller counters while holding the existing image
lock, then publishes the complete snapshot. Core 1 never reads the live,
SWD-visible multiword diagnostic structure.

Both cores own the mailbox in explicit phases: free, request, response. An
unread response prevents another request from being accepted; there is no
unbounded command queue or spin waiting for another core. A disconnect discards
partial requests and response bytes. DTR-drop and unmount callbacks observe
every delivered transition, including drop/rise within one USB task visit. If a command was submitted, its completion
is drained before accepting another command, even after reconnect. The shutdown
operation itself continues independently of the USB connection.

This bounds application buffers and work per visit, not TinyUSB execution time.
The pinned TinyUSB task drains its event queue; USB interrupt load, journal
latency and memory contention still need measurements. Pico critical sections
mask interrupts on the lock-holding core, so a USB callback does not run inside
an image critical section. Simulation charges snapshot copying through the
existing snapshot-cost hook and injects separate worker delays outside the lock.
It does not emulate the USB stack or prove a physical service-time budget.
Protected-writeback budgets must include USB visits and interrupt/memory
contention as well as the SD transaction itself.

## Wire format, version 1

All integers are little-endian. Requests are exactly 16 bytes:

| Offset | Meaning |
| --- | --- |
| 0–3 | `P1CQ` magic |
| 4 | Version 1 |
| 5 | STATUS=1, EJECT=2 |
| 6–7 | Reserved zero |
| 8–11 | Request ID, echoed by the response |
| 12–15 | CRC32 of bytes 0–11 |

Responses have a 16-byte header, zero or 112 payload bytes, and a final four-byte
CRC32 of header plus payload:

| Offset | Meaning |
| --- | --- |
| 0–3 | `P1CR` magic |
| 4–7 | Version, echoed command, error, reserved zero |
| 8–11 | Echoed request ID |
| 12–15 | Payload size |

CRC32 uses the same reflected IEEE algorithm as Python `binascii.crc32`. Errors
are 1 malformed request, 2 unsupported command, 3 service rejected the command,
4 control mailbox busy. Errors 1/2/4 have no payload; error 3 carries the snapshot.
Success always carries a snapshot. The host verifies identity, size and CRC
before interpreting state. Protocol magic differs from the analyzer protocol.

The payload is `<10I9Q>`: ten 32-bit fields followed by nine 64-bit fields:

- `state, dirty_blocks, storage_error, max_service_us, shutdown, shutdown_reason,
  backup, write_policy, dirty_limit, storage_busy`
- `requests, reserve_us, shutdown_deadline, writes, rejected_writes, overruns,
  underflows, tx_overruns, tx_underruns`

Request IDs correlate responses; they are not replay-prevention tokens. Both
commands are safe to repeat within their stated semantics. Unsupported or
CRC-invalid commands cannot request shutdown. Send one request and read its
response before another; unsolicited pipelined bytes are not queued by the
portable handler. Reconnect after framing/CRC errors to discard residual bytes.

## Verification and reproduction

[Protocol and contention evidence](../reports/controller-usb.json) covers eleven
UBSan-backed shared-handler/host-CLI tests and four firmware/RTL contention cases.
Tests include partial transfers, corrupt/unsupported requests, 64-bit snapshots,
backpressure, disconnect before/after submission, repeated eject, startup failure,
storage failure, host timeout, and a snapshot taken while a block write is busy.
Exact persisted sector contents are independently checked after successful eject.

The native adapter test also checks the 16-byte RX/64-byte TX visit bounds,
endpoint backpressure, rapid DTR reconnect and completion after disconnect.
[ARM build evidence](../reports/controller-usb-arm.json) covers read-only,
experimental writeback and the protected branch (compile-only placeholder
budgets, not reserve qualification). The analyzer target also still builds.

The sustained read fixtures inject 0 or 8 µs snapshot cost with delayed SD writes;
the latter also adds 1 ms of worker-side work per USB visit. Both remain loss-free
and process more than ten status responses. A 128 µs snapshot overload still
faults the mailbox. Eject during delayed writeback reaches SAFE with exact saved
contents. These are hypothetical costs, not measured Pico timings.

```sh
python3 tools/check_controller_usb.py --out local/new-controller-usb
make test test-store test-firmware-service
cmake -S firmware -B build/new-controller-usb -DPICO_NO_PICOTOOL=1
cmake --build build/new-controller-usb --target pico1715 pico1715_analyzer -j2
```

The [early](../reports/controller-usb-early.json) and
[late](../reports/controller-usb-late.json) stock-ROM stress profiles pass all
**18/18 cases**, with zero byte loss or watchdog faults.

The broader regressions also pass: [14 CPU cases](../reports/controller-usb-public.json),
[263 interrupt cases](../reports/controller-usb-interrupts.json),
[153 service-timing cases](../reports/controller-usb-timing.json), and
[42 storage-fault cases](../reports/controller-usb-faults.json).
`make test` passes 63 tests with one optional skip; storage and firmware-service
unit suites pass as well. These general regressions run without active USB traffic;
the four contention cases above exercise control traffic with the scripted bus.

Set `PICO_SDK_PATH` and the ARM compiler path for the local toolchain. The same
controller code builds for read-only and experimental writeback. CI runs the
portable protocol/CLI suite and contention check without private ROMs or USB
hardware. USB enumeration, cable unplugging, sustained host traffic and the real
SD busy-time budget remain bench qualification.
