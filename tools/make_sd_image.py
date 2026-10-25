#!/usr/bin/env python3
"""Create a raw Pico1715 SD image FILE; never opens a block device for writing."""
import argparse
from pathlib import Path
import struct
import zlib
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--disk',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();data=a.disk.read_bytes()
if len(data)!=819200: p.error('disk must be the 80x2x5x1024 raw format')
h=bytearray(512);h[:8]=b'P1715SD1';struct.pack_into('<II',h,8,2048,1600)
struct.pack_into('<I',h,508,zlib.crc32(h[:508]))
with a.out.open('xb') as f:
 f.write(h);f.write(bytes(512*2));f.seek(2048*512);f.write(data)
print(f'{a.out}: raw dedicated-card image, not a FAT filesystem; source untouched')
