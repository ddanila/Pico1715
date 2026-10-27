# Hash-bound Z80 source maps

Generate original platform and diagnostic maps from the existing CP/M build:

```
python3 tools/source_map.py --source ../cpm-plus-1715/src/platform.asm --listing ../cpm-plus-1715/build/platform.lst --binary ../cpm-plus-1715/build/platform.cim --base 0xc000 --space ram --include-source --out platform.map.json
python3 tools/source_map.py --source ../cpm-plus-1715/src/p1715test.asm --listing ../cpm-plus-1715/build/p1715test.lst --binary ../cpm-plus-1715/build/p1715test.cim --base 0x100 --space ram --include-source --out diagnostics.map.json
```

The generator verifies emitted listing bytes against the binary and listing text
against source lines. It records SHA-256 for both inputs, distinguishes data from
instructions, retains symbols, rejects duplicate addresses and refuses an existing
output. Includes without emitted code are permitted; included executable sources
are not silently attributed to the outer file. RMAC relocatable BIOS listings are
not ZMAC listings and are not supported by this generator.

In the analyzer, load a map and its binary. Source text can be embedded explicitly
or supplied separately. Select an opcode fetch or use **Find first fetch** for a
symbol. The display separates bytes observed on the bus from expected image bytes
and disassembles only supplied observed bytes. Short operands, partial intervals,
loss and missing mapping history remain uncertain. Interrupt acknowledgements are
not instruction fetches. Matching bytes establish a candidate source interpretation,
not full-image residency or completed instruction execution.

Below 0800h, mapping is unknown until an observed reset or MEMCS1 write establishes
it in a capture containing the required event classes without reported loss.
MEMCS1 uses the documented classic-board decode `(port & 0xfc) == 0x28`.
Higher addresses are RAM in this classic profile. This does not apply to W/M banked
profiles. A bounded scan (two million preceding records) prevents unbounded work;
larger selections require a shorter capture window and retain an unavailable result.

Source maps/binaries/text explicitly loaded into the analyzer are included in its
portable bundle export. They remain local until exported. Original source licence
terms still apply to embedded text; the map generator's MIT licence does not
relicense those inputs.
