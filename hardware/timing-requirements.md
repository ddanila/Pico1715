# Bus frontend and buffering requirements

> Historical modelling requirements. Current hardware choices and implementation
> are in [prototype.md](prototype.md), the [adapter schematic](interface/README.md),
> and [bench fixture](bench-fixture.md). Physical qualification remains open.


This is the implementation contract following the
[scheduled-byte experiments](../docs/timing-contract.md). It is not a released
schematic, component selection, or authorization to order a PCB.

## Deterministic path

| Function | Requirement for the first prototype | Acceptance evidence |
|---|---|---|
| /WAIT assertion | Decode the selected normal I/O transaction in hardware; assert before the actual CPU's sampling deadline. Do not wait for a C interrupt or SD operation. | Timing calculation using actual CPU, decoder and translator specifications, then scope capture at worst load |
| Read completion | Present stable data, enable the bus driver only for a selected read, then release /WAIT with CPU setup/hold satisfied. | Read timing and contention measurements |
| Write completion | Capture each accepted write once; release /WAIT only when its register has capacity. | Alternating-byte transfers and full-register backpressure |
| Byte pacing | Independent 31,250-byte/s producer/consumer, 32 us period; no accumulated per-byte rounding error. | Long transfers with zero lost/duplicated bytes |
| IRQ and acknowledge | Implement observed PIO vector programming, pending state, acknowledgement and RETI suppression; distinguish /M1+/IORQ acknowledge from normal I/O. | ROM index wait, SCP mark ISR and competing interrupt tests |
| Reset | Immediately release bus outputs and waits; cancel pending IRQ/transfer state; preserve only completed media updates. | Reset during read, write and stalled transaction |
| SD access | Keep storage latency outside the byte-service path. Prefetch and use RAM; define bounded cache-miss/error behavior. | SD stalls injected while unrelated bus and refresh activity continue |

One CPU tick is approximately 407 ns. A decode/assert path below one tick is an
initial engineering target only: the real deadline depends on when decode
inputs become valid and the CPU's /WAIT setup requirement. The emulator's
4.882 us clean read-latency point does **not** permit waiting that long before
asserting /WAIT. Determine the nanosecond budget before freezing parts.
Long waits are not a substitute for caching: the motherboard's DRAM refresh
must continue to meet its retention requirements. Measure maximum wait duration
and bound all error paths.

## Memory layout proposal

A track contains five 1,024-byte payloads (5,120 bytes). Including the model's
ID/data sync, marks and CRC requires 5,200 bytes before gaps. Reserve **8 KiB per
track buffer**, with an explicit bound on encoded gap layout, and **two buffers
(16 KiB)** for active and prefetched tracks. This is a proposed firmware budget,
not an assertion that the original track layout has been reproduced. Keep SD
block buffers, bus FIFOs, metadata and firmware memory separate in the budget.
A whole mounted image is **819,200 bytes (800 KiB)**; fitting that is an optional
external-RAM strategy, not a prerequisite for streaming cached tracks.

Use a small FIFO between the deterministic frontend and RAM/DMA service, but
preserve stock register/handshake semantics. Larger internal buffering must not
turn the visible controller into an unrelated FIFO device. The experiments show
that extra receive capacity alone does not cure sustained service delays.

Initially stage writes in RAM and expose coherent read-after-write behavior.
Specify when dirty sectors are flushed, how SD errors are reported, and what
survives power loss. The model's atomic sector commit and cold-reboot persistence
of an exported image do not establish SD durability.

## Pico PIO versus additional programmable logic

The proposed split is hardware address/control decode and fail-safe bus gating,
Pico PIO for deterministic register handshakes and byte transfer, DMA/RAM for
buffers, and ordinary firmware for SD/cache management. This is a hypothesis to
prototype, not an established pin-count or timing fit for a particular Pico.
Do not route the latency-critical path through ordinary firmware interrupts.

Before selecting a carrier, make a complete GPIO/state-machine/DMA budget for
address selection, data, /RD, /WR, /IORQ, /M1, reset, /WAIT, IRQ, interrupt-chain
handling, SD and external RAM. Validate voltage translation, power sequencing,
output enables and safe reset defaults. Keep the bus driver disabled when the
Pico is unpowered or resetting.

Use a CPLD or other dedicated frontend if the chosen Pico plus simple logic
cannot meet decode, interrupt-chain, output-enable or pin-count requirements.
The current tests do not justify either promising a Pico-only frontend or
mandating a CPLD. A small frontend prototype is the next decision gate.

## Gate before PCB order

1. Confirm the owner's mainboard revision and X2 orientation; resolve the
   existing interrupt-chain contact discrepancy against hardware.
2. Freeze the GPIO and electrical design, including power/reset states and
   CPU/translator setup/hold calculations.
3. Demonstrate selected read/write, /WAIT, IRQ acknowledge and reset on a bus
   fixture, then the machine; capture scope/logic-analyzer evidence.
4. Run stock boot, file creation/readback and fault recovery with real SD/RAM;
   measure worst-case latency under cache misses and storage stalls.
5. Only then freeze schematic, BOM, connector/mechanical drawing and layout;
   run ERC/DRC and manufacturing review before ordering prototypes.

The [executable frontend reference](frontend.md) now implements normal-I/O
decode, waits, read gating and mailbox fault handling. It provides a GPIO budget
and bench handoff; IRQ/RETI and physical timing remain open.
