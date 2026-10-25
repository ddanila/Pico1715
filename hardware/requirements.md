# Hardware draft — no component or pin assignment is frozen

> Historical modelling requirements. Current hardware choices and implementation
> are in [prototype.md](prototype.md), the [adapter schematic](interface/README.md),
> and [bench fixture](bench-fixture.md). Physical qualification remains open.


## Agreed scope

- X2-connected replacement for the absent original floppy controller.
- Plug-in Pico-family module, microSD and fitted external RAM.
- Buffered 5 V host / 3.3 V card interface, controlled data direction and output
  enables; host bus must not be driven during Pico reset or startup.
- Stock-ROM and stock-OS virtual floppy compatibility. Physical floppy drive
  electronics are outside the initial scope.
- External RAM initially holds disk/track cache and device state. Exposing it as
  banked host memory is a later, separate feature.
- USB programming/debugging, test points and provision for power-source isolation.

## Decisions to make after modelling

The exact Pico variant, GPIO allocation, RAM technology/capacity, SD interface,
logic families and connector footprint remain open. 8 MB PSRAM is a candidate,
not a confirmed part. Do not share SD and latency-critical RAM traffic without
analysing worst-case contention. A full track/image cache may hide SD stalls,
but cache size alone does not prove controller compatibility.

The ordinary 1715 X1/X2 manual has 29 contacts in each of rows A and B. Previous
transcriptions have an IEI location discrepancy against the index-2B schematic.
Confirm row orientation, IEI/IEO, BAO, signal direction, open-collector behaviour,
straps and board revision from primary documents before assigning nets.
Do not apply that connector table blindly to a W/M board.

Budget /WAIT assertion against the CPU sampling deadline, including decode and
level-translation propagation; release safely. Do not use long CPU stalls for
arbitrary SD transactions. Account for /M1 interrupt acknowledgements separately
from ordinary /IORQ reads and writes, and verify PIO interrupt-chain requirements.

Do not substitute emulated RAM for display-accessed RAM until memory inhibition,
display fetches and bus arbitration are understood. A successful software boot
does not establish electrical safety or timing margin.

See [timing and buffering requirements](timing-requirements.md) for the scheduled-byte
results, proposed 16 KiB track buffering, frontend split and measurement gates.
