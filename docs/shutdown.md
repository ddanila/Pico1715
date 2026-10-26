# Safe eject and reserve-aware shutdown

The controller firmware now has a shared shutdown state machine in
`firmware/service.c`, exercised through the production storage/journal code.
It works without a backup capacitor: request safe eject while external power is
still present and wait for `P1715_SAFE` before removing power. This completes the
firmware contract; no power supervisor, charger, hold-up capacitor or physical
safe indicator is fitted/qualified by this change.

## Commands and observable state

The controller deliberately has no USB command handler on its bus-serving core.
The core-0 API `p1715_shutdown_request(P1715_EJECT)` performs flush-and-eject:

1. Disable controller writes and cancel any incomplete, uncommitted sector.
2. Lower BACKEND_READY and ACK, release the shared data pins, and clear both IRQ
   requests. The existing FPGA gate then releases host data, WAIT and interrupt.
3. Drain every acknowledged dirty RAM block through the existing redo journal.
4. Report `P1715_SAFE` only with zero dirty blocks, no SD/journal operation in
   flight, and no latched storage error or missed shutdown deadline.

A ready indication means the backend has completed its current SD protocol
writes, including busy release, CMD13 status and journal clear. It cannot prove
an SD card's internal flash survives power loss; qualify real cards separately.
A shutdown during a partial sector cancels that partial sector; it does not claim
that bytes short of a committed sector were saved. The model's existing write
acceptance boundary is unchanged.

The SWD-visible `p1715_shutdown_command` mailbox accepts 1 (eject) or 2 (early power
failure); core 0 consumes it on its next service step. For example, with a debugger
attached to running controller firmware:

```gdb
set variable p1715_shutdown_command = 1
continue
# Interrupt later to inspect; let both cores run while draining.
print p1715_status.shutdown
print p1715_status.dirty_blocks
print p1715_status.storage_busy
print p1715_status.shutdown_reason
```

States are 0 RUNNING, 1 DRAINING, 2 SAFE, 3 UNSAFE. Reasons are 0 none, 1 storage
failure, 2 missing/exhausted reserve during power failure, 3 deadline expired.
Repeated requests are idempotent. SAFE and UNSAFE are terminal for the current
mount: host RESET2 does not reopen service, recharge cannot clear a failure, and
there is no automatic remount or retry after a journal error. A board restart
reloads/replays storage through the normal validated startup path. No new guest
I/O port, USB endpoint or arbitrary motherboard pin has been assigned.

The API and mailbox are bring-up controls, not a finished end-user eject button.
A future supervisor/button implementation must call these APIs on core 0, not
from the storage worker or an interrupt handler. `p1715_status` is diagnostic
state; multiword SWD reads while running are not an atomic status packet.

## Write policies and backup states

Read-only remains the default. The existing `P1715_WRITEBACK=ON` selects explicit
**experimental** writeback: acknowledgement can precede SD persistence, and
sudden power loss without a charged reserve can lose acknowledged RAM data.
Safe eject provides an orderly shutdown path for this configuration.

`p1715_service_init_protected(controller, worst_block_us, margin_us)` instead starts
in reserve-gated mode, write-protected and with backup ABSENT on every boot.
The matching build option is `P1715_PROTECTED_WRITEBACK=ON`. It is mutually
exclusive with experimental writeback and requires a positive
`P1715_WORST_BLOCK_US`; `P1715_RESERVE_MARGIN_US` supplies additional detection,
isolation and scheduling allowance. These values must come from qualified worst
case measurements. No usable hardware values are supplied by default.

A core-0 supervisor reports `p1715_backup_update(state, reserve_us)`:

| State | Meaning |
| --- | --- |
| ABSENT (0) | No backup power available |
| CHARGING (1) | Reserve not yet qualified for writes |
| READY (2) | Specified usable reserve time is available |
| EXHAUSTED (3) | Previously available reserve depleted |
| FAILED (4) | Reserve/supervisor fault |

Reserve time is ignored unless READY. Protected mode admits a sector commit only
when READY and `dirty_blocks + 2 <= dirty_limit`, with:

```
dirty_limit = min(1600, floor((reserve_us - margin_us) / worst_block_us))
```

The limit is zero when the budget cannot cover the margin. One block budget must
cover the **entire four-write 512-byte journal transaction**, including SD busy
and status waits, not just transferring 512 bytes. The two-block allowance is
conservative even when rewriting already-dirty data. In-flight blocks remain
counted as dirty until the journal clear has completed. Writeability is rechecked
under the image lock at the actual controller write, including worker failures.
At budget exhaustion the model reports write protection; it does not buffer an
unbounded backlog or promise a guest-transparent pause.

Reserve loss with dirty/incomplete writes freezes service and drains while live
external power remains. With no dirty/incomplete work, protected service remains
available for reads but cannot accept writes until adequate reserve returns.
There is no silent switch into experimental mode. A clean running mount may
explicitly change policy via `p1715_write_policy`; changing policy during a write,
with dirty/in-flight data, or after eject is rejected.

## Early power failure

`p1715_shutdown_request(P1715_POWER_FAIL)` immediately isolates the bus and starts
or tightens a deadline from the current READY reserve. Without reserve, dirty or
in-flight data makes the result UNSAFE; clean error-free storage can be SAFE.
Once set, a deadline can only shorten: repeated outage notifications or apparent
recharge cannot buy extra time. Updates reporting a smaller remaining reserve
while draining also tighten it. Exhaustion/failure or elapsed deadline latches
UNSAFE and prevents new storage transactions. A transaction already inside the
synchronous SD driver may finish; that cannot subsequently change UNSAFE to SAFE.

Software cannot run after power has actually disappeared. The early-failure
signal must arrive while GPIO, FPGA isolation and storage remain powered. This
implementation has no physical detector input yet. A real board still needs
independent isolation, reserve sensing, measured hold-up energy and validation
of cross-domain power sequencing. The independent worker may be blocked inside
an SD timeout; safe indication never assumes that a blocked operation succeeded.

Journal recovery remains atomic per 512-byte block, not per 1024-byte sector or
filesystem operation. An outage can leave half a sector updated, or lose all
unflushed RAM. Torn journal metadata fails closed on reboot. SAFE means orderly
backend completion within the stated contract, not arbitrary power-loss immunity.

## Verification

`make test` compiles and runs `tests/shutdown_test.c` with UBSan against the real
service/controller/store code and the deterministic host SD implementation. It
covers read-only eject, cancellation of an incomplete sector, eject during an
in-flight journal operation, no service reopening after host reset, absent and
charging reserve, insufficient and exact two-block budgets, backlog rejection,
reserve loss, shortened/non-extendable deadlines, exhausted reserve, 16 complete
or torn SD failures and cold recovery from cuts before all eight SD operations
of a sector write. Protected restart remains write-protected until recharge.
Synthetic timing budgets are test fixtures, not hardware recommendations.

The existing 42-case firmware/FPGA storage-fault regression is also rerun, covering
bus service during slow SD operations, concurrent rewrites, host reset, startup
failures and journal recovery. Host hooks model deterministic interleavings, not
instruction-level dual-core scheduling or electrical storage behavior. See
[recorded verification](../reports/shutdown.json) for source identities and results.
