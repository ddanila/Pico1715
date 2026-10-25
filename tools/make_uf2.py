#!/usr/bin/env python3
"""Wrap a Pico SDK RP2350 Arm-secure flash binary as UF2 (no device writes)."""
import argparse
from pathlib import Path
import struct
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bin',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();data=a.bin.read_bytes()
if not data or len(data)>16*1024*1024:p.error('expected a nonempty flash binary of at most 16 MiB')
count=(len(data)+255)//256
with a.out.open('xb') as f:
 for i in range(count):
  # RP2350_ARM_S_FAMILY_ID from the official SDK boot/uf2.h.
  h=struct.pack('<8I',0x0a324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff59)
  f.write(h+data[i*256:(i+1)*256].ljust(256,b'\0')+bytes(220)+struct.pack('<I',0x0ab16f30))
print(f'{count} UF2 blocks; RP2350 Arm secure; no device programmed')
