# Shared firmware co-simulation

The stock plain-1715 ROM and SCP run through the same firmware service loop that
is built for the Pico Plus 2, connected to the board-level FPGA RTL. The
[compatibility report](../reports/firmware-compatibility.json) records nine cases,
source hashes, independent mailbox-response counts and firmware storage counters.
That historical run used the legacy keyboard stub. The new
[onboard SIO run](onboard-keyboard.md#firmware-timing-failure-exposed-by-migration)
exposed an index/mark collision with a one-byte queue. The
[two-byte firmware follow-up](receive-elasticity.md) passes all nine stock cases
and adds ROM-free phase and overload regressions.
The ROM and BIOS are unchanged and are not redistributed.

## Execution boundary

`firmware/main.c` initializes the service and repeatedly calls
`p1715_service_step()`. `firmware/service.c` contains startup, PSRAM image loading,
controller ticks, GPIO direction changes, request/acknowledgement sequencing,
interrupt toggles, reset handling and the dirty-block worker. Both the Pico build
and host simulator compile this file, `store.c` and `model/controller.c`.

The host simulator supplies the Pico SDK peripheral operations through
`firmware/platform.h` and `tools/firmware_host/host_hal.*`. Its SD block device is
separate from PSRAM, with a real superblock and redo-journal area. Startup loads
all 1,600 blocks through the production storage code. Guest writes reach the
production worker and journal before the exported image is read from SD. The
runner rejects a difference between PSRAM and persisted SD at the end of a
successful run. Input images are never modified.

`firmware_cosim_top.v` wraps the unmodified `pico1715_top.v`, including its 100 MHz
clock divider, vector mirrors and synchronized interrupt inputs. It resolves the
shared data bus and detects simultaneous FPGA/Pico drive. The C++ bridge routes
pin values and advances the firmware; it never calls controller read, write,
tick, wait, acknowledge or RETI functions directly. A separate count of rising
GPIO ACK signals must match the firmware's serviced-request count.

DAC exposes deferred normal I/O separately from observed CPU pins. The wrapper
selects the deferred transaction for ordinary I/O and observed fetch/IACK pins
for interrupt recognition. Observed normal I/O is suppressed to prevent replaying
a transaction. When firmware startup fails, the backend remains disabled and
undriven host reads return FF, representing pull-ups.

## Reproduce

With the pinned clean DAC checkout, C/C++ compilers and Verilator:

```sh
python3 tools/check_classic.py --firmware-cosim --dac ../dac-emulation \
  --rom /path/r1715bt.bin --disk /path/r1715.cpm --out local/firmware-check
```

The output directory must not already exist. The suite checks boot/DIR, SAVE,
saved-file persistence, a BDOS read/write/compare workload, TYPE after cold boot,
deletion and its persistence, write protection, and absent media. Each restart
loads the exported SD image into a fresh firmware instance. File contents are
also checked independently of the emulated OS.

Portable startup/reset/handshake tests and a small original Z80 mailbox program
run in CI without proprietary inputs:

```sh
make test-firmware-service
python3 tools/build_cosim.py --firmware --dac ../dac-emulation --out build/fw-sim
python3 tests/firmware_cosim_smoke.py build/fw-sim/classic-probe
```

The synthetic program deliberately has no OS handoff. It tests four actual CPU
I/O transactions, storage startup and unchanged media. The full compatibility
suite still requires the externally supplied ROM and disk.

## What remains outside this proof

This is host compilation of shared production C, not execution of the ARM ELF or
UF2. SD SPI commands, CRC transport, QMI/PSRAM signalling and Pico SDK multicore
machinery are replaced by deterministic host operations. By default SD block transfers complete immediately. With
`--sd-write-delay-us`, each worker write yields on a separate POSIX `ucontext`
stack while the emulated CPU, FPGA and serving loop continue. A dirty worker
starts at a 100-microsecond polling boundary. Interleaving occurs at SD operations
outside the image lock; locking is consequently uncontended. The host clock
remains monotonic across 1715 resets so pending SD deadlines remain meaningful.

The firmware polls on changes of the microsecond timer, quantized to CPU ticks.
Idle FPGA clocks can be skipped once the normal mailbox has settled; observed
CPU bus transitions still advance the RTL. This proves functional sequencing,
not firmware execution-time bounds, full CDC behavior, or physical /WAIT margins.
The motherboard now enables modeled CTC/SIO, with completed keyboard bytes
entering the real SIO FIFO. [Keyboard migration tests](onboard-keyboard.md) record
functional/timed passes and the firmware failure/fix history; [chain tests](motherboard-interrupts.md) separately cover
interrupt priority and nesting. Serial wire timing remains outside this profile.

The [storage/reset qualification](firmware-storage-faults.md) adds delayed stock-OS
workloads, three stock-ROM reset scenarios and 42 scripted firmware/RTL fault
cases. Full instruction-level multicore interleaving, wider OS coverage and
physical measurements remain separate work. The legacy controller-only timing
injection options are not firmware-storage fault controls.

## Nonzero service-cost experiments

The separate [ROM-free service-cost harness](service-costs.md) pauses production
firmware at controlled work sites while the FPGA and the other core continue.
It models image-lock ownership and measures byte-loss and watchdog boundaries.
The [stock CPU bridge now supports the same cost sites](cpu-service-costs.md),
including combined costs, delayed SD and actual image-lock contention. Zero
costs remain the default. Historical delayed-SD reports used zero service costs. The new request-liveness checks
prevent a delayed operation from publishing an ACK after observed cancellation.
