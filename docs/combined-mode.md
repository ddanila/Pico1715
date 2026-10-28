# Experimental simultaneous controller and capture

The third `carrier_combined` FPGA personality shares the existing 22-pin Pico
link. It is opt-in: standalone controller/analyzer personalities and firmware
remain the default. This is a desk-tested implementation, not a qualified PCB
interface or physical timing result. Reserve sensing uses the separate PIM724 SP/CE connector; see
[reserve interface](reserve-interface.md).

## Wire contract

The normal four-phase mailbox occupies registers 0–11. A read of register 14
negotiates extension version 1, reply `A7`. Legacy firmware returns FF for this
unused read and receives no extension writes. No host port is added.

After negotiation, register 12 reads retrieve one command: 0 idle, 1 arm, 2 stop,
3 clear. Register 13 writes start a frame; register 15 writes continue it. Frames
retain the existing analyzer's 22-byte layout and CRC16. The first-byte marker
restarts a partial frame following link reset; sequence numbers deduplicate
complete retransmissions. Malformed evidence fails capture without claiming a
complete downloadable trace. Controller service continues independently.

Controller requests win every idle-link arbitration. An admitted auxiliary byte
finishes its ACK drain before a controller request can start. Command polls occur
at most once per 1024 acquisition clocks; the auxiliary handshake/drain timeout
is 1024 clocks (20.48 us at 50 MHz) per phase. Timeout quarantines the link until
reset, rather than reassigning a late ACK to a disk request. The controller's
independent watchdog remains in force. This bounds arbitration, not measured
firmware execution time. FIFO overflow records loss and never backpressures disk
service. A saturated trace can have substantial loss during dense disk traffic.

Acquisition and controller logic share 50 MHz. Capture uses the existing finite
FPGA FIFO, I/O/IACK/reset mask 0x170, and PSRAM bytes 1 MiB through 8 MiB. The disk
image remains below 1 MiB. Host reset restarts the transport, not the capture.
Card power loss invalidates volatile evidence. Stop and drain capture before eject;
eject lowers backend-ready and prevents further transfer from the FPGA.

## Firmware and USB

Build with `P1715_CARRIER=ON` and `P1715_COMBINED=ON`. The optional feature reuses
the controller USB framing/version; legacy status/eject commands and their
112-byte response payload are unchanged. New command IDs are 3 start, 4 stop,
5 trace status, 6 read next 64-byte chunk, and 7 rewind. These IDs are rejected
by standalone firmware. Commands 6/7 require both a complete capture and SAFE
eject. USB reads never access a live capture or stall a running guest.

New commands return twelve little-endian 32-bit fields followed by 64 data bytes:
capability, capture state, records, FPGA drops, local drops, total bytes, cursor
after read, chunk bytes, framing errors, CRC errors, filtered events, pending FPGA
command. Unused bytes are zeroed. State values match the existing analyzer;
zero means no capture, 4 complete, 5 failed. Start success queues clear/arm; it
does not establish that the FPGA accepted those commands. The status remains HOLD
until arm is retrieved. Capability means firmware support, not hardware identity.

Use `tools/controller_usb.py --port PORT trace-start`, then `trace-stop` (waits
for drain), `eject`, and `--output NEW.p1715 trace-save`. Stop the guest workload
before eject. Downloads start with rewind, validate cursor/length and never
replace an existing file. After interrupted download, rewind and retry. The
result is the existing P1715CY capture format, including drop accounting.

## Reproduce desk checks

```
make test-carrier-combined test-combined-endpoint test-firmware-service
python3 -m unittest discover -s tests -p 'test_*usb.py' -v
python3 tools/build_firmware_faults.py --suite timing --combined --out build/combined-cosim
build/combined-cosim/firmware-timing --combined
python3 tools/build_fpga.py --combined
```

Pass explicit local `--nextpnr`/`--icepack` paths when those tools are not installed
on PATH. The internal FPGA timing report does not qualify external cables, bus
receiver delays or analog return paths. Co-simulation resolves read-data/WAIT
feedback at the opposite 100 MHz edge; it is a discrete receiver model.

`tools/build_cosim.py --combined --dac DAC --out OUTPUT` builds the classic CPU
probe using the same firmware and RTL. Capture starts automatically; set
`PICO1715_COMBINED_CAPTURE=0` for a control. An optional new output pathname in
`PICO1715_COMBINED_TRACE` retains the trace at final export. Final export stops
capture, drains it, safely ejects, and verifies PSRAM against the persisted SD
image. This intentionally terminal path differs from the browser's resumable
export. Real-machine boot, loss-free capture throughput and measured reserve
power are not established by these tests.

The classic guest qualification runner is `tools/check_combined_classic.py`.
It requires a new output directory, runs INFO, writes a deterministic 32 KiB file,
and cold-boots to verify it. An independent CP/M filesystem reader checks every
pre-existing file and the exact new contents. Each run decodes its saved capture;
reported loss is retained. See [recorded run](../reports/combined-classic.json).

The saved INFO/write/cold-verify captures also pass the existing DAC workbench's
`Capture.open` JavaScript parser, including their drop counts. This checks file
compatibility; direct combined-device browser USB control is not implemented.
