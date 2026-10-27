#!/usr/bin/env python3
"""Classify the four non-prompt images from unmodified execution evidence."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for n in ['binary','rom','images','out']:ap.add_argument('--'+n,type=Path,required=True)
 ap.add_argument('--report',type=Path,default=ROOT/'reports/boot-diagnosis.json');a=ap.parse_args()
 catalog=json.loads((ROOT/'tests/extended-media-inputs.json').read_text());assert digest(a.rom)==catalog['rom_sha256'];a.out.mkdir(parents=True,exist_ok=False)
 env={k:v for k,v in os.environ.items() if not k.startswith('PICO1715_')};env.update(PICO1715_TIMED='0',PICO1715_BOOT_DIAGNOSTICS='1');rows=[]
 for name,c in catalog['images'].items():
  if c['prompt_observed']:continue
  source=a.images/name;assert digest(source)==c['sha256'];out=a.out/source.stem;out.mkdir()
  result=subprocess.run([str(a.binary.resolve()),str(a.rom.resolve()),str(source.resolve()),str(out.resolve()),'DIR\r','readonly'],env=env,capture_output=True,text=True,check=True,timeout=120)
  stats=json.loads(result.stdout);d=json.loads((out/'boot-diagnostic.json').read_text());ram=(out/'ram.bin').read_bytes()
  assert stats['rom_handoff_target']==0x4000 and ram[0x5c38:0x5c3b]==bytes.fromhex('c3385c')
  assert d['io_reads'].get('28',0)>0 and d['io_reads'].get('29',0)>0
  assert sum(d['pc_ticks'].get(str(p),0) for p in [0x5c38,0x5c39,0x5c3a])>80000000
  assert b'PRESS RESET-KEY' in ram and b'READ SCP3.SYS' in ram
  assert digest(source)==c['sha256'] and digest(out/'disk.img')==c['sha256']
  rows.append(dict(image=name,input_sha256=c['sha256'],handoff=stats['rom_handoff_target'],loader_ram_sha256=hashlib.sha256(ram[0x4000:0x6800]).hexdigest(),terminal_loop=0x5c38,terminal_loop_ticks=sum(d['pc_ticks'].get(str(p),0) for p in [0x5c38,0x5c39,0x5c3a]),post_handoff_io_reads=d['io_reads'],post_handoff_io_writes=d['io_writes'],classification='W-style 8272/DMA/banked-memory loader; incompatible with the implemented classic PIO controller'))
 assert len({r['loader_ram_sha256'] for r in rows})==1
 report=dict(schema=1,hardware_executed=False,cases=rows,evidence=['All four reach 4000h with an identical loaded 4000h..67FFh RAM region.','They access 1Ch/1Dh (8272 on 1715W), DMA port 00h and bank port 24h; these are not the classic PIO floppy interface.','They terminate at JP 5C38h after the READ SCP3.SYS BIOS error path; extending the cycle bound cannot leave this unconditional self-jump.'],limits=['No W-model implementation added; original OS/media remain unchanged.','The diagnostic fixed F800h screen dump does not emulate the W display/memory mapping.'],hardware_map_source='https://github.com/mamedev/mame/blob/master/src/mame/robotron/rt1715.cpp',source_sha256={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'tools/classic_probe.c',ROOT/'tests/extended-media-inputs.json']})
 a.report.write_text(json.dumps(report,indent=2)+'\n');print('PASS four incompatible-loader classifications')
if __name__=='__main__':main()
