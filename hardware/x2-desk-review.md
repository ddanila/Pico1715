# X2 desk review, 2026-10-25

## Closed by original drawings

The [pinout review](x2-pinout.md) now traces the original FDC and ZRE sheets,
not just the connector-table names. Card IEO drives X2 A10; card IEI receives
X2 B10 with a local pull-up. The motherboard chain is X2 A10 -> CTC A30
pin 13; CTC pin 11 -> SIO A29 pin 6; SIO pin 7 -> X1 B10. X2 B10 has no
motherboard driver shown. Original sheet 1.93.300101.5/04 says X2:A10;
the Zander redraw's X1:A10 is a transcription discrepancy. Revision C's
removable R16/R17 links implement the original FDC connection, and the
netlist checker verifies both directions independently.

The assembly drawing fixes the component-view orientation: X2 pin 1 at left,
B row toward the CPU, A row toward X1, with X3 at left and X4/X5/X6 at right.
The selected connector's dimensioned drawing is still needed for a footprint.
No dimensions have been inferred from the scan's scale.

## Conditional timing budget

Run `python3 tools/check_bus_budget.py` after fitting the production top.
The [report](../reports/x2-desk-timing.json) includes the routed timing file hash
and explicitly leaves the CPU margin unset. This is a pre-layout budget under
specified datasheet loads, not a measured or guaranteed assembled-card result.

At 2.458 MHz a CPU period is 406.835 ns. Normal-I/O WAIT assertion is
combinational in `bus_frontend.v`: receiver U1/U3 -> FPGA decode -> U8 NAND
-> U9 open drain. It does not wait for a 50 MHz edge or Pico firmware.
With arm and power qualifiers already stable, the U6/U7 qualifier chain is
not an additional serial stage on every WAIT request.

| Element | Budget, ns | Conditions/source |
| --- | ---: | --- |
| LVC245A receiver | 6.3 | 3.3 ±0.3 V, -40..85°C, datasheet switching/load conditions |
| Routed FPGA async envelope | 14.082 | Current production-top nextpnr summary, worst reported async-to-async path ends at host_oe |
| LVC00A NAND | 4.3 | Same voltage/temperature range, datasheet test load |
| LVC07A open drain | 3.6 | Same range; use 3.3 V column, not headline 5 V number |
| Conditional sum | 28.282 | Excludes motherboard delay and loads outside test conditions |

Sources: [TI LVC245A](https://www.ti.com/lit/ds/symlink/sn74lvc245a.pdf),
[TI LVC00A](https://www.ti.com/lit/ds/symlink/sn74lvc00a.pdf),
[TI LVC07A](https://www.ti.com/lit/ds/symlink/sn74lvc07a.pdf).
The generic async envelope is useful screening evidence, but is not an explicit
pad-to-pad WAIT constraint with board timing attached. A fitted Fmax is not
an external-bus timing certificate.

The [Zilog manual, Figure 7](https://www.zilog.com/docs/z80/um0080.pdf)
shows the automatic I/O wait state. A correct margin must use that sampling
edge and subtract CPU output delay, motherboard buffers, card delay, CPU WAIT
setup and skew. We have not substituted a modern Z80 speed-grade specification
for the owner's unspecified U880. Consequently `406.835 - 28.282` is **not**
a valid claimed setup margin.

The original ZRE sheet gives WAIT pull-up R10.4 = 3.3 kΩ and INT pull-up
R8.19 = 1 kΩ. WAIT release is especially load-sensitive. A simple 5 V RC
model starting from 0 V reaches an illustrative 2 V threshold after
`-R*C*ln(1-2/5)`: 84.3 ns at 50 pF, 168.6 ns at 100 pF and 337.1 ns at
200 pF. These capacitances are scenarios, not measurements; 2 V is a
screening threshold, not an asserted U880 specification. Receiver leakage,
probe capacitance, motherboard load and wiring must enter the final model.
A slow release can add a wait state. Do not add the falling-edge datasheet
maximum as though it certifies this rising edge.

## Timing work that is still open

The frontend's single SETTLE cycle provides 20 ns between latching response
data/enabling its driver and requesting WAIT release. To close that path,
compare the *latest* host-data validity (FPGA data and OE paths, U8/U9, U4
AHCT541 and bus capacitance) with the *earliest* possible WAIT recognition
and subsequent CPU data sample. The nominal 20 ns alone proves neither
success nor failure. Do not increase it blindly and call the path qualified.

IACK is separately decoded and does not use normal-I/O WAIT. Its vector/OE
path needs its own deadline. Desk review found that the former RETI detector
sampled data at fetch start. It now tracks data and IEI throughout the fetch,
then decodes the final in-window sample once fetch ends. Tests cover delayed
valid data, stale early 4D, post-fetch bus changes, non-M1 reads, RETN and
higher-priority service. The delayed-data regression fails on the old RTL.
The remaining physical contract is that data and IEI are valid at the last
50 MHz sample before fetch deassertion (allow a full 20 ns phase uncertainty
plus setup/skew). This is not an asynchronous-bus CDC qualification.

Remaining physical work: confirm the specimen matches the drawings, verify
connector fit and unpowered continuity, measure bus loads and edge timing,
then exercise power sequencing, IACK/RETI and stock boot on the fixture and
machine. These are concrete qualification tasks, not reasons to keep the
source-proven connector mapping unresolved.
