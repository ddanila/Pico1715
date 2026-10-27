# SPDX-License-Identifier: MIT
import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import bringup as b
import cycle_trace as trace
from test_analyzer_usb import AnalyzerUSBTests,Port
import analyzer_usb
class BringupTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.bin=self.base/'firmware';self.bin.write_bytes(b'original fixture');self.root=self.base/'run';b.init(self.root,'simulated','fixture',self.bin,self.bin);self.state=json.loads((self.root/'run.json').read_text())
 def tearDown(self):self.tmp.cleanup()
 def evidence(self,stage,result='pass',mode=None):
  p=self.base/(stage+'.json');p.write_text(json.dumps({'schema':1,'mode':mode or self.state['mode'],'stage':stage,'result':result,'operator':'unit-test','notes':'synthetic observations only','identities':{k:v['sha256'] for k,v in self.state['identities'].items()},'measurements':{k:'fixture value' for k in b.STAGES[stage][1]}}));return p
 def through(self,stage):
  for name in list(b.STAGES)[:list(b.STAGES).index(stage)+1]:b.record(self.root,self.state,name,self.evidence(name))
 def test_simulated_end_to_end_and_no_physical_promotion(self):
  self.through('writable');cap=self.base/'capture';cap.write_bytes(trace.Header(1,1,capture_mask=0x170).encode()+trace.Cycle(4,0,0,0,0,2,0,0).encode())
  b.action(self.root,self.state,'arm','analyzer',True);b.action(self.root,self.state,'stop','analyzer',True);b.action(self.root,self.state,'download','analyzer',True,replay=cap)
  r=b.report(self.root,self.state);self.assertFalse(r['physical_qualification']);self.assertFalse(r['hardware_executed']);self.assertEqual(r['stages_pending'],[])
  self.assertRaises(ValueError,b.record,self.root,self.state,'inspection',self.evidence('inspection',mode='physical'))
 def test_prerequisites_and_changed_stage_invalidate_later(self):
  self.assertRaises(ValueError,b.record,self.root,self.state,'module',self.evidence('module'))
  self.assertRaises(ValueError,b.action,self.root,self.state,'reset','analyzer',True)
  self.through('storage');b.record(self.root,self.state,'module',self.evidence('module','fail'));self.assertNotIn('storage',self.state['stages'])
 def test_missing_and_modified_evidence(self):
  p=self.evidence('inspection');e=json.loads(p.read_text());e['measurements']={};p.write_text(json.dumps(e));self.assertRaises(ValueError,b.record,self.root,self.state,'inspection',p)
  (self.root/'artifacts/firmware').write_bytes(b'changed');self.assertRaises(ValueError,b.verify,self.root,self.state)
 def test_dry_run_does_not_open_device(self):
  self.assertTrue(b.action(self.root,self.state,'status','analyzer')['dry_run']);self.assertEqual(self.state['actions'],[])
 def test_ambiguous_action_requires_status_then_explicit_reconcile(self):
  self.state['mode']='physical';self.through('interlocks')
  class Broken:
   def status(self):return {'state':0}
   def arm(self):raise TimeoutError('disconnected')
  self.assertRaises(TimeoutError,b.action,self.root,self.state,'arm','analyzer',True,client=Broken());self.assertTrue(self.state['reconciliation_required'])
  self.assertRaises(ValueError,b.action,self.root,self.state,'arm','analyzer',True,client=Broken())
  self.assertRaises(ValueError,b.reconcile,self.state,'checked')
  b.action(self.root,self.state,'status','analyzer',True,client=Broken());b.reconcile(self.state,'device status inspected; do not replay');self.assertFalse(self.state['reconciliation_required'])
 def test_pending_process_exit_is_detected_on_reopen(self):
  self.state['actions'].append({'id':1,'action':'arm','state':'pending','artifacts':[]});b.verify(self.root,self.state);self.assertTrue(self.state['reconciliation_required'])
 def test_real_usb_handler_download_with_fragmented_transport(self):
  AnalyzerUSBTests.setUpClass()
  try:
   lib=AnalyzerUSBTests.lib;lib.fixture_init();client=analyzer_usb.Client(Port(lib));self.state['mode']='physical';self.through('interlocks')
   b.action(self.root,self.state,'arm','analyzer',True,client=client)
   blob=trace.Header(50000000,1,capture_mask=0x170).encode()+trace.Cycle(4,0,42,0,0,4,0,0).encode();self.assertEqual(lib.fixture_complete(blob,len(blob)),0)
   b.action(self.root,self.state,'download','analyzer',True,client=client)
   self.assertEqual((self.root/self.state['actions'][-1]['artifacts'][0]['path']).read_bytes(),blob)
  finally:AnalyzerUSBTests.tearDownClass()
