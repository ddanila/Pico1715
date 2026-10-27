# Guided bring-up evidence runner

`tools/bringup.py` prepares and records staged work; it does not qualify a board
on its own. No physical device was needed to test the orchestration. All exported
reports retain `physical_qualification: false` for independent engineering review.

Initialize a new run with exact artifacts and board identity:

```
python3 tools/bringup.py init local/bench-001 --mode physical --board carrier-draft-a --firmware build/firmware/pico1715.uf2 --bitstream build/carrier-analyzer.bin
python3 tools/bringup.py show local/bench-001
```

Use `--mode simulated` for rehearsal; a simulated run never connects to USB and
cannot accept physical stage records. Identity artifacts are copied and hashed.
All later evidence is checked against those exact hashes. Select a new run when
firmware, bitstream or board configuration changes. Artifact hash mismatches block
resume/export. Hashes provide integrity, not a signed authenticity claim.

Stages follow inspection → module power → programming → storage → isolated
interlocks → host fit → passive observation → read-only boot → disposable writes.
The show command lists required measurements. Record an operator-authored JSON:

```
{
  "schema": 1,
  "mode": "physical",
  "stage": "module",
  "result": "pass",
  "operator": "name",
  "notes": "Host disconnected; measured against reviewed schematic limits",
  "identities": {"firmware": "SHA256", "bitstream": "SHA256"},
  "measurements": {
    "rail_voltages": {"P3V3": "measured value", "V3P3": "measured value"},
    "currents": {"startup": "measured value", "idle": "measured value"},
    "instrument": "model, settings and calibration/reference"
  }
}
```

```
python3 tools/bringup.py record local/bench-001 module module-evidence.json
```

The operator judges measured limits. Missing values or prerequisites do not pass.
Changing an earlier stage invalidates later approvals. All old files are retained.
Programming/readback is a manual stage until the actual programmer is chosen and
qualified; the carrier CDONE tap is not a programming interface. Attach the exact
programmer/readback results in the stage evidence. Do not substitute a status bit
for a voltage, bus-contention or connector measurement.

Actions are dry runs unless `--execute` is provided. Select the explicit CDC port
and personality; do not use another client on that port concurrently:

```
python3 tools/bringup.py action local/bench-001 status --port /dev/ttyACM0 --execute
python3 tools/bringup.py action local/bench-001 configure --port /dev/ttyACM0 --execute
python3 tools/bringup.py action local/bench-001 arm --port /dev/ttyACM0 --execute
python3 tools/bringup.py action local/bench-001 stop --port /dev/ttyACM0 --execute
python3 tools/bringup.py action local/bench-001 download --port /dev/ttyACM0 --execute
```

ARM explicitly replaces the prior device capture. CONFIGURE selects immediate,
non-triggered acquisition; firmware capacity remains bounded. RESET/ARM-RESET
require the firmware's optional accessory capability; the ordinary carrier has
no accessory and GP22 is SD CS. Do not drive connector /RESET2 as CPU reset.
Controller `status` and `eject` use `--personality controller`. No write-enable or
power-failure override is introduced.

Actions are journalled before execution. After an interrupted or ambiguous action,
read fresh status, inspect the device, then run `reconcile --note 'observed state…'`.
No reset, arm, programming or write operation is automatically repeated. A run lock
prevents two instances from mutating its state simultaneously.

`assert --capture FILE --suite RULES --dac ../dac --node /path/to/node` runs the
same bounded engine as the browser, preserving capture, rules and result hashes.
Failed/inconclusive suites return nonzero. `export RUN NEW-DIRECTORY` copies the
report and artifacts, including `.p1715` captures for the analyzer. There are no
ROM/disk payloads unless explicitly supplied as evidence by the operator.

The tests exercise staged simulation, missing/stale evidence, prerequisite
invalidation, interruption/reconciliation and fragmented downloads using the real
C analyzer USB handler. None of those tests is physical qualification.
