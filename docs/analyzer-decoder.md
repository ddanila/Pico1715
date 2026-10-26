# Classic PC1715 trace decoder

`tools/analyzer_1715.py` interprets compact v1/v2 captures using the implemented
classic controller contract in `model/controller.c`. It covers drive selection,
control transitions, head/step requests, write gating, status bits, PIO vector and
interrupt programming (including direction/mask follow-up words), interrupt
acknowledgements, and MFM ID/data fields with CRC-16 checks. This is the original
1715 controller subset, not the 1715W/M 8272 protocol.

```sh
# Show a timeline around the recorded trigger, or the beginning of a v1 capture.
python3 tools/analyzer_1715.py capture.p1715
# Inspect a particular record and export every annotated cycle for other tools.
python3 tools/analyzer_1715.py capture.p1715 --center 100 --context 12 \
  --events capture-events.jsonl --json
# Compare complete observed I/O sequences, ignoring capture clock differences.
python3 tools/analyzer_1715.py capture.p1715 --reference reference.p1715 --json
# Compare from each capture's own trigger; explicitly opt into timing checks.
python3 tools/analyzer_1715.py capture.p1715 --reference reference.p1715 \
  --align trigger --timing-tolerance-us 2
```

Summary JSON contains source SHA-256, counts, CRC results, diagnostics and a
bounded timeline. JSONL export streams all records, preserving full address,
sequence, tick, duration, WAIT samples, flags, gaps and trigger position. Exports
require a new output file and cannot overwrite either input. The input streams
are fully validated, including tails after a comparison divergence. Exit codes
are 0 for decoding/matching, 1 for comparison mismatch (including empty selected
streams), and 2 for invalid input or invocation.

Comparison retains I/O, interrupt acknowledge, reset and invalid cycles. It uses
kind, data and flags, and the low eight I/O address bits decoded by this machine.
It excludes memory and refresh, does not silently resynchronize, and reports both
record indices at the first divergence. Use these indices with `--center` to
inspect either timeline. Default alignment starts at the first retained event;
trigger alignment explicitly excludes both pre-trigger histories. Unequal tails
fail comparison. Timing is optional: tolerance applies to elapsed time from the
first compared event, cycle duration and accumulated WAIT time, converted to
microseconds using each capture's clock. This measures cumulative drift as well
as individual cycle timing; it is not a gate-level timing qualification.

`--wait-budget-us` and `--gap-budget-us` flag configured limits. There is no
invented universal controller timeout: an idle interval may include normal CPU
work, filtered traffic, or intentional delays. WAIT samples are the record's
accumulated count, not necessarily one contiguous assertion. Saturated/partial
cycles invalidate inferred state instead of supplying precise controller claims.

State starts unknown, including for cropped windows. Observed reset clears
inference; it does not establish that CPU RESET1 was asserted. Sequence gaps may
be filtering, omitted trigger history or transport loss. If the header reports
any loss, every gap conservatively clears state because the file cannot locate
which gaps lost data. Without reported loss, filtering alone preserves state.
Partial/address-changing cycles also clear state. Status values are reported
without inferring unobserved physical media or cylinder position. A TX-register
load with the write gate closed is ignored by the model and is normal during ROM
initialization. CRC failures and incomplete observed writes are diagnostic facts,
not proof that SD persistence failed. Field decoding requires an observed valid
ID for data length and supports 128–1024-byte sectors; other formats remain outside
the modeled subset. Bus bytes cannot reveal FIFO overruns that repeated identical
bytes conceal, or guarantee disk persistence.

Time unwrap assumes less than one 32-bit timestamp wrap between adjacent captured
records (about 85.9 seconds at 50 MHz). Equality means equality of the selected
observations, not proof that either file is complete. Inspect dropped counts and
capture masks before drawing conclusions. Capturing only reads omits the writes
needed to interpret control transitions.

## Desk verification

Nine automated tests exercise known ID CRC DA4E, payloads containing sync-like
bytes, corrupt CRC, unknown field length, PIO follow-up priority, partial writes,
uncertain cycles, filtering versus loss, clock wrap, budgets, normalized clocks
and ports, divergent/unequal/invalid tails, trigger alignment and CLI protection.
They run in `make test` without private images or hardware.

[The recorded boot analysis](../reports/analyzer-decoder.json) additionally checks
the existing 215,848-record emulator capture and its transported copy, and decodes
the 13-record trigger window. Source captures remain local; their hashes are
recorded. This validates interpretation of emulator evidence, not physical bus
capture accuracy or a complete controller implementation.
