# USB analyzer control and capture download

The standalone analyzer firmware now provides USB CDC commands for status, arm,
stop and download. It starts idle with acquisition held clear. USB uses the Pico
SDK CDC descriptors and the product string `Pico1715 Analyzer`; its SDK VID/PID
is a development identity, not a newly allocated product identity. UART logging,
1200-baud boot reset and the SDK vendor reset interface are disabled.

[Configurable triggers](analyzer-triggers.md) extend this protocol with pre/post
history and commands 5/6. Normal capture retains the original version-1 format.

## Host workflow

Install `pyserial` in your Python environment, then use the explicitly selected
CDC port (Linux example below; Windows accepts a COM port):

```sh
python3 tools/analyzer_usb.py --port /dev/ttyACM0 status
python3 tools/analyzer_usb.py --port /dev/ttyACM0 arm
# Exercise or boot the 1715, then stop and drain the capture:
python3 tools/analyzer_usb.py --port /dev/ttyACM0 stop
python3 tools/analyzer_usb.py --port /dev/ttyACM0 download boot.p1715
python3 tools/cycle_trace.py --help
```

Commands print JSON status. State values are 0 idle, 1 initial/recovery hold,
2 waiting for a byte, 3 waiting for request release, 4 DONE and 5 ERROR. Stop
waits up to 15 seconds for DONE; a timeout does not discard the capture. Query
status before retrying. The PSRAM-full policy still stops and records losses.
ARM is rejected during active acquisition. ARM after DONE/ERROR explicitly starts
a new capture and discards the previous one; download it first if needed.

Download requires DONE, reads bounded 1024-byte chunks, checks every response
CRC and then validates the compact capture format. It publishes the final path
atomically without replacing an existing file. Interrupted or invalid downloads
remove their temporary file. Reconnect and rerun download to restart from byte
zero; data stays in PSRAM until the next ARM or board reset. A process crash may
leave a uniquely named `.part` file, which is never treated as a completed capture.

Disconnecting USB or dropping DTR resets only USB parser/output state. Acquisition
continues, and a completed capture remains available. Each successful ARM
increments a capture ID; reads and stop commands require the current ID. IDs
are scoped to one firmware boot, and the host does not resume partial files
across reconnects or power cycles. Use one host client per port.

## Wire protocol, version 1

All integers are little-endian. Commands 1–4 use a fixed 24-byte request; CONFIGURE (5) appends 24 bytes. The host then
consumes its full response before sending another. No text is mixed into CDC.

| Request bytes | Value |
| --- | --- |
| 0–3 | `P17Q` |
| 4 | version 1 |
| 5 | command: STATUS=1, ARM=2, STOP=3, READ=4; extensions 5/6 below |
| 6–7 | reserved zero |
| 8–11 | host request ID, echoed |
| 12–15 | expected capture ID; ignored for STATUS |
| 16–19 | byte offset; zero except READ |
| 20–23 | requested length; zero except READ |

READ length must be 1–1024 and wholly within the finalized capture. ARM uses the
previous ID as a precondition, then increments it. Replaying that ARM request
therefore cannot silently rearm again. STOP is idempotent for the same active or
completed capture. Capture ID exhaustion requires a firmware restart.

Responses have a 28-byte header followed by at most 1024 payload bytes:

| Response bytes | Value |
| --- | --- |
| 0–3 | `P17R` |
| 4–7 | version, echoed command, error, reserved zero |
| 8–11 | echoed request ID |
| 12–15 | current capture ID |
| 16–19 | echoed offset |
| 20–23 | payload length |
| 24–27 | CRC32 of header bytes 0–23 followed by payload |

CRC32 uses the reflected polynomial `0xedb88320`, initial and final XOR
`0xffffffff` (Python `binascii.crc32`). Errors carry no payload: 1 invalid command,
2 wrong capture state, 3 stale capture ID, 4 invalid range, 5 unavailable storage
or capture ID exhaustion. USB packet CRC protects requests at the USB layer;
there is no extra application CRC on requests.

Successful STATUS/ARM/STOP payloads are ten uint32 values: state, capture ID,
stored records, downloadable bytes, FPGA losses, PSRAM-tail losses, filtered
records, retries, full flag, stopping flag. Downloadable bytes is zero until
DONE. FPGA loss/filter totals are finalized when terminal status arrives from
the FPGA, so active status is not a final loss report. READ payload is the exact
requested slice of the existing `P1715CY` file, including its header at offset 0.

The parser seeks the request magic, rejects invalid versions/reserved bytes and
bounds every read. After a partial request or response, drop DTR for at least
100 ms before reconnecting. The supplied tool does this on open. It never retries
an ambiguous ARM automatically; query STATUS after reconnecting.

## Implementation and verification

`firmware/analyzer_usb.c` is the portable command handler used by both firmware
and native tests. USB input/output functions retain partial progress and never
wait for the host. The RP2350 main loop owns TinyUSB task servicing, using the
SDK CDC configuration/descriptors without starting its stdio background worker.
After each 256 capture-service iterations it runs TinyUSB and handles at most
24 input bytes and 64 output bytes. Capture reads are forbidden while acquiring.
TinyUSB task duration, interrupt load and actual capture throughput still need
physical measurement; the earlier 100/200 ns receiver model does not qualify
this combined USB loop. Hardware overflow remains explicitly counted.

Build with the existing toolchain and the SDK's pinned TinyUSB submodule:

```sh
git -C local/pico-sdk submodule update --init lib/tinyusb
cmake -S firmware -B build/firmware -DPICO_NO_PICOTOOL=1
cmake --build build/firmware --target pico1715_analyzer pico1715 -j2
python3 -m unittest discover -s tests -p test_analyzer_usb.py -v
```

The native tests compile the actual C handler and capture service with undefined
behavior checks, then drive them with the Python client using deliberately split
reads. Seven ROM-free tests cover lifecycle, bounds, stale IDs, malformed commands,
partial-request/response disconnects, CRC/format rejection and interrupted-download
cleanup/restart. They run through the existing `make test` CI step. An optional
eighth test transfers a supplied completed capture through the same protocol:

```sh
P1715_USB_CAPTURE=local/transport-final/boot-normal/capture.p1715 \
  python3 -m unittest discover -s tests -p test_analyzer_usb.py -v
```

The [verification report](../reports/analyzer-usb.json) records eight passing tests,
including byte-identical download of the 3,453,600-byte, 215,848-record boot capture,
and successful builds of both firmware targets. This test loads a previously
verified capture into simulated PSRAM; it does not emulate USB packets or rerun
the boot through the FPGA. TinyUSB enumeration, cable unplugging, QMI timings and
sustained acquisition with USB traffic remain bench tests. The later [passive adapter](../hardware/analyzer-interface/README.md) supplies
analyzer pin binding, receiver integration and routed timing; physical
qualification and PCB layout remain open.

## Optional remote reset

Commands 7–9 add reset status, reset and arm-then-reset. The standard build leaves
the accessory unavailable. See [the reset protocol, host workflow and accessory
contract](analyzer-reset.md) for exact fields, replay protection and bench gates.
