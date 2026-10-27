# Deterministic classic-session experiments

The shared `tools/browser/experiment.mjs` orchestrator uses the existing session
ABI in native libraries and WebAssembly. It does not save or restore internal
machine snapshots. Every replay starts with a newly initialized machine at clock
zero. Inputs and the engine are identified by SHA-256. Model and firmware remain
distinct backends; their internal checkpoints are not interchangeable.

Schema 1 records ordered actions at absolute CPU clocks: key, cancel, reset,
capture-start/stop/release, explicit disk export and checkpoint. Same-clock actions
retain array order. Scheduling splits execution budgets before each action.
Breakpoints are disabled during replay; rendering and wall-clock speed are absent
from the schedule. A 120-second simulated-time limit and 10,000-action limit bound
the first version. A recording that exceeds either limit cannot be exported as a
valid experiment.

Checkpoints include registers, diagnostic counters and hashes of RAM, text memory
and the session disk image. They never call disk export or flush storage. The
firmware's pending writes therefore remain pending. Explicit export records how
many bounded export calls occurred; each call's completion result is checked on
replay. Export can advance CPU clocks while reaching an instruction boundary and
can progress storage while CPU clocks stay fixed. Later actions retain their
actual post-operation clocks. Export failure invalidates the browser recording.

## CLI

```
node tools/browser/replay.mjs module.so experiment.json initial.rom initial.img new-report.json
node tools/browser/replay.mjs module.mjs experiment.json initial.rom initial.img new-report.json
node tools/browser/replay.mjs module.so session.p1715investigation - - new-report.json --rebind-engine
```

The `.so` engine identity is the library hash. The WASM engine identity is the hash
of UTF-8 JSON `{"javascript":"<mjs-sha256>","wasm":"<wasm-sha256>"}`. This binds
both artifacts; substituting a native engine for a WASM engine requires an explicit
new experiment identity, not a silent fallback. `--rebind-engine` explicitly
permits this only when both build manifests identify the same clean Pico1715 and
emulator source commits and the target artifact hash matches its manifest. The
report preserves both engine identities. `-` inputs use explicitly bundled initial
ROM/disk bytes. The CLI refuses input/engine
mismatches and existing report paths. Exit codes are 0 for completion, 1 for first
checkpoint divergence, and 2 for invalid input or execution failure.

The native Python subprocess is a private adapter for this JS orchestrator, not
a second schedule interpreter. It exposes an allowlisted subset of session calls
and bounded memory reads. No expression or code from an experiment is executed.

## Investigation archives

`.p1715investigation` is a schema-1 JSON archive, containing an experiment and up
to 64 flat named files with lengths, SHA-256 hashes and canonical base64 payloads.
Decoded contents are bounded to 128 MiB and the serialized input to 180 MiB.
Analyzer-only bundles carry a null experiment and remain view-only. There is no
filesystem extraction, path traversal or script execution. Corrupt
files, duplicate names and unsupported schemas are rejected.

ROM/disk bytes are omitted by default. Explicit browser inclusion attaches the
initial inputs, not the later working disk. Completed bus captures may accompany
the experiment. Import is inspection-only until the user explicitly selects
replay with matching inputs. A replay finishes paused and reports the first
divergent checkpoint rather than continuing through it.

## Verification

```
node --test tools/browser/experiment.test.mjs
node tools/browser/check-experiment.mjs build/browser-native build/browser
```

The real-session test compares native and WASM registers, RAM, disk, counters and
capture bytes for both backends despite different run chunk sizes. It covers
same-clock input ordering, cancellation, reset and deliberately incorrect
checkpoint evidence. Unit controls cover validation, export progression,
cancellation and bundle corruption. These tests establish simulator determinism,
not physical bus or SD behavior.
