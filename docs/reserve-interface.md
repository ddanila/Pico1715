# Optional reserve interface for Rev A

This allocation uses the PIM724 SP/CE connector, independently of the FPGA and
its 22-pin transport. Qw/ST is not usable here: its GP4/5 already serve that link.
No main-header GPIO is reassigned. This is an electrical/cable contract; exact
cable mates, carrier power connector and mechanical placement remain release gates.

| PIM724 SP/CE J3 pin | PIM724 function | Reserve daughter J3 pin/function |
| --- | --- | --- |
| 1 | GND | 2, GND |
| 2 | GPIO36 | 5, PRESENT_N, tied to daughter ground |
| 3 | GPIO32 | 3, SUPPLY_OK open drain |
| 4 | GPIO35 | Not connected |
| 5 | GPIO34 | Not connected |
| 6 | GPIO33 | 4, RESERVE_OK open drain |
| 7 | Pico 3V3 | 1, backed comparator supply/pull-ups |
| 8 | VSYS | Not connected by this status cable |

These are connector **pin numbers**, not left-to-right positions viewed from
an unspecified side. Verify keyed cable orientation and continuity before power.
GPIO36 uses the Pico pull-up; open or missing presence wiring means absent.
GPIO32/33 are inputs with weak pull-downs; the daughter has 10 kΩ pull-ups to the
same backed 3V3 rail. Verify logic levels over tolerances on the actual assembly.
An unplugged presence wire cannot qualify reserve. This is not a fault-tolerant
presence detector: shorts or incorrect wiring require bench inspection.

Keep capacitor charge/discharge current off the status cable. Daughter J1 takes
raw V5_MODULE/GND; J2 returns P_VSYS/GND. The carrier's existing D1 stays fitted,
so an omitted daughter does not interrupt normal power. Do not duplicate D1 or
join FPGA/host power to backed VSYS. Cable and power connector current ratings,
polarization, fuse and reverse-current paths require review before fabrication.

## Firmware

`P1715_RESERVE_SUPERVISOR=ON` requires the PIM724 carrier profile. Core 0 polls
pins using the SDK's individual GPIO access, which handles pins above GPIO31.
It does not use the 32-bit bus masks. No FPGA service is required for detection.
The option defaults off; `P1715_QUALIFIED_RESERVE_US` defaults zero. A zero budget
never reaches READY even with both comparator outputs high. Setting it nonzero
requires a separately recorded controlled load test for that actual assembly,
SD card, temperature range and firmware. No measured value is supplied here.
Protected-write mode additionally requires its existing measured block and margin
budgets; reserve sensing does not itself change the chosen write policy.

One second of stable SUPPLY_OK/RESERVE_OK qualifies READY only when that measured
budget is supplied. Reserve loss while supply remains valid revokes qualification
and uses the existing protected-write drain policy. Supply loss requests
POWER_FAIL once, preserving the previously qualified budget and latching the
existing deadline. Falling RESERVE_OK during discharge cannot erase that budget.
Restored supply never restarts the mount. Removing a previously detected daughter
invalidates the budget and shuts down. Hot plugging is unsupported. An absent
daughter leaves ordinary read-only/experimental operation available; protected
writes remain refused. Voltage status alone cannot prove capacitor health.

Polling latency, GPIO levels, power-domain isolation, capacitor energy and SD
busy-time bounds remain physical qualification gates. The existing analog READY
threshold's upper bound can exceed low-input charging equilibrium: this interface
allocation does not resolve that circuit issue or relax the qualification gate.

## Source evidence

Visually reviewed manufacturer schematic, PIM724, generated 29 August 2024,
page 1, SP/CE J3, downloaded from the
[distributor-hosted Pimoroni schematic](https://www.electrokit.com/upload/quick/60/6d/7672_Pimoroni_Pico_Plus_2_Schematic.pdf).
SHA-256: `fb84bd32f63b18296d19af1e8d4d9126b80bb674f042bcf40f4ef3e2788c1418`.
The Pico SDK `pimoroni_pico_plus2_rp2350.h` independently assigns SP/CE GPIO32–36.
Manufacturer documents are not redistributed. The original generated daughter
schematic labels its separate J3 cable mapping explicitly; J3 numbering on the
two boards is different.
