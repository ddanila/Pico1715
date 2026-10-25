# Firmware storage and reset qualification

The combined path now exercises SD stalls, failed and torn writes, resets, and
journal recovery. Production firmware and FPGA logic are unchanged by this
milestone; the new mechanisms are host-side fault injection, deterministic
worker scheduling, assertions and reports.

## Evidence

* [42 scripted fault cases](../reports/firmware-storage-faults.json) drive real
  mailbox transactions through the board-level RTL and shared firmware. They
  need no external ROM or disk. The host is a scripted bus driver, not a CPU.
* [Three stock-ROM reset cases](../reports/firmware-reset-recovery.json) run the
  actual DAC Z80, unchanged ROM and SCP. Reset is triggered during a received
  field, a partial transmitted sector, or a suspended SD write. All reboot into
  SCP; successful SAVE results are independently compared with guest RAM.
* [Nine delayed stock-ROM cases](../reports/firmware-delayed-compatibility.json)
  repeat boot/DIR, writes, cold-reboot persistence, deletion, write protection
  and absent media with **5 ms per SD block write**.

The scripted cases cover:

| Injection | Required behavior |
| --- | --- |
| SD write stalls of 0, 100, 5,000 and 50,000 us | Serving-core mailbox requests continue; dirty blocks eventually drain and survive cold boot |
| Slow startup reads, 100 us per block | FPGA remains disabled until the entire cache is loaded |
| Reset while a read is waiting, or after 100 bytes of an incomplete write | Bus drivers/ACK release; incomplete sector is discarded without changing media |
| Host reset during each of eight SD operations for one sector | Dirty RAM and the worker survive; both blocks eventually persist |
| A newer sector write during an older block flush | Generation check retains the newer dirty block; another pass persists it |
| Failure at each of eight SD operations | Worker stops; firmware rejects further valid writes, including after host reset |
| Abrupt Pico power loss before each of eight SD operations | Worker stack is abandoned, PSRAM discarded, and startup replays any valid journal |
| Torn writes to payload, journal header, target or journal clear | Recover valid payload/target records; reject ambiguous metadata without further media writes |
| Read or write failure during journal replay | Backend stays disabled and journal survives for a later retry |
| Startup read failure at superblock, journal, first or last image block | No partially loaded cache is exposed |

Each 1,024-byte sector uses two 512-byte blocks. Each block's four SD writes are
journal payload, journal header, target block and journal clear. The suite checks
specific old/new bytes after restart, verifies the rest of the image is
unchanged, and independently constructs the sector CRC for bus writes.

## Execution model

The SD HAL exposes a hook before a transfer completes. Scripted tests use that
hook to run the serving loop and FPGA while the real storage function remains
suspended. They can issue another complete sector write during a flush. Abrupt
power loss uses `longjmp` across only trivial frames to abandon the worker before
an SD operation; unlike an I/O error, it never returns through the worker's
failure handler. A power cycle clears GPIO state and PSRAM but preserves the
entire SD block array, including journal metadata.

For stock software, a separate `ucontext` stack runs the production storage
worker. SD writes yield until their simulated deadline; normal CPU execution
continues on the caller stack. The clock remains monotonic across motherboard
resets. End-of-run export drains that same worker, never starts a concurrent
journal writer, and compares persisted SD bytes with PSRAM.

The reset probe now snapshots the real PSRAM cache. Its earlier comparison of
the original disk output buffer would not have proved firmware-cache preservation.
A reset during interrupt service may leave one more acknowledgement than RETI;
reset cancels that service rather than inventing a RETI.

## Reproduce

On Linux/POSIX with C/C++, Python and Verilator:

```sh
python3 tools/check_firmware_faults.py --out local/storage-faults
python3 tools/check_firmware_resets.py --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm --out local/storage-resets
python3 tools/check_classic.py --firmware-cosim --sd-write-delay-us 5000 \
  --dac ../dac-emulation --rom /path/r1715bt.bin --disk /path/r1715.cpm \
  --out local/storage-delayed
```

Output directories must be new. The 42-case suite also runs in CI. Stock-ROM
qualification requires the pinned clean DAC dependency and externally supplied
ROM/disk hashes. Input files are never modified. The raw probe additionally
accepts `PICO1715_RESET_PHASE=3` for a host reset while its worker is suspended;
use a nonzero `PICO1715_SD_WRITE_DELAY_US` and a workload that writes to disk.

## Durability and remaining limits

**Writeback remains experimental and disabled by default.** Guest writes finish
in PSRAM before SD persistence. A subsequent host reset preserves that cache;
a Pico power failure does not. Journal recovery protects one 512-byte block at
a time. It does not make an entire 1,024-byte sector, directory update or file
operation atomic. A power cut can therefore retain only part of a sector or lose
acknowledged but unflushed data. These tests document that boundary, not promise
filesystem consistency under arbitrary power loss.

A torn journal header/clear fails closed with startup state E2 and the backend
disabled; there is no automatic repair policy. Synthetic torn writes alter the
first 19 bytes of a block, not every possible SD-card failure pattern.

The worker interleavings are deterministic and occur at SD calls, outside the
image lock. This does not qualify instruction-level races, lock contention,
RP2350 execution time, physical SD/QMI behavior, bus electrical timing or analog
power sequencing. CTC/SIO interrupt-chain integration and broader OS coverage
remain useful emulation work.
