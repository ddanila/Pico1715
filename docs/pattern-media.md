# Indexed records, extent boundaries and disk-full handling

The new original MIT BDOS workload generates a different 128-byte record for
every record index. It writes and rereads 256 records (32 KiB), crossing the
16 KiB extent boundary. Two seed patterns are used. An independent host parser
checks extent ordering, allocation bounds and exact file contents. Cold-boot
runs use a read-only guest verification program, not merely a directory listing.

A negative control flips a payload byte: the guest must report failure while the
read-only disk image remains unchanged. A separate fixture occupies free blocks
with valid dummy directory allocations, leaving ten blocks for the test file.
The guest must receive BDOS disk-full status after 160 records, close the partial
file and preserve all 160 records through cold boot. No original file allocation
is overwritten and the input image is hash-checked before and after.

All seven cases passed with the native functional controller and again with the
shared Pico service/storage code plus Verilated FPGA frontend. See
[native results](../reports/pattern-native.json) and
[shared-firmware results](../reports/pattern-firmware.json). The deliberate
corruption case passes only when corruption is detected; it is not a successful
read of corrupt data. These runs retain scheduled byte timing and transaction
waits, but do not execute RP2350 instructions or model measured SD latency.

```sh
python3 tools/build_cosim.py --dac ../dac-emulation --out local/pattern-build --firmware
python3 tools/check_pattern_media.py --binary local/pattern-build/classic-probe \
  --rom /path/to/r1715bt.bin --disk /path/to/anasana.cpm \
  --out local/new-pattern-run --backend shared-firmware-rtl \
  --report reports/pattern-firmware.json
```

The external image and ROM must match the recorded hashes. Fixtures and binary
outputs remain local; copyrighted input media are not redistributed. Portable
unit tests check record uniqueness, malformed extents, duplicate allocations and
the deliberately limited free-block count without requiring external media.
