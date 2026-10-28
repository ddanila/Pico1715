#!/usr/bin/env python3
import copy,json,sys,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from check_backup_budget import budget,charge
BASE=ROOT/'hardware/backup-power'
def check(parts,xml):
 by={p['ref']:p for p in parts};pins={(p['ref'],str(n)):net for p in parts for n,_,_,net in p['pins']}
 for net in xml.findall('./nets/net'):
  for node in net.findall('node'):assert '/'+pins[(node.attrib['ref'],node.attrib['pin'])]==net.attrib['name']
 assert [pins[('J3',str(i))] for i in range(1,6)]==['P3V3','GND','SUPPLY_OK','RESERVE_OK','GND']
 for ref,k,a in [('D1','P_VSYS','V5_MODULE'),('D2','CHARGE_IN','V5_MODULE'),('D3','P_VSYS','CAP_FUSED')]:assert [pins[(ref,str(i))] for i in (1,2)]==[k,a]
 assert [pins[('R1',str(i))] for i in (1,2)]==['CHARGE_IN','CAP_TOP'] and by['R1']['value']=='100R_1W_1pct'
 for ref,hi,lo in [('U1','CAP_TOP','CAP_MID'),('U2','CAP_MID','GND')]:assert [pins[(ref,str(i))] for i in (1,2,3)]==[hi,hi,lo]
 for ref,rail in [('U3','SENSE3'),('U4','SENSE4')]:
  assert pins[(ref,'3')]==rail and pins[(ref,'6')]=='P3V3' and pins[(ref,'2')]=='GND'
class Backup(unittest.TestCase):
 def test_contract(self):
  c=json.loads((BASE/'connections.json').read_text());self.assertFalse(c['carrier_integrated']);self.assertFalse(c['fabrication_ready']);xml=ET.parse(BASE/'backup.net.xml');check(c['parts'],xml)
  for ref in ['D1','D2','D3','U1','U2']:
   bad=copy.deepcopy(c['parts']);p=next(p for p in bad if p['ref']==ref);p['pins'][0][3],p['pins'][-1][3]=p['pins'][-1][3],p['pins'][0][3]
   with self.subTest(ref=ref),self.assertRaises(AssertionError):check(bad,xml)
 def test_budget(self):
  p=json.loads((BASE/'budget-inputs.json').read_text());r=budget(p);self.assertLess(r['max_startup_charge_a'],.06)
  self.assertGreater(r['rows'][0]['reserve_s'],r['rows'][-1]['reserve_s']);self.assertFalse(r['rows'][-1]['can_admit_first_sector'])
  p['cell_capacitance_f']=0;self.assertTrue(all(x['reserve_s']==0 for x in budget(p)['rows']))
 def test_mismatch_clamp(self):
  p=json.loads((BASE/'budget-inputs.json').read_text());self.assertLessEqual(max(charge(p)['maximum_cell_v']),2.55);self.assertGreater(max(charge(p,False)['maximum_cell_v']),3)
if __name__=='__main__':unittest.main()
