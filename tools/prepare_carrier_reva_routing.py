#!/usr/bin/env python3
"""Prepare outer-layer routing only; inner layers remain continuous GND."""
import argparse,json,re,hashlib
from pathlib import Path
import pcbnew as k
ROOT=Path(__file__).resolve().parents[1]
def prepare(out,replace=None):
 out.mkdir(parents=True,exist_ok=True);src=ROOT/'hardware/carrier-reva/carrier.kicad_pcb'
 from kicad_text import remove_nodes
 replace_only=replace is not None
 replace=replace or ['F_CLK','F_WR_N']
 review=json.loads((src.parent/'pcb-review.json').read_text())
 assert review['board_sha256']==hashlib.sha256(src.read_bytes()).hexdigest(),'stale board metadata'
 prior=json.loads((src.parent/'routes.json').read_text()) if review['routed_additions'] else None
 text=remove_nodes(src.read_text(),lambda head,node,depth:
  head=='zone' or (head in ('segment','via') and any('(net "/'+n+'")' in node for n in replace)))
 (out/'router-base.kicad_pcb').write_text(text)
 b=k.LoadBoard(str(out/'router-base.kicad_pcb'));b.SetCopperLayerCount(2)
 k.SaveBoard(str(out/'router-base.kicad_pcb'),b)
 assert k.ExportSpecctraDSN(b,str(out/'carrier.raw.dsn'))
 s=(out/'carrier.raw.dsn').read_text()
 s=s.replace('(via "Via[0-1]_600:300_um")', '(keepout "SD_BODY" (rect F.Cu 161000 -37900 175000 -30100))\n    (via "Via[0-1]_600:300_um")',1)
 s=s.replace('(type route)','(type fix)').replace('(width 200)','(width 250)')
 # Exclude poured ground from the router; use wider copper for reserve paths.
 start=s.index('    (class kicad_default');head,classes=s[:start],s[start:]
 for net in ['GND','V5_MODULE','P_VSYS']:classes=classes.replace(' /'+net+' ',' ',1)
 s=head+'''    (class plane_ground /GND (circuit (use_via "Via[0-1]_600:300_um")) (rule (width 250) (clearance 250)))
    (class reserve_power /V5_MODULE /P_VSYS (circuit (use_via "Via[0-1]_600:300_um")) (rule (width 1000) (clearance 250)))
'''+classes
 (out/'carrier.dsn').write_text(s)
 (out/'routing-input.json').write_text(json.dumps(dict(schema=1,source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),replace_nets=replace,replace_only=replace_only,prior_supplement=prior,sd_omitted=False,inner_layers_not_routed=True),indent=2)+'\n')
 print('Prepared host/reserve completion and fresh clock/write routes; SD top-body exclusion preserved')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--replace-net',action='append');a=p.parse_args();prepare(a.out,a.replace_net)
