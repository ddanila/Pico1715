#!/usr/bin/env python3
"""Extract routing review metrics. Geometry screening, not signal-integrity signoff."""
import argparse,hashlib,json,math
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def metrics(plan):
    rows={}; bynet=defaultdict(list)
    for t in plan['routes']:bynet[t['net']].append(t)
    for net,tracks in bynet.items():
        rows[net]={'copper_length_mm':round(sum(math.dist(t['start'],t['end']) for t in tracks),3),
                   'longest_segment_mm':round(max(math.dist(t['start'],t['end']) for t in tracks),3),
                   'vias':sum(v['net']==net for v in plan['vias']),
                   'segments':len(tracks)}
    parallel=[]
    tracks=[t for t in plan['routes'] if t['net'] not in {'GND','V3P3','P3V3','V5_HOST','V5_MODULE','P_VSYS'} and math.dist(t['start'],t['end'])>=10]
    for i,a in enumerate(tracks):
        ax,ay=a['start'];dx=a['end'][0]-ax;dy=a['end'][1]-ay;length=math.hypot(dx,dy);ux,uy=dx/length,dy/length
        for b in tracks[i+1:]:
            if a['net']==b['net'] or a['layer']!=b['layer']:continue
            vx=b['end'][0]-b['start'][0];vy=b['end'][1]-b['start'][1]
            if abs(ux*vy-uy*vx)>math.sin(math.radians(1))*math.hypot(vx,vy):continue
            separation=abs((b['start'][0]-ax)*uy-(b['start'][1]-ay)*ux)
            gap=separation-(a['width']+b['width'])/2
            if not 0<=gap<=.5:continue
            lo,hi=sorted((p[0]-ax)*ux+(p[1]-ay)*uy for p in [b['start'],b['end']])
            overlap=min(length,hi)-max(0,lo)
            if overlap>=10:parallel.append({'nets':[a['net'],b['net']],'layer':a['layer'],'overlap_mm':round(overlap,3),'edge_gap_mm':round(gap,3),'start':a['start'],'end':a['end']})
    return rows,sorted(parallel,key=lambda x:-x['overlap_mm'])

def main():
    import pcbnew as k
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--report',type=Path,default=ROOT/'reports/carrier-routing-review.json');args=ap.parse_args()
    base=ROOT/'hardware/carrier';plan=json.loads((base/'pcb-placement.json').read_text());nets,parallel=metrics(plan)
    b=k.LoadBoard(str(base/'carrier.kicad_pcb'));planes={z.GetLayer():z for z in b.Zones() if not z.GetIsRuleArea()}
    coverage=defaultdict(lambda:[0,0]);grounds=[v['at'] for v in plan['vias'] if v['net']=='GND'];returns=[]
    for t in plan['routes']:
        if t['net']=='GND':continue
        layer=k.B_Cu if t['layer']=='F.Cu' else k.F_Cu
        length=math.dist(t['start'],t['end']);n=max(1,math.ceil(length/.5));ds=length/n
        for i in range(n):
            f=(i+.5)/n;p=[t['start'][j]+f*(t['end'][j]-t['start'][j]) for j in range(2)]
            coverage[t['net']][0]+=ds
            if not planes[layer].HitTestFilledArea(layer,k.VECTOR2I(round(p[0]*1e6),round(p[1]*1e6))):coverage[t['net']][1]+=ds
    for v in plan['vias']:
        if v['net'] in {'GND','V3P3','P3V3','V5_HOST','V5_MODULE','P_VSYS'}:continue
        returns.append({'net':v['net'],'at':v['at'],'nearest_ground_via_mm':round(min(math.dist(v['at'],g) for g in grounds),3)})
    for net,(length,uncovered) in coverage.items():nets[net]['opposite_ground_uncovered_mm']=round(uncovered,3);nets[net]['opposite_ground_uncovered_percent']=round(100*uncovered/length,2) if length else 0
    report={'schema':1,'hardware_executed':False,'signal_integrity_qualified':False,
        'method':{'sample_step_max_mm':.5,'parallel_angle_tolerance_deg':1,'parallel_min_overlap_mm':10,'parallel_max_edge_gap_mm':.5,
                  'limits':'Copper length sums branches; no propagation/impedance model. Opposite-layer ground absence is a review flag, not proof of a broken return. Nearest-via distance ignores ground PTH pads and ground path impedance.'},
        'nets':dict(sorted(nets.items())),'parallel_candidates':parallel,'signal_via_return_distances':returns,
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [base/'carrier.kicad_pcb',base/'pcb-placement.json',Path(__file__)]}}
    args.report.write_text(json.dumps(report,indent=2)+'\n');print('Reviewed',len(nets),'nets;',len(parallel),'parallel candidates')
if __name__=='__main__':main()
