# Optional reserve supply — electrical draft

The [KiCad schematic](backup.kicad_sch) and [rendered sheet](preview/backup.svg)
provide a concrete, separate backup circuit for review. **Not fabrication-ready,
not integrated into the carrier PCB, and not qualified for protected writeback.**
Omitting the entire reserve branch leaves the existing D1 supply path operational.
D1 in this drawing represents the carrier's existing diode; do not fit a duplicate
feed or connect the reserve to V5_HOST, V5_MODULE or the FPGA rail.

## Power path

V5_MODULE feeds the Pico's P_VSYS through existing D1. A separate path through
D2 and R1 charges two series capacitors. F1 and D3 discharge the bank directly
into P_VSYS, bypassing the charging resistor. D1/D2 block reverse current into
the removed supply; D3 blocks USB/Pico VSYS from rapidly charging the bank.
Diode reverse leakage remains real and must be measured. This is resistor-limited
charging, not a constant-current charger.

R1 is a provisional 100 Ω, 1 W, 1% part. At the assumed 5.25 V input maximum,
even ignoring diode drop, startup charging is limited to 53.1 mA and resistor
power to 0.279 W. The limit also bounds shunt-clamp current. F1 is a provisional
0.75 A fuse; its interruption rating, resistance, pulse behavior and mounting
must be selected for the actual capacitor fault energy and load. R1 limits
charging, not a short circuit in the discharge path.

C1/C2 are candidate Eaton TV1030-3R0106-R, 10 F, 3 V cells. Each has a 10 kΩ
bleed/balance resistor and its own TL431A shunt clamp at approximately 2.495 V.
U1 floats on the midpoint; U2 references ground. This avoids depending solely on
passive resistors during unequal-cell charging. The TL431 **DBZ** pin contract
is 1=cathode, 2=reference, 3=anode; TL432 is different. Clamp stability, overshoot,
minimum regulation current and heating with these very large capacitors require
measurement. Do not interpret an ideal-clamp simulation as those measurements.
The proposed cells' temperature derating also applies; this draft does not
qualify hot-enclosure operation.

## Detection and firmware integration

U3 senses raw module power, before D1, and provides open-drain SUPPLY_OK.
U4 senses total capacitor voltage and provides open-drain RESERVE_OK. Both run
from backed-up P3V3 with 10 kΩ pull-ups to that same rail. They use TLV3011B,
including its fail-safe inputs and internal hysteresis. Nominal trip points are
approximately 4.56 V and 4.72 V. The calculator includes deliberately wider
reference/offset/hysteresis/resistor allowances instead of treating these nominal
values as guaranteed thresholds.

J3 is a five-wire cable interface, **not a pin-for-pin Pico connector**. Its
PIM724 SP/CE mapping and opt-in core-0 supervisor are documented in the
[reserve interface](../../docs/reserve-interface.md). The carrier power ECO and
analog threshold qualification remain unresolved. The integration contract is:

1. Start with backup ABSENT and writes protected. A high RESERVE_OK alone cannot
   establish fitted capacitance or capacitor health; an open capacitor can also
   leave the sense node high. Require installation confirmation and a controlled
   load test establishing a conservative reserve budget.
2. With valid measured reserve and SUPPLY_OK, qualify READY after stable charging.
   Admit writes only through the existing dirty-limit calculation.
3. On loss of SUPPLY_OK, request POWER_FAIL shutdown once and latch its deadline.
   Lower BACKEND_READY and release the bus immediately; drain the journal.
4. RESERVE_OK falling during discharge is expected. Do not map it directly to
   EXHAUSTED: use the qualified time budget and any subsequently implemented
   undervoltage monitor. At deadline, report failure rather than extending it.
   Restored power does not automatically reopen a terminated mount.

Pico, PSRAM and SD are backed up; FPGA and motherboard rails are not. The carrier
already uses SN74CB3Q3245 switches with power-off isolation, but every crossing
(including power-good, pull-ups and status wiring) must be audited and measured
under asymmetric supply loss. Preserve the hardware qualification/enable gates.
USB can keep VSYS alive after module power loss; that must not suppress the raw
power-fail event or silently re-enable writes.

## Calculated envelope

Run `python3 tools/check_backup_budget.py`. The [inputs](budget-inputs.json) and
[report](../../reports/backup-budget.json) separate component data from assumed
load, voltage-drop and timing envelopes. After initial tolerance and aging,
the two 10 F cells are modelled as 3.15 F effective, with 0.104 Ω capacitor ESR
plus an assumed 0.15 Ω fuse/wiring resistance. The constant-current model matches
an LDO-fed load; no buck/boost efficiency formula is substituted.

At the lowest modelled READY threshold, the example reserve is about 5.93 s at
100 mA, 1.44 s at 300 mA, and 0.55 s at 500 mA. The last case cannot admit even
the first sector with the example margin. These are **not measured hold-up times**
and the example journal timings must never be used as production settings.

The upper READY threshold can be about 4.93 V under the chosen conservative
allowances, above the charge equilibrium at a low input voltage. Such a unit
would remain CHARGING/read-only. Before integration, narrow the qualified detector
and diode bounds or revise the detector/topology; do not lower the firmware gate
to conceal insufficient reserve. Charging may take tens of minutes. Repeated
outages must require requalification, not merely a short charging delay.

## Bench acceptance

Measure both cell voltages, charging current, clamp oscillation/overshoot and
thermal behavior using mismatched cells and repeated outages. Measure discharge
voltage at Pico VSYS and SD 3V3 during worst-case SD busy intervals, with aged/low
capacitance and worst cable/fuse resistance. Test absent/shorted cells, USB-only
power, FPGA-only loss, host-only loss, and signal backfeed. Measure actual journal
transaction time and effective reserve before enabling protected writeback.

Primary sources: [Eaton cell data](https://www.eaton.com/us/en-us/skuPage.TV1030-3R0106-R.html),
[TL431 pinout/stability](https://www.ti.com/lit/ds/symlink/tl431.pdf),
[TLV3011B](https://www.ti.com/lit/ds/symlink/tlv3011.pdf),
[Pico Plus 2 schematic](https://www.electrokit.com/upload/quick/60/6d/7672_Pimoroni_Pico_Plus_2_Schematic.pdf),
and [bus-switch isolation](https://www.ti.com/document-viewer/SN74CB3Q3245/datasheet).
Manufacturer documents are not redistributed.
