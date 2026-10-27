# Desk-work results, 2026-10-27

The carrier now has 23 additional ground stitches and a reproducible geometric
[routing review](../hardware/carrier/routing.md). Long clock/control routes and
parallel runs are explicitly flagged; this is not measured electrical signoff.
The canonical board retains 12 SD opens and an unplaced X2 connector.

The [SD review](../hardware/carrier/sd-review.md) adds visually inspected catalog
evidence. The full engineering drawing was inaccessible, so routing release is
still blocked on its detailed mechanical/exclusion comparison.

A [separate provisional X2 breakout](../hardware/x2-adapter/README.md) now has a
schematic, local footprints, 58 isolated routed paths, a contact/harness map and a
1:1 template. KiCad reports zero violations, opens and schematic parity issues.
Physical contact orientation/fit and host installation remain unverified.

The [assembly plan](../hardware/carrier/assembly.md) and generated component/pad
locator cover polarity, probe points, programming and staged interlock/host tests.
They are preparation for hardware; no bench result has been filled in.

## Extended media test

[Recorded results](../reports/extended-media.json) contain 30 native functional
controller runs. Six unchanged external images are surveyed read-only for 100M
CPU cycles each. `r1715.cpm` and `anasana.cpm` reach SCP 0006; these are different
disk contents, not proof of two supported OS versions. Each gets three rounds of
96-record (12 KiB) guest writes and reads, independent host payload checks,
read-only cold-boot TYPE, deletion and cold-boot confirmation of deletion.

The original images are hash-checked before and after. The temporary workload
chooses a free allocation block, so an occupied block 62 on the additional image
is preserved. `r1715ms.cpm`, `r1715mt.cpm`, `scp3.cpm` and `scp30.cpm` do not reach
a prompt within the bound; their cause is not diagnosed or waived. This suite
uses scheduled byte timing and transaction waits, not RTL or Pico instruction
execution. Existing RTL/shared-firmware qualification remains separate.

External copyrighted ROM/images are not redistributed. With the inputs listed
in `tests/extended-media-inputs.json` and the pinned clean DAC checkout:

```sh
python3 tools/check_extended_media.py --dac ../dac-emulation \
  --rom /path/to/r1715bt.bin --images /path/to/r1715fdd \
  --out local/extended-media-new
make test-desk-review test-x2-adapter-cad
make test-carrier-schematic test-carrier-footprints test-carrier-pcb test-carrier-layout-cad
```

The output directory must be new. The report distinguishes unqualified media from
passed workload cases. Repeated identical record payloads do not cover all data
patterns, and completed disk-file writes do not prove physical SD power-loss
behavior. Next software work can investigate the four non-prompt boots; next
release work needs the SD drawing and actual connector/module measurements.
