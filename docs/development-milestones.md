# Investigation and prototype development milestones

Accepted scope: all twelve goals, implemented in verified increments. Reference
hardware remains HX8K plus Pico Plus 2; four-layer carrier candidates are allowed.
Simulation evidence does not release physical qualification gates.

| Milestone | Goals | Completion contract | State |
| --- | --- | --- | --- |
| A | 4 replay, 2 bundles | Clocked replay from boot, hash-bound checkpoints, native/WASM parity, browser recording/import/export and missing-input handling | Implemented; native/WASM and browser checks pass |
| B | 3 faults, 1 trace/source | Scheduled supported faults, control runs, failure bundles and reduction; observed fetch/disassembly/source links with explicit uncertainty | Core implemented; extensions below remain |
| C | 5 combined mode | Controller-priority bounded transport, finite I/O/IACK/reset capture, disjoint PSRAM, loss accounting, capability negotiation, fit and co-simulation | Planned |
| D | 6 rotation, 7 CTC/SIO | Explicit rotating-media profile and asynchronous serial/peripheral timing; preserve previous qualified profiles | Planned |
| D | 8 applications, 9 diagnostics | Public source-built workloads, optional local historical manifests, transient-memory diagnostics and separate low-level diagnostic image | Planned |
| E | 10 disk workbench | Extend existing explorer for classic CP/M, staged edits to a new image and independent host/guest checks | Planned |
| F | 11 power | Resolve reserve threshold margin, assign GPIO interface and test shutdown/power-domain scenarios; measured energy remains pending | Planned |
| F | 12 PCB | SD evidence, provisional EFS58 integration, combined/supervisor interface, four-layer candidate, layout/assembly review and physical gate list | Planned |

Replay is from boot, not arbitrary-state restore. Bundles reference ROMs/disks
unless explicitly included. Fault APIs stay simulation-only. Source attribution
must not infer missing execution from I/O-only or incomplete traces. Combined
trace never delays controller service waiting for capture storage; bulk download
requires safe quiescence. Old standalone personalities remain supported.

Public CI uses redistributable source inputs. Local historical applications are
identified by hashes, never silently fetched or published. Guest diagnostics
must preserve OS/stack/resident memory and report the exact tested region.

Hardware work preserves the reproducible two-layer baseline. The SD routing hold
requires the engineering drawing, and connector mating/installation needs physical
evidence. Remote CPU reset retains the separate accessory; X1/X2 RESET2 is not
substituted. No orderable manufacturing release precedes required physical gates.

## Verified software increments

A provides hash-bound replay, explicit input inclusion and original-report
preservation. B provides scheduled named faults, paired CLI control runs, bounded
command reduction and browser evidence export. Public CP/M CRC investigations
boot the control successfully on both backends and reach the guest boot-error
message with corruption enabled. The first observed bad CRC is retained even
when downstream decoding uncertainty prevents a conclusive assertion failure.

Trace/source interpretation validates the source and binary identities, observed
opcode/operand bytes and available banking evidence. Platform and portable
diagnostic source profiles are included. Relocated RMAC BIOS mapping, event-based
fault triggers, browser paired-control execution and integration with independent
guest/host file-preservation oracles remain follow-ups. Milestones C–F remain
unimplemented by these software increments; no physical qualification is implied.
