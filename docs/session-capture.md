# Session capture ABI 2

Both browser backends expose bounded passive capture through the actual cycle
encoder RTL. Start accepts byte capacity (8 KiB–64 MiB), mask 0x170 (I/O, IACK,
reset) or 0x3fe (all events), and a CPU-clock limit (zero disables the limit).
The browser defaults to 16 MiB and accepts time limits up to 120 seconds.
Status fields are state, stop reason, encoded bytes, records, CPU clocks sampled,
mask and capacity. States are empty/acquiring/complete/failed (0–3); stop reasons
are manual/size/time/fault (1–4). Data is available only after a successful drain.
Retrieve bounded slices from the returned buffer before release or another start.

The collector reserves 4224 bytes for FIFO and encoder drain. Reaching a storage
limit stops observation, not the guest. Capture is optional; the controller still
uses its original scheduling. The native callback oracle remains independent.
The common bus sampler reproduces the existing four illustrative samples per
CPU T-state and deferred-I/O WAIT seam. This is not half-cycle electrical timing.
A simulator reset is sidecar evidence, not an invented sampled CPU reset pulse.
Long gaps still have the compact format's less-than-one-counter-wrap limitation.

The browser attaches schema-1 metadata with capture/input SHA-256 values, exact
build manifest, backend, clock range, stop reason and bounded timestamped console,
reset and export observations. Console snapshots describe observations, not exact
transition times. Modified working media cannot select a qualified boot profile.
No input ROM or disk is transferred to the analyzer. Metadata and capture files
stay local; explicit download is needed for preservation.

Reproduce capture qualification:

```
python3 tools/build_browser.py --native --out build/browser-native
python3 tools/build_browser.py
python3 tools/check_session_capture.py --build build/browser-native --out local/new-capture-check
node tools/browser/check-capture.mjs build/browser local/new-capture-check
```

The synthetic program checks full/I/O modes, size/time stops, reset and empty
captures, Python format validation, unchanged guest registers/RAM and exact
native/WASM bytes for both backends. Existing full-OS parity and native analyzer
callback-oracle checks remain separate requirements.
