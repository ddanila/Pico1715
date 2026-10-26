# Executable passive analyzer prototype

`hardware/rtl/analyzer_top.v` implements a standalone analyzer personality, not
an option wired into the floppy-controller top. It has no host-data output and
holds all host drive enables/pull-down requests low, including reset. IEO follows
IEI combinationally. Physical bypass/output gating during power loss or FPGA
configuration still belongs to the adapter design; RTL cannot guarantee it.

The implementation provides finite raw captures with level/mask triggering,
pre/post-trigger samples, synchronous frozen-buffer download, a binary capture
format and CSV/VCD export. It does not yet implement USB commands, Pico firmware,
PSRAM streaming, combined controller/trace mode, remote reset or completed bus-cycle
reconstruction. The [feature plan](analyzer-mode.md) remains the wider scope.

## Acquisition contract

All command/configuration signals are synchronous to `clk`. Pulse `arm` for one
clock while inactive; configuration is latched. Capture starts on the following
edge with tick zero. `PTR_BITS` sets depth to 2**PTR_BITS (default 256). Require
`pre_samples + 1 + post_samples <= depth`; invalid configuration or simultaneous
arm/stop sets `config_error` and leaves acquisition inactive. Arming while active
sets sticky `command_rejected` and does not change the running capture. Both
flags clear on the next inactive arm or card reset.

The trigger is `(sample & mask) == (value & mask)`; zero mask triggers on the first
sample. This is a level trigger, not edge detection. Before a match, retain only
the most recent `pre_samples`. On the matching sample, latch `trigger_index` to
the amount of history actually retained, then acquire exactly `post_samples`
more samples and freeze. An early trigger can produce less than the requested
history. Ring overwrite before trigger is intentional; the frozen capture never
overwrites unread records and does not depend on download speed.

`stop` has priority over sampling and freezes the existing records with `stopped`
set. It may produce zero records, an untriggered history, or a shortened posttrigger
window. A 32-bit tick wraps modulo 2**32 (about 85.9 seconds at 50 MHz). Captured
records remain consecutive modulo this wrap; tools reject missing/duplicate ticks.

After `done`, assert `read_enable` with a logical `read_index` from zero through
`count-1`. On the next rising edge, `read_valid` and `read_record` describe that
record, oldest first. The record is `{tick[31:0], sample[39:0]}`. Out-of-range
reads, reads during acquisition, and reads on an arm edge have no valid response.
Ignore `read_record` when `read_valid` is low. Rearming discards the previous
capture. RAM contents are not reset; metadata prevents access to stale records.

Only `card_reset_n` resets capture state. Host reset is an observed sample bit,
so it cannot erase a boot trace. Card reset release must meet the acquisition
clock's recovery/removal requirements; a board wrapper must provide this.

## Sample layout

| Bits | Signal |
| --- | --- |
| 15:0 | A0–A15, numerical address |
| 23:16 | D0–D7, numerical data |
| 24–29 | /MREQ, /IORQ, /RD, /WR, /M1, /RFSH |
| 30 | Host clock |
| 31–35 | Connector /RESET, /WAIT, /INT, /BUSRQ, /BAO |
| 36–37 | IEI, IEO |
| 38–39 | Reserved, supply zero |

The core samples levels on each acquisition clock edge. This fixture uses 50 MHz;
it is not a qualified sampling rate. A physical wrapper needs receiver timing,
clock constraints and an explicit asynchronous-bus sampling/CDC review. Samples
near transitions may be ambiguous. The CSV labels describe sampled bus states,
not completed transactions or guaranteed valid data. For the separate compact
interval encoder and boot comparison, see [cycle capture](cycle-analyzer.md). `/M1 + /IORQ` is classified
as interrupt acknowledgement; refresh is separate from opcode fetch. Unknown
memory mapping and internal CPU state cannot be reconstructed from every sample.

## Frozen capture file, version 1

Little-endian header (`<8sHHIIIIIIQQ`, 52 bytes): magic `P1715LA` plus NUL,
version 1, record size 12, sample-clock Hz, record count, trigger index, flags,
configured pre/post sample limits, trigger mask and trigger value. Trigger index
is `0xffffffff` if absent; flag bit 0 means triggered, bit 1 means stopped. Other
flags and reserved sample bits must be zero. Each record is `<IQ`: 32-bit tick,
64-bit container for the 40-bit sample. Upper container bits must be zero.

The file parser rejects unknown versions, inconsistent lengths/flags/trigger
positions, invalid limits, sequence gaps and reserved bits. This file format is
not a USB framing/checksum protocol. CSV/VCD time starts at the first retained
sample; CSV also preserves tick32. VCD uses integer picoseconds. The trigger is
exported as a separate pulse. A future streaming format needs explicit gap records;
this format only accepts complete contiguous frozen windows.

## Reproduce and inspect

```sh
make test-analyzer lint-analyzer synth-analyzer
python3 -m unittest discover -s tests -p test_analyzer.py -v
python3 tools/check_analyzer.py --out local/analyzer-check.json
```

`make test-analyzer` writes synthetic `build/analyzer.p1715`, `build/analyzer.csv`
and `build/analyzer.vcd`; the latter opens in a VCD waveform viewer. These are
simulation fixtures, not motherboard captures. To export another frozen file:

```sh
python3 tools/analyzer_trace.py export capture.p1715 --csv capture.csv --vcd capture.vcd
```

The [recorded desk check](../reports/analyzer-prototype.json) covers 198 directed
checks and 160 seeded captures comparing 1,624 records with an independent list
model. Cases include wrapped history, early/immediate triggers, maximum capacity,
invalid configuration, active rearm, stop priority, observed host reset, frozen
readback, passive outputs and priority bypass. Host tests cover file corruption,
timestamp wrap, sample-state classification and exports. CI repeats these checks.

Default synthesis uses five iCE40 4-Kbit RAM blocks and 283 LUT4s with the recorded
toolchain. The 256 samples span only 5.12 microseconds at 50 MHz. This validates a
small capture primitive; useful long boot traces need compressed/cycle records
and/or sustained transport into PSRAM. Synthesis is not placement/routing or a
50 MHz timing qualification. The [compact cycle personality](cycle-analyzer.md) now adds emulator-driven
boot verification and filtered interval records. Next integration work is a
transport/register wrapper, receiver/pin assignment and Pico USB/PSRAM implementation. No production bitstream or hardware reset driver
is supplied by this milestone.
