# Optional reset accessory and repeatable boot capture

The analyzer USB protocol and host utility now support `reset`, `reset-status`
and `arm-reset`. Stock builds keep the accessory disabled. Experimental builds
reserve **Pico GP22** for a 3.3 V active-high accessory command and one PIO0 state
machine. This is separate from the FPGA parallel transport (GP0–21) and QMI
PSRAM. The controller firmware does not enable this interface.

**GP22 must not be connected directly to RESET-TASTE or X1/X2.** X1/X2 A20 is
observed `/RESET2`; it does not establish CPU `/RESET1`. The separate accessory
must close the reset-button contacts through a qualified isolated interface.
See [the source-backed reset distinction](analyzer-mode.md#remote-cpu-reset-separate-optional-connection).

## Implemented behavior

- PIO executes a fixed 100,000-clock high pulse at a configured 1 MHz, then
  blocks with its output low. USB stalls, a stopped main loop or disabled CPU
  interrupts do not prolong the pulse while the PIO clock continues.
- `arm-reset` starts a new capture, waits for RUN with CLEAR released, then waits
  another 1 ms before queueing the pulse. This is a settling allowance, not a
  measured readiness acknowledgement from the FPGA. A 100 ms readiness timeout,
  capture failure/completion or STOP before assertion cancels the reset request.
- Disconnect or STOP cancels a pending pulse and releases an active output.
  Connecting USB, querying status or configuring a trigger never requests reset.
- Reset requests require both the current capture generation and a one-use reset
  token. An accepted attempt consumes its token, including backend failures.
  Replaying it cannot cause another pulse. ARM and trigger reconfiguration are
  rejected while reset is pending or active. A second reset is also rejected.
- Ordinary `reset` can run with or without a capture. It does not discard a
  capture. `arm-reset` has ARM's existing behavior: a new capture discards the
  previous one, so download useful data first.

The PIO source is `firmware/reset_pulse.pio`; shared protocol sequencing lives in
`firmware/analyzer_usb.c`. Default firmware has no GPIO reset driver. To build the
experimental backend after qualifying the accessory:

```sh
cmake -S firmware -B build/firmware -DPICO_NO_PICOTOOL=1 -DP1715_RESET_ACCESSORY=ON
cmake --build build/firmware --target pico1715_analyzer -j2
```

Return to `-DP1715_RESET_ACCESSORY=OFF` for the normal disabled build. Do not use
this option as evidence that the electrical interface has been qualified.

## Host workflow and records

```sh
python3 tools/analyzer_usb.py --port /dev/ttyACM0 reset-status
python3 tools/analyzer_usb.py --port /dev/ttyACM0 arm-reset --reset-log boot-reset.jsonl
# Or use the same trigger options as arm, e.g. --trigger iack --pre 8 --post 4.
python3 tools/analyzer_usb.py --port /dev/ttyACM0 stop
python3 tools/analyzer_usb.py --port /dev/ttyACM0 download boot.p1715
python3 tools/analyzer_1715.py boot.p1715 --reference reference.p1715
```

Reset calls wait for completion and return JSON metadata. `--reset-log` opens a
new file before sending any command, records the request, then appends the result.
If an operation fails or the connection is lost, a request without a result means
**outcome unknown**, not that no pulse occurred. Query `reset-status` before
issuing another request; the client does not automatically retry a reset.

Reset metadata is a sidecar associated by capture generation within a single Pico
boot, not fabricated bus-cycle records. It records request time, pulse enqueue
(assertion command) time and software-observed command-output release/cancel time
in the Pico's microsecond clock, modulo 2^32. They are not FPGA capture timestamps
or exact measured contact edges. PIO queueing takes a few clocks and release may
be observed later if polling stalls. Actual `/RESET2` intervals remain ordinary
captured records. Neither those intervals nor output release proves CPU reset.
Only the latest reset attempt is retained in RAM; save metadata before the next
request or Pico reboot. This mode performs no storage flush and makes no
safe-shutdown claim; controller-plus-analyzer operation remains separate work.

## Wire extension

Commands use the existing 24-byte request and CRC-protected response. Version
remains 1; older firmware rejects these commands. Reserved fields and length
must be zero.

| Command | ID | Generation | Offset |
| --- | --- | --- | --- |
| RESET_STATUS | 7 | ignored | zero |
| RESET | 8 | current capture generation | current reset token |
| ARM_RESET | 9 | current capture generation | current reset token |

Successful responses contain eight little-endian uint32 values: `enabled`,
`reset_state`, `reset_id`, `capture_generation`, `requested_us32`, `asserted_us32`,
`released_observed_us32`, `reason`. The response header carries the current
capture generation; `capture_generation` in the payload belongs to the most recent
reset attempt. ARM_RESET increments capture generation on successful arming.
RESET_STATUS is read-only. Reset tokens start at zero and cannot wrap; exhaustion
requires a device reboot, as with capture generations.

States: 0 idle, 1 waiting for capture, 2 pulse queued/active, 3 completed, 4
cancelled/failed. Reasons: 0 none, 1 disconnect, 2 capture readiness timeout or
capture ended/failed, 3 backend/start failure, 4 STOP. State and reason distinguish
an unset timestamp from a real event at clock zero. New wire errors are 6 reset
accessory unavailable and 7 stale reset token. Other error meanings are unchanged.

## Accessory interface contract and open bench gates

Reserve a keyed accessory connection carrying GP22 command, Pico ground and
3.3 V only. This is a logical pin allocation, not a frozen connector footprint.
The daughterboard must supply:

1. An external pull-down so reset is released while the Pico is unpowered,
   rebooting, being programmed or reconfiguring GP22. No motherboard voltage may
   reach GP22 or power the Pico through this connection.
2. An isolated, normally-open contact-equivalent across the two RESET-TASTE
   terminals. Determine terminal voltage, polarity, current and acceptable
   contact resistance from measurements before selecting parts.
3. An independent, non-retriggerable pulse limit with a required low interval
   before rearming. PIO limits ordinary firmware stalls but cannot release its
   output if its own clock stops while high. The accessory must therefore bound
   contact closure independently of the Pico clock, and never assert on power-up.
   Its pulse limit must be chosen against measured motherboard requirements;
   100 ms is the current software test value, not a certified switch requirement.
4. Isolation and power sequencing review for motherboard-only, USB-only and
   simultaneous power, including no backfeeding through other analyzer paths.

No reset accessory schematic, parts list or production connector is frozen by
this increment. Before enabling reset, verify pulse width, startup/disconnect,
Pico/FPGA resets, clock failure, stuck-high input and repeated commands on the
bench; probe both motherboard reset branches and confirm boot capture coverage.

## Desk verification

`make test` runs native UBSan protocol tests for unavailable accessories, stale
commands, autonomous timer release without polling, settling/readiness timeout,
STOP/disconnect/error cancellation, backend failure, and the host completion
loop. A small interpreter executes the actual PIO source's instruction subset
for 300,000 cycles and checks exactly one 100,000-cycle pulse followed by idle.
This covers program logic, not an RP2350 electrical/timing simulation. Both the
disabled and enabled ARM firmware configurations are compiled locally.

[Recorded source and firmware identities](../reports/analyzer-reset.json) identify
the desk-verified implementation. The local build is restored to accessory OFF.
