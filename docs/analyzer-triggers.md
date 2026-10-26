# Compact analyzer triggers and rolling history

The compact USB analyzer can now retain a bounded history, match an event, record
a chosen number of following events and stop automatically. Matching runs in the
shared Pico receiver **after link CRC validation and duplicate suppression**.
It needs no FPGA pin or bitstream changes. This is a cycle-record trigger, not an
edge trigger on raw FPGA samples.

```sh
# Capture 128 retained events before a write to port/address 0x0030,
# and 64 retained events after it. Address is exact unless a mask is supplied.
python3 tools/analyzer_usb.py --port /dev/ttyACM0 arm \
  --trigger io-write --address 0x0030 --pre 128 --post 64
python3 tools/analyzer_usb.py --port /dev/ttyACM0 status
# Once state is DONE:
python3 tools/analyzer_usb.py --port /dev/ttyACM0 download port-write.p1715
python3 tools/cycle_trace.py port-write.p1715 --csv port-write.csv
```

Supported event choices are `io-read`, `io-write`, `io` (either), `iack` and
`reset`. `--address-mask` and `--data-mask` are optional hexadecimal/integer
masks. Matching uses `(value & mask) == (configured_value & mask)` for both
fields and membership in the kind mask. Supplying an address or data value makes
that field exact by default; omitting the field makes it a wildcard. Reset records
have zero address/data. Reset here means observed connector /RESET2, not proof
that CPU /RESET1 was asserted.

`arm` without trigger options explicitly disables triggering and preserves the
previous linear-capture workflow and version-1 file format. `stop` remains useful
if the event never happens or if the user wants a shorter post-trigger window.

## Window semantics

- Counts refer to **received retained records**, not clock samples or all CPU
  cycles. The FPGA's existing mask 0x170 retains I/O, IACK and reset events.
- Before a match, PSRAM retains the most recent `pre` records in a ring. Older
  records are intentionally omitted. Pre=0 is valid and keeps no history.
- The first matching record is included once. Its zero-based index in the file
  is the available pre-history length, which may be less than requested.
- Exactly `post` following records are retained, then acquisition is stopped.
  Post=0 stops on the matching record. Matching records later in the window do
  not retrigger it.
- Already queued FPGA records are still drained and acknowledged. Records after
  the chosen window are counted as intentional omissions, not transport loss.
- Manual stop freezes the current window immediately at the receiver. Pending
  records are drained but cannot fire a new trigger or extend the window. Before
  a match, the result is an explicitly untriggered history; after one, it records
  the actual shorter post history. Stop during initial clear yields an empty file.
- `pre + 1 + post` must fit the buffer; for the 7 MiB region the limit is 458,747
  records with the 80-byte extended header. Invalid configurations are rejected
  before arming. The first 1 MiB reserved for the disk remains untouched.

The ring is not rotated or copied at stop. USB reads map logical file offsets to
physical ring slots, so wraparound is invisible in the chronological download.
Only DONE is exportable. CRC failure cannot fire a trigger; retransmitting a
committed record cannot fire it again or consume a second post slot.

A record lost to FPGA overflow cannot trigger the receiver. Pre/post counts span
the records that arrived, so a window with losses is not a complete history of
all host events. Loss counters remain explicit and separate from omissions.
The report carries whole-session loss/filter totals, not a reconstruction of
where every loss occurred. Receiver polling/QMI throughput with USB activity is
still unmeasured; the prior modeled timing profiles are not bench qualification.
The existing sequence-ordering limitation also remains: fewer than 2^31 sequence
steps between received records, and fewer than 2^32 received records per session.

## USB extension

Existing command framing and commands 1–4 remain compatible. Two commands extend
[USB protocol version 1](analyzer-usb.md):

- **5 CONFIGURE:** offset=0, length=24, followed by six little-endian uint32 values:
  enabled, kind mask, packed address, packed data, pre, post. Packed address is
  `(mask16 << 16) | value16`; packed data is `(mask8 << 8) | value8`, with upper
  16 bits zero. Disabled configuration must have all six values zero.
- **6 TRIGGER_STATUS:** offset=length=0; no request payload. Returns metadata for
  the current capture. Both commands require the current capture ID.

CONFIGURE is atomic, rejected during acquisition/draining, and affects the next
ARM. It does not change a completed capture's metadata or contents. Partial
configuration is discarded on disconnect; the prior configuration survives.
ARM still increments the capture ID. Configuration/status responses use the
48-byte metadata layout below; CONFIGURE reports the pending configuration with
no trigger, while TRIGGER_STATUS reports the capture's actual state. DTR changes
and USB disconnects do not clear configuration, history or trigger state.

The CLI configures before arming and includes trigger status in its JSON output.
After an ambiguous ARM/CONFIGURE timeout, reconnect and inspect status or resend
an explicit configuration before the next ARM; do not assume the command failed.

## Triggered file format (version 2)

The magic, 16-byte record layout and first 32 header bytes remain as in
[compact captures](cycle-analyzer.md), except the version is 2. Another 48 bytes
(twelve little-endian uint32 values) precede the records, making an 80-byte header:

| Offset | Field |
| --- | --- |
| 32 | enabled, always 1 in a version-2 file |
| 36 | kind mask |
| 40 | packed address mask/value |
| 44 | packed data mask/value |
| 48 | requested pre records |
| 52 | requested post records |
| 56 | triggered: 0 or 1 |
| 60 | trigger index; 0xffffffff if unmatched |
| 64 | original trigger sequence; 0xffffffff if unmatched |
| 68 | intentionally omitted window/history records |
| 72 | actual post-trigger records retained |
| 76 | stop reason: 1 automatic window complete, 2 manual |

The base header's filtered count is FPGA-filtered events **plus** intentional
window/history omissions, saturating at uint32 maximum. Its dropped count still
means actual FPGA/local loss. Original timestamps and sequence numbers are
preserved. The host validates metadata against the trigger record, window counts
and sequence gaps. Older decoders reject version 2 rather than treating the
extended header as data. Version-1 files remain byte-identical in normal mode.
CSV exports of version 2 add a `trigger` column marking the matching record.

## Verification

```sh
python3 -m unittest discover -s tests -p test_analyzer_usb.py -v
python3 tools/check_analyzer_transport.py --out build/trigger-check
cmake --build build/firmware --target pico1715_analyzer pico1715 -j2
```

The [recorded results](../reports/analyzer-triggers.json) include native USB tests
against the real C handler/receiver, plus Verilated production FIFO/link tests.
The tests cover ring wrap, masks, first/early matches, zero pre/post, manual
snapshots, overflow, corrupted frames, lost final ACK, configuration atomicity,
initial-clear stop, malformed file metadata and interrupted downloads. The native
C seam runs with undefined-behavior checks. Guard regions check PSRAM bounds.

Optional boot-workload replay uses the same inputs as the transport qualification:

```sh
python3 tools/check_analyzer_transport.py --out local/trigger-check \
  --workload local/cycle-analyzer-final/stock-boot-all/cycles.p1715 \
  --reference local/cycle-analyzer-final/stock-boot-io-only/cycles.p1715
```

The first boot IACK produces an exact reference window of eight preceding records,
the IACK, and four following records, with no FPGA loss. Both untriggered boot
profiles still match the prior full filtered capture byte-for-byte. This replays
previously emulator-generated completed records through the FIFO/link and receiver;
it does not rerun RP2350 instructions or measure real hardware.
