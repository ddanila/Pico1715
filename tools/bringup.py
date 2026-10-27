#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Guided evidence collection. Simulation can never qualify a physical stage."""
import argparse, contextlib, fcntl, hashlib, json, os, shutil, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path

STAGES={
 'inspection':('Board revision, polarity, shorts and separate power domains',('continuity',)),
 'module':('Host disconnected; rails and startup/idle current measured',('rail_voltages','currents','instrument')),
 'programming':('Explicit manual programming and readback with chosen programmer',('programmer','firmware_readback','bitstream_readback')),
 'storage':('Disposable media; PSRAM patterns, SD identity/CRC and cold starts',('psram','sd','cold_starts')),
 'interlocks':('Isolated fixture: reset, missing power/link and watchdog inhibit outputs',('fixture','oe_observations','instrument')),
 'host-fit':('Host disconnected: actual connector mapping, clearance and chain continuity',('connector_map','clearance','chain_continuity')),
 'passive':('Passive host observation only; measured clock and bus levels',('clock','bus_levels','instrument')),
 'boot':('Read-only real-host boot, trace and independently observed console',('console','capture','read_only')),
 'writable':('Explicit disposable-media writes, cold verification and safe eject',('disposable_media','cold_verify','eject')),
}
PREREQUISITES={stage:list(STAGES)[:i] for i,stage in enumerate(STAGES)}
ACTIONS={'status':[], 'reset-status':['programming'], 'configure':['interlocks'], 'arm':['interlocks'], 'stop':['interlocks'], 'download':['interlocks'], 'reset':['host-fit'], 'arm-reset':['host-fit'], 'eject':['storage']}
MUTATING={'configure','arm','stop','reset','arm-reset','eject'}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def save(root,data):
 fd,name=tempfile.mkstemp(prefix='.state-',dir=root)
 try:
  with os.fdopen(fd,'w') as f:json.dump(data,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
  os.replace(name,root/'run.json')
 finally:
  if os.path.exists(name):os.unlink(name)
def init(root,mode,board,firmware,bitstream):
 root=Path(root);root.mkdir(parents=True,exist_ok=False);(root/'artifacts').mkdir()
 state={'schema':1,'mode':mode,'hardware_executed':False,'board':board,'created':now(),'identities':{},'stages':{},'actions':[],'reconciliation_required':False}
 for name,path in [('firmware',firmware),('bitstream',bitstream)]:
  target=root/'artifacts'/name;shutil.copyfile(path,target);state['identities'][name]={'path':str(target.relative_to(root)),'sha256':sha(target)}
 save(root,state)
@contextlib.contextmanager
def opened(root):
 root=Path(root)
 with (root/'.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  state=json.loads((root/'run.json').read_text());verify(root,state)
  yield root,state
  save(root,state)
def verify(root,state):
 if state.get('schema')!=1 or state.get('mode') not in ('simulated','physical'):raise ValueError('Unsupported run')
 artifacts=list(state['identities'].values())+[s['evidence'] for s in state['stages'].values()]
 for a in state['actions']:artifacts.extend(a.get('artifacts',[]))
 for a in artifacts:
  p=(root/a['path']).resolve()
  if not p.is_relative_to((root/'artifacts').resolve()) or sha(p)!=a['sha256']:raise ValueError('Stale or modified artifact: '+a['path'])
 if any(a['state']=='pending' for a in state['actions']):state['reconciliation_required']=True
def prerequisites(state,stages):
 for stage in stages:
  if state['stages'].get(stage,{}).get('result')!='pass':raise ValueError('Prerequisite pending/failed: '+stage)
def attach(root,path,name):
 target=root/'artifacts'/name
 with target.open('xb') as out,Path(path).open('rb') as source:shutil.copyfileobj(source,out)
 return {'path':str(target.relative_to(root)),'sha256':sha(target)}
def record(root,state,stage,path):
 prerequisites(state,PREREQUISITES[stage]);e=json.loads(Path(path).read_text())
 if state['reconciliation_required']:raise ValueError('Reconcile interrupted operation first')
 if e.get('schema')!=1 or e.get('stage')!=stage or e.get('mode')!=state['mode'] or e.get('result') not in ('pass','fail') or not e.get('operator') or not e.get('notes'):raise ValueError('Evidence needs matching mode/stage, result, operator and notes')
 if e.get('identities')!={k:v['sha256'] for k,v in state['identities'].items()}:raise ValueError('Evidence identifies other firmware/bitstream')
 if e['result']=='pass' and any(not e.get('measurements',{}).get(k) for k in STAGES[stage][1]):raise ValueError('Required measurement missing')
 n=len(list((root/'artifacts').iterdir()));artifact=attach(root,path,f'evidence-{n}.json')
 # Any changed prerequisite invalidates all later approvals, retaining their files.
 for later in list(STAGES)[list(STAGES).index(stage)+1:]:state['stages'].pop(later,None)
 state['stages'][stage]={'result':e['result'],'evidence':artifact,'basis':'operator-attested physical measurements' if state['mode']=='physical' else 'simulated evidence; not physical qualification','recorded':now()}

def action(root,state,name,personality,execute=False,port=None,client=None,replay=None):
 if name not in ACTIONS:raise ValueError('Unknown action')
 if personality not in ('analyzer','controller') or (personality=='controller' and name not in ('status','eject')) or (personality=='analyzer' and name=='eject'):raise ValueError('Action/personality mismatch')
 prerequisites(state,ACTIONS[name])
 if state['reconciliation_required'] and name not in ('status','reset-status'):raise ValueError('Reconcile interrupted operation before further actions')
 if not execute:return {'dry_run':True,'action':name,'personality':personality,'mode':state['mode'],'note':'Use --execute for this deliberate action; no device opened'}
 event={'id':len(state['actions'])+1,'action':name,'personality':personality,'state':'pending','started':now(),'artifacts':[]};state['actions'].append(event);save(root,state)
 try:
  if state['mode']=='simulated':
   if client is not None:raise ValueError('Simulated run must not access a physical client')
   if name=='download':
    if not replay:raise ValueError('Simulation download needs --replay CAPTURE')
    from cycle_trace import read_header,records
    with Path(replay).open('rb') as stream:h=read_header(stream);sum(1 for _ in records(stream,h))
    event['artifacts'].append(attach(root,replay,f"capture-{event['id']}.p1715"));result={'simulated':True,'records':h.count}
   else:result={'simulated':True,'action':name,'state':'replayed; no hardware operation'}
  else:
   if client is None:
    if not port:raise ValueError('Select an explicit serial port')
    import serial
    from analyzer_usb import Client as Analyzer
    from controller_usb import Client as Controller
    with serial.Serial(port,115200,timeout=5,write_timeout=5,exclusive=True) as serial_port:
     serial_port.dtr=True;serial_port.rts=False
     result=perform(root,event,name,Analyzer(serial_port) if personality=='analyzer' else Controller(serial_port))
   else:result=perform(root,event,name,client)
   state['hardware_executed']=True
  event.update(state='complete',result=result,finished=now());save(root,state);return result
 except BaseException as e:
  event.update(state='unknown',error=str(e),finished=now());state['reconciliation_required']=True;save(root,state);raise

def perform(root,event,name,client):
 if name=='status':return client.status()
 if name=='reset-status':return client.reset_status()
 status=client.status() # explicit reconciliation precedes any action
 if name=='configure':return client.configure_trigger() # bounded immediate capture; no trigger history
 if name=='arm':return client.arm()
 if name=='stop':return client.stop()
 if name=='eject':return client.eject()
 if name in ('reset','arm-reset'):return client.reset(arm=name=='arm-reset')
 if name=='download':
  path=root/'artifacts'/f"capture-{event['id']}.p1715";client.download(path)
  event['artifacts'].append({'path':str(path.relative_to(root)),'sha256':sha(path)})
  return {'capture_sha256':sha(path),'device_status':status}
 raise ValueError('Unsupported action')
def reconcile(state,note):
 if not note:raise ValueError('Reconciliation requires operator notes')
 unresolved=[a for a in state['actions'] if a['state'] in ('pending','unknown')]
 last_unknown=max((a['id'] for a in unresolved),default=0)
 if last_unknown and not any(a['id']>last_unknown and a['state']=='complete' and a['action']=='status' for a in state['actions']):raise ValueError('Read fresh device status before reconciliation')
 for a in unresolved:a['state']='reconciled';a['reconciliation']=note
 state['reconciliation_required']=False

def report(root,state):
 verify(root,state)
 return {**state,'stages_pending':[s for s in STAGES if state['stages'].get(s,{}).get('result')!='pass'],'physical_qualification':False,'qualification_note':'Guided evidence package only. Review electrical measurements and device test evidence independently; simulated results never qualify hardware.'}
def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 initp=sub.add_parser('init');initp.add_argument('run',type=Path);initp.add_argument('--mode',choices=['simulated','physical'],required=True);initp.add_argument('--board',required=True);initp.add_argument('--firmware',type=Path,required=True);initp.add_argument('--bitstream',type=Path,required=True)
 for name in ('show','record','action','reconcile','export','assert'):
  q=sub.add_parser(name);q.add_argument('run',type=Path)
  if name=='record':q.add_argument('stage',choices=STAGES);q.add_argument('evidence',type=Path)
  if name=='action':
   q.add_argument('action',choices=ACTIONS);q.add_argument('--personality',choices=['analyzer','controller'],default='analyzer');q.add_argument('--port');q.add_argument('--execute',action='store_true');q.add_argument('--replay',type=Path)
  if name=='reconcile':q.add_argument('--note',required=True)
  if name=='export':q.add_argument('output',type=Path)
  if name=='assert':
   q.add_argument('--capture',type=Path,required=True);q.add_argument('--suite',type=Path,required=True);q.add_argument('--dac',type=Path,required=True);q.add_argument('--node',default='node')
 a=p.parse_args()
 if a.command=='init':init(a.run,a.mode,a.board,a.firmware,a.bitstream);return
 with opened(a.run) as (root,state):
  if a.command=='show':print(json.dumps({'stages':STAGES,'run':report(root,state)},indent=2))
  elif a.command=='record':record(root,state,a.stage,a.evidence)
  elif a.command=='action':print(json.dumps(action(root,state,a.action,a.personality,a.execute,a.port,replay=a.replay),indent=2))
  elif a.command=='reconcile':reconcile(state,a.note)
  elif a.command=='export':
   # Copy all evidence to a new standalone directory; never overwrite a prior export.
   a.output.mkdir(parents=True,exist_ok=False);shutil.copytree(root/'artifacts',a.output/'artifacts');(a.output/'report.json').write_text(json.dumps(report(root,state),indent=2)+'\n')
  elif a.command=='assert':
   n=len(state['actions'])+1;capture=attach(root,a.capture,f'assert-{n}.p1715');suite=attach(root,a.suite,f'assert-{n}.suite.json');out=root/'artifacts'/f'assert-{n}.json'
   cmd=[a.node,str(a.dac/'tools/analyzer/check.mjs'),str(root/capture['path']),str(root/suite['path']),str(out)]
   state['actions'].append({'id':n,'action':'assert','state':'pending','artifacts':[capture,suite],'started':now()});save(root,state)
   completed=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
   event=state['actions'][-1];event.update(state='complete' if completed.returncode in (0,1) else 'failed',exit_status=completed.returncode,stderr=completed.stderr,finished=now())
   if out.exists():event['artifacts'].append({'path':str(out.relative_to(root)),'sha256':sha(out)})
   save(root,state);print(json.dumps(event,indent=2))
   if completed.returncode:raise SystemExit(completed.returncode)
if __name__=='__main__':main()
