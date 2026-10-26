# Analyzer mode and remote reset

## Purpose and explicit modes

Add a USB-connected bus analyzer to Pico1715 so the fitted card can capture boot,
I/O and interrupt activity without individual probe wires. The [standalone capture prototype](analyzer-prototype.md) now implements raw
triggered buffering and host file export. A second [compact personality](cycle-analyzer.md)
adds cycle intervals, filtering and stock-boot verification against the emulator. This document remains the full feature
plan: board integration, USB transport and remote reset are not implemented yet.

- **Controller:** existing floppy replacement behavior.
- **Analyzer:** passive capture only; no floppy responses, data drive, /WAIT,
  /INT, /BUSRQ, /NMI or memory-inhibit assertion. Preserve the required interrupt
  chain with a reviewed bypass; simply disabling its output can break the host.
- **Controller plus trace:** later option, with explicit capture/storage bandwidth
  budgets so observation cannot compromise floppy deadlines.

Select the mode before arming. Reject mode changes during active capture or
controller transactions; define a quiescent transition with all drivers disabled.
Hardware output gating must enforce analyzer isolation during startup, reset,
USB disconnect and FPGA reconfiguration, independently of Pico software.
Passive mode cannot replace the missing floppy controller: a bare machine's boot
attempt will be observable but will not acquire a virtual disk from this mode.

## Capture architecture

Host bus -> TTL-compatible receivers -> FPGA timestamp/trigger/FIFO -> Pico ->
PSRAM capture buffer -> USB host. The FPGA handles acquisition; USB and host
scheduling must never stall the motherboard. Keep acquisition alive across host
reset so the trace contains reset assertion, release and the first bus cycles.
Card power/reset and observed host reset must be separate in this mode.

First target: finite, triggered captures with pre/post-trigger history and
stop/download operation. Add filtered streaming only within measured throughput.
Provide address/data masks, memory/I/O read/write, opcode-fetch, interrupt-ack
and reset triggers. Include timestamps, raw control levels, capture configuration,
sequence numbers and explicit overflow/gap markers; never silently lose records.
Offer decoded bus transactions and raw sampled windows, with documented sampling
phase and data-valid rules. Do not label every /M1 assertion an opcode fetch:
interrupt acknowledgement and refresh need their own decoding.

Expand the receiver/pin budget to A0–A15, D0–D7, /MREQ, /IORQ, /RD, /WR,
/M1, /RFSH, clock, /RESET, /WAIT and /INT; assess /BUSRQ, /BAO and priority-chain
observation too. The current adapter only receives A0–A7 and leaves upper address,
clock and refresh contacts unconnected. Full address capture therefore needs a
schematic, connector-netlist and FPGA pin-allocation revision, not just firmware.
X1/X2 clock and priority contacts have slot-specific meanings; use the documented
mapping rather than treating the slots as interchangeable.

Budget raw storage and transfer before choosing sample rate: an illustrative
40-bit record at 50 MHz is 250 MB/s before framing, far beyond Pico USB full-speed
streaming. An 8 MiB buffer would hold only about 34 ms at that rate, even if its
write bandwidth were sufficient. Use FPGA-local buffering, compact cycle records,
filters and bounded bursts; PSRAM capacity is not proof of acquisition bandwidth.
Keep disk-cache and trace allocations separate in combined mode. Provide a host
CLI for arm/stop/download, a versioned binary format and VCD/CSV export; waveform
viewer integration can follow without making it a first-release dependency.

## Remote CPU reset: separate optional connection

**X1 A20 and X2 A20 do not directly reset the CPU on the documented index-2B
motherboard.** The connector table calls A20 `/RESET`, but the original ZRE
sheet 1.93.300101.5/04 (PDF page 7 in the locally recorded original drawings)
and the [Zander redraw, sheet 1](https://www.sax.de/~zander/pc1715/pc_zres.pdf)
show it on `/RESET2` (sheet reference 20). CPU A27 pin 26 is on the separate
`/RESET1` branch (reference 12). A32 has distinct output stages for these nets;
the shared reset generator does not make the outputs interchangeable. Pulling
A20 low must not be advertised as a CPU or whole-machine reset.

Plan an optional two-wire connection across RESET-TASTE, using an electrically
reviewed isolated contact closure or suitable transistor interface. This invokes
the motherboard reset generator instead of forcing its output nets. Verify switch
voltage/current and pulse requirements before component selection. Keep A20 as an
observed input on the card; do not add a CPU-reset driver to that contact.

Expose explicit reset and arm-then-reset commands, available only when the reset
accessory is enabled. Default to released; bound the pulse independently of USB
traffic, and ensure disconnect, firmware failure or reconfiguration cannot leave
reset asserted. USB connection alone must never reset the host. Record command,
assertion and observed release in the trace; do not claim a CPU reset was observed
solely from A20. Reset is not power cycling and must retain the controller's
existing dirty-data semantics. If a requested flush fails, report it instead of
silently treating reset as a safe shutdown. Review USB/host power isolation so a
USB-powered analyzer cannot backfeed an unpowered motherboard.

## Desk acceptance and bench gates

1. Freeze acquisition signals, mode isolation, reset accessory and transport
   contracts; update the schematic and pin/resource budgets.
2. Test FPGA capture against known CPU traces: memory/I/O, fetch, refresh, IACK,
   waits, back-to-back cycles, timestamps, trigger boundaries and FIFO overflow.
3. Verify passive mode never drives the bus, preserves the interrupt chain and
   does not reset its capture buffer when the host resets. Test USB backpressure,
   disconnect, mode-transition rejection and reset pulse timeout.
4. Compare decoded captures with emulator traces and document reconstruction
   limits. Execute host-side export/protocol tests with synthetic recordings.
5. On hardware, measure receiver loading, timing, sustainable capture bandwidth,
   safe power sequencing and actual reset behavior before enabling host reset.
