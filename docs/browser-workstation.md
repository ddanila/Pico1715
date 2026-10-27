# Classic 1715 browser workstation

The DAC museum consumes two independent WebAssembly modules built here. Each
module owns one classic 1715 motherboard and controller session. The model backend
uses the controller model; firmware uses the production service/storage C, host
SD/PSRAM HAL and Verilated FPGA frontend. Neither measures physical timing.
The ordinary `classic_probe` and interactive host share `tools/session.h`.

## Build and test

Use Emscripten 4.0.23, Verilator, a C/C++ compiler and the pinned dac-emulation
checkout. `python3 tools/build_browser.py --dac ../dac-emulation --probes` builds
both browser modules and Node CLI probes. `--native --out build/browser-native`
builds comparison libraries. `--emcc` selects the compiler. No pthreads,
SharedArrayBuffer, server helper or cross-origin isolation is required.

`make test-browser-session` checks input limits/cancellation, overlay inspection,
execution breaks, stepping, reset and resumable export. `tests/browser_parity.py`
compares native and WASM RAM, registers, diagnostics and disk bytes at identical
clock boundaries, including continuing after an export. Use `PICO1715_TEST_RESET=1`
for a subsequent reset, and existing cost/SD-delay environment settings for
cooperative-context coverage. `PICO1715_FORCE_CONTEXT=1` disables the no-delay
context-switch optimization. The optimization executes the same service/storage
steps directly only when no configured cost or delay can suspend them.

Native contexts use ucontext; browser contexts use Emscripten fibers/Asyncify.
A yielding WebAssembly export does not reliably return its final C result to JS.
After init/run/step/export, **read `p1715_result()`**; it is non-yielding and carries
that completed operation's result. Never treat a zero trampoline return as no
CPU progress. The Node probe exits explicitly for the same reason.

## ABI 1

The `p1715_` exports are a single-session C interface. Init takes a 2048-byte ROM,
an 819200-byte disk and a write-enable flag, copying both inputs. Reinitialization
is rejected; create a fresh module for a cold power cycle. Run takes a bounded
clock count; reset retains RAM and media, clears queued host input and restores
the ROM overlay. A monotonic input clock does not replay events after reset.

Key accepts one nonzero 7-bit character into a 4096-character source queue.
Completed E0/data bytes are attempted once, 1000 clocks apart, with 101000 clocks
between character starts. Receiver-full/disabled input is counted, not retried.
Cancel retains an already-started pair. The guest's own 128-character ring is a
separate resource. Bytes, flags, disassembly and mapped-memory reads are
observation-only. Execution breakpoints stop at opcode fetch, before execution.
Instruction stepping is capped at 100000 clocks and advances all devices.

Export returns 0 while pending, 1 when the copied image is ready, or a negative
error. Each call advances at most 1024 CPU clocks to reach an instruction boundary
or 100 simulated microseconds of firmware drain. No exposed I/O transaction is
completed twice. Drain stops new serving steps, completes suspended work and dirty
storage, verifies PSRAM/SD agreement, then restores serving and advances the clock
epoch so time cannot run backwards. UI hosts must keep pumping bounded calls.
Export can advance the machine even when it was paused; it preserves no whole-
machine snapshot. CPU reset is distinct from orderly save-and-power-off.

The stat accessor reports clocks, cylinder, sector, fields, writes/rejections,
WAIT clocks, RX/TX errors, source queue and input outcomes; firmware adds state,
dirty blocks, storage error, RTL requests and SD writes. Memory pointer exports
are valid only in that module's current heap; copy data before heap growth.

## Distribution

The artifact manifest identifies both source revisions, compiler, Verilator and
file hashes. Dirty builds are marked; museum synchronization rejects them unless
explicitly used for development. The museum bundles the separately source-built
CP/M demo with its original notices and identifies the fixture ROM as bypassing
the historical bootstrap. Historical ROMs remain local inputs. Existing museum
snapshots and the 1715M backend are separate and unaffected.
