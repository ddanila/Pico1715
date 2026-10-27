# Carrier assembly and staged bring-up

This is a preparation document, not an assembly release. J3 has 12 held
connections and X2 is unplaced. The separate provisional X2 adapter does not
resolve the carrier's host connection or installation clearance.

Use the [component-side locator](preview/assembly.svg),
[actual pad coordinates](assembly-points.json), [BOM](bom.tsv), schematic and
footprints together. The locator marks pad 1, not universal polarity. IC dot or
notch must match pad 1; D1's cathode (marked end) is pad 1, P_VSYS. J2 must match
Pico physical pin numbers, not GPIO numbers. Verify every cable end by continuity;
three 1.27 mm FPGA cables are not interchangeable by appearance alone.

## Unpowered assembly

1. Inspect bare copper and plated holes against the reviewed files. Do not bridge
   SD exclusions or populate a guessed X2 footprint. Check for supply-to-ground
   shorts before and after each component group.
2. Assemble small passives and ICs, then connectors and controls. Inspect IC pin 1,
   D1 cathode, connector pin 1 and SW1 numbering before inserting modules. Confirm
   SW1 commons 2/6 select passive terminals 1/5 or controller terminals 3/7.
3. With modules and host disconnected, verify J4 pin 1 → V5_MODULE and pin 2 →
   GND; D1 anode pin 2 → V5_MODULE, cathode pin 1 → Pico VSYS (J2 pin 39).
   J2 pin 36 is P3V3. V3P3 (FPGA), P3V3 (Pico), V5_HOST and V5_MODULE must not
   be accidentally shorted together. Ground is common.
4. Verify header orientation using the actual pad coordinates. J1 pin 1 receives
   CDONE from FPGA PGM1 pin 5; J1 pin 2 is ground. **J1 is not a programming port.**

## Module-only power and programming

Keep the motherboard and X2 harness disconnected. Use regulated, current-limited
5 V at J4; it has no reverse-polarity input protection. Set the current limit from
the assembled module load budget and record measured startup/idle current;
no measured safe limit is claimed here. Check supply polarity before connection.
Follow the module power-isolation instructions before also connecting USB.

Program the Pico through its own USB and the HX8K through its own programming
interface. Use the carrier firmware/profile and matching carrier FPGA personality.
The standalone bench-fixture bitstream changes pin direction and must only be
used with its isolated fixture, with the host and carrier adapter disconnected.
GP22 is SD CS on this carrier; do not enable the optional remote-reset accessory.
X1/X2 RESET2 is not a CPU-reset output.

Measure P3V3 and V3P3 separately before functional tests. At J5: 1=GND, 2=PG3,
3=PG5, 4=PGP, 5=CDONE, 6=MODE_CTL, 7=PERSONALITY_CTL, 8=LINK_OK,
9=ARMED, 10=DATA_OE_N, 11=H_WAIT_N, 12=H_INT_N, 13=F_FAULT,
14=P3V3, 15=V3P3. Use these as observations against the schematic/RTL truth table;
PG5 cannot be expected asserted without host power. Do not externally force
status pins or attach a 5 V logic source to a 3.3 V input.

## Interlocks, then host

With an isolated fixture, verify reset, unconfigured FPGA, missing link, passive
mode, lost power-good and watchdog timeout all inhibit bus driving as specified
in the existing interlock tests. Observe actual output enables and contention,
not just a software status message. Start storage tests read-only using disposable
image copies; verify PSRAM, SD identity/CRC and recovery before writable media.
Optional backup energy is not required for normal operation; its charging circuit
and physical hold-up qualification remain a separate planned feature.

Host insertion requires resolved connector orientation, pin-to-pin continuity,
power compatibility and clearance. Start in passive/analyzer mode and observe
clock and bus voltages before enabling controller mode. Power down before mode
changes or cable moves. Compare captured cycles to the emulator; then exercise
read-only boot, writes to a disposable image, reset and power-loss recovery.

For each stage record board revision, component variants, firmware/bitstream
hashes, cable maps, supply voltage/current, instrument settings, observations and
pass/fail reason. No physical stage has been executed. Failed or unmeasured stages
must remain pending; passing simulation does not fill in these measurements.
