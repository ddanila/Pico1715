# Why four images do not boot on the classic controller

The four failed surveys are now diagnosed as incompatible loader hardware,
rather than unexplained timeouts. `r1715ms.cpm`, `r1715mt.cpm`, `scp3.cpm` and
`scp30.cpm` all hand off from the unchanged ROM to 4000h. Their loaded RAM region
4000h–67FFh is identical in the diagnostic runs.

They access 1Ch/1Dh and use the W-style DMA/banking control ports. The
[MAME hardware map](https://github.com/mamedev/mame/blob/master/src/mame/robotron/rt1715.cpp)
assigns 1Ch/1Dh to the 1715W's 8272 controller, 00h to DMA and 24h to bank
selection. The classic machine instead uses the two PIOs at 00h–07h. Our classic
controller does not supply the W peripheral protocol or banked-memory semantics.

After the attempted SCP3.SYS read, all four enter the loader's BIOS-error path
and finish at `JP 5C38h` at address 5C38h—an unconditional self-jump. More than
80 million of the 100 million simulated cycles are spent in that instruction's
PC states. A larger timeout alone cannot get past it. The error path includes
“PRESS RESET-KEY”; our fixed F800h diagnostic screen dump does not implement the
W display mapping, explaining why it did not show that message.

This diagnosis does not add W compatibility or justify patching the loader to
skip the error. These images remain unsupported on the current classic card.
Supporting them would require a separately scoped W controller/memory model or
an appropriately ported system image.

The [report](../reports/boot-diagnosis.json) records input hashes, loaded-region
hashes and actual post-handoff I/O counts. `PICO1715_BOOT_DIAGNOSTICS=1` enables
bounded fetch logging and PC/I/O histograms in the native probe. It changes no
ROM, media or peripheral return values. Reproduce with a freshly built probe:

```sh
python3 tools/check_boot_diagnostics.py --binary /path/to/classic-probe \
  --rom /path/to/r1715bt.bin --images /path/to/r1715fdd \
  --out local/new-boot-diagnostics
```
