#!/usr/bin/env python3
"""Create supplemental copper for the rejected shorter-write experiment."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 base=ROOT/'hardware/carrier/additional-routes.json';candidate=json.loads((ROOT/'hardware/carrier/shorter-write-candidate.json').read_text())
 assert hashlib.sha256(base.read_bytes()).hexdigest()==candidate['base_additional_sha256'],'routing baseline changed; review candidate again'
 assert not candidate['adopted'];result=json.loads(base.read_text());net=candidate['net']
 for key in ['routes','vias']:result[key]=[r for r in result[key] if r['net']!=net]+candidate[key]
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print('Wrote experimental copper; not adopted:',a.output)
if __name__=='__main__':main()
