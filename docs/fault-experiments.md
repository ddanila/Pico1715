# Scheduled simulation fault investigations

The experiment schedule accepts `fault` actions with a named fault and bounded
integer value. These APIs are compiled into the session tools, not physical
firmware. The session ABI remains version 2 with discoverable optional
`sim_config`, `sim_capabilities` and `sim_fault` exports; old engines cannot silently
accept new fault actions.

| Fault | Value | Backend |
| --- | --- | --- |
| crc | 0/1; corrupt subsequently generated field CRCs | both |
| drop-byte | 0 disables; otherwise 1–1030 selects a field byte | both |
| read-delay / write-delay | 0–2458000 CPU clocks | both |
| write-protect | 0 restores initial policy, 1 protects | model |
| sd-delay | 0–1000000 microseconds for subsequent SD writes | firmware |
| sd-write-failure | 1 fails the next SD write, 0 clears injection | firmware |
| power-fail | 1 requests shutdown on the next serving-core poll | firmware |

Firmware write protection is an initial read-only mount policy; a caller cannot
change it across a suspended image-lock owner. Power failure is a queued request,
not an instantaneous hardware voltage event. Fault-state observations include
shutdown/reason, SD reads and the active CRC/drop/read/write-delay settings.
An `absent: true` experiment configures absence before session initialization.
Native adapters remove ambient `PICO1715_*` variables so an unrecorded environment
fault cannot alter replay. The controller's production timing and shutdown gates
remain in force.

## Paired CLI investigation

With sibling `dac` present (the same browser assertion engine is imported):

```
node tools/browser/fault-investigation.mjs build/browser-native/pico1715-model.so model ../cpm-plus-1715/build/test.rom ../cpm-plus-1715/out/cpm-plus-1715.img crc local/new-crc-investigation
```

Arguments after the new output directory are an optional ASCII command, end
clock (default 40M), fault clock (default zero), and maximum reduction attempts
(default zero, at most eight). Commands are queued at 30M clocks. Presets include
the table's CRC/drop/delay/storage/shutdown cases and initial `absent`/`readonly`.
Use the firmware backend for SD and power-fail scenarios. A delay or write-failure
scenario without writes may never exercise its injected condition; configuration
alone is not evidence that it took effect.

The runner preserves a fault-free control, the fault experiment, capture bundles,
exact end-state checkpoints, screen contents and session-visible output images.
It uses the analyzer's shared integrity assertions, retaining inconclusive results.
It reports the first observed violation separately from a conclusive failed rule:
for example a bad ID CRC can make subsequent data-length decoding uncertain.
Neither finding is automatically a root-cause claim. Missing required events have
no invented record location. Images are not implicitly flushed; SD durability and
unrelated-file preservation require the separate guest/host storage oracle.

Optional reduction removes only key/cancel actions, preserves the original, and
accepts candidates only when the same rule, outcome and reason recur. Every
attempt retains its evidence; this is bounded script reduction, not a proof of a
minimal reproducer. A control with the same signature prevents reduction.

The browser exposes the same named faults through **Run fault experiment from
boot**, uses the current initial media, finishes paused, and displays shared
assertion outcomes. The paste box supplies the optional 30M-clock command.
Its exported bundle retains the original experiment and report; CLI paired runs
provide the corresponding control comparison.
