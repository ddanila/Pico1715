#!/usr/bin/env python3
"""Extract a Rev A router candidate; independent DRC is mandatory before adoption."""
import argparse, hashlib, json
from pathlib import Path
import pcbnew as k
from import_carrier_routing import point, uncovered
ROOT = Path(__file__).resolve().parents[1]
def extract(directory, output):
    meta = json.loads((directory/'routing-input.json').read_text())
    source = ROOT/'hardware/carrier-reva/carrier.kicad_pcb'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == meta['source_sha256'], 'stale routing input'
    old = k.LoadBoard(str(directory/'router-base.kicad_pcb'))
    segments, old_vias = {}, set()
    for t in old.GetTracks():
        net = t.GetNetname().removeprefix('/')
        if isinstance(t, k.PCB_VIA):
            old_vias.add((net, tuple(point(t.GetPosition()))))
        else:
            key = (net, old.GetLayerName(t.GetLayer()), round(k.ToMM(t.GetWidth()), 6))
            segments.setdefault(key, []).append((point(t.GetStart()), point(t.GetEnd())))
    assert k.ImportSpecctraSES(old, str(directory/'carrier.ses'))
    prior=meta.get('prior_supplement') or {}
    tracks=[t for t in prior.get('tracks',[]) if t['net'] not in meta['replace_nets']]
    vias=[v for v in prior.get('vias',[]) if v['net'] not in meta['replace_nets']]
    for t in old.GetTracks():
        net = t.GetNetname().removeprefix('/')
        if net == 'GND':
            continue  # Ground is filled on the final four-layer board.
        if isinstance(t, k.PCB_VIA):
            at = point(t.GetPosition())
            if (net, tuple(at)) not in old_vias:
                vias.append(dict(net=net, at=at, diameter=round(k.ToMM(t.GetWidth(k.F_Cu)),6), drill=round(k.ToMM(t.GetDrillValue()),6)))
        else:
            layer=old.GetLayerName(t.GetLayer()); width=round(k.ToMM(t.GetWidth()),6)
            for a,z in uncovered(point(t.GetStart()),point(t.GetEnd()),segments.get((net,layer,width),[])):
                tracks.append(dict(net=net,layer=layer,width=max(.25,width),start=a,end=z))
    result=dict(schema=1,baseline_sha256=hashlib.sha256((ROOT/'hardware/carrier/carrier.kicad_pcb').read_bytes()).hexdigest(),source_sha256=meta['source_sha256'],session_sha256=hashlib.sha256((directory/'carrier.ses').read_bytes()).hexdigest(),replace_nets=meta['replace_nets'],tracks=sorted(tracks,key=lambda r:(r['net'],r['layer'],r['start'],r['end'])),vias=sorted(vias,key=lambda r:(r['net'],r['at'])))
    output.write_text(json.dumps(result,indent=2)+'\n')
    print('UNREVIEWED candidate:',len(tracks),'tracks,',len(vias),'vias')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('output',type=Path);a=p.parse_args();extract(a.directory,a.output)
