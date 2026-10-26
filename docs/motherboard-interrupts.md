# Card–CTC–SIO interrupt-chain qualification

The pinned DAC revision now provides an opt-in classic-1715 CTC/SIO interrupt
model. Priority follows the original-board wiring resolved in
[X2 contact evidence](../hardware/x2-pinout.md): floppy card, four CTC channels,
then SIO A receive/transmit/external and B receive/transmit/external. Acknowledge
chooses one eligible source; RETI releases one in-service owner. Higher-priority
sources can nest over lower-priority handlers; an in-service source blocks itself
and lower priorities. Onboard port decoding owns 08h–0Fh in enabled mode.

This removes the old assumption that every acknowledge and RETI belongs to the
floppy card. `pc1715_card_quiesce` releases an isolated card's bus and chain
ownership until board reset, allowing pending CTC/SIO requests to proceed. It is
an emulator seam, not an automatic storage flush: callers must coordinate with
the [shutdown contract](shutdown.md). If a card is removed while its CPU ISR is
still executing, that routine remains on the CPU stack; later RETI propagation
can affect downstream owners exactly as releasing a physical chain would.

## Reproduce

```sh
make -C ../dac-emulation test-pc1715
make -C ../dac-emulation test-runtime-sanitize
python3 tools/check_motherboard_chain.py --dac ../dac-emulation \
  --out local/new-motherboard-chain
```

The integration checker requires the clean pinned DAC revision, uses no private
ROM/disk images, builds with UBSan, and is now part of Pico1715 CI. Its original
synthetic Z80 IM2 program runs the **actual Pico1715 controller model**, alongside
CTC and SIO. Simultaneous requests yield vectors 10h (index), 12h (mark), 40h
(CTC) and 6Ch (SIO A receive). Each ISR runs once, the receive ISR consumes its
byte through real IN, and each RETI clears the proper owner. Another test isolates
an active card, services the downstream devices and resets the board.

DAC's native regression additionally exercises higher-priority nesting,
independent in-service owners, all six ordinary SIO vector classes, stray RETI,
reset during service, CTC prescale 16/256, external timer start, falling-edge
counter inputs, constant zero as 256 and timer progress during card WAIT. A
synthetic guest programs the CTC through actual OUT instructions and takes
repeated IM2 interrupts. The shared runtime and plain-board sanitizer suites pass.

[Combined-controller report](../reports/motherboard-interrupts.json) records the
revision, source hashes and result. The existing nine-case external ROM/SCP
regression also passed against this pin; see
[compatibility report](../reports/motherboard-compatibility.json). These historical
workloads retain their existing polled keyboard fixture, so they demonstrate
backward compatibility, **not** full OS qualification of the new SIO model.

## Scope and remaining work

Enable the new peripherals with `pc1715_onboard_enable` before CPU execution.
Legacy mode is unchanged by default to preserve existing external keyboard
fixtures. The native board struct changed; external clients must rebuild.

CTC timer/counter and SIO interrupt-register behavior are sufficient for the
qualified arbitration cases. Serial input uses a completed-byte seam; TX
completes on the next peripheral tick. This does not yet model serial waveforms,
CTC-to-SIO baud wiring, full modem/status latching, special-receive vectors,
exact FIFO-overrun behavior, synchronous serial modes, X1 expansion devices or
CRT/display. See the pinned emulator's `machines/robotron1715/interrupts.md` for
exact supported registers, exclusions and primary-source references.

The **card–CTC–SIO arbitration milestone is complete at register level**. Full
motherboard peripheral emulation, migration of the stock keyboard fixture and
physical daisy-chain propagation/electrical timing remain separate work. Nothing
here qualifies PCB mechanics, power sequencing or actual interrupt latency.
