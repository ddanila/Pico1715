#!/usr/bin/env node
// SPDX-License-Identifier: MIT
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
import {loadAdapter} from './replay.mjs';
import {replay,sha256,engineIdentity,makeBundle,FAULTS} from './experiment.mjs';
import {Capture} from '../../../dac/src/analyzer/capture.js';
import {evaluate,defaultSuite} from '../../../dac/src/analyzer/assertions.js';

const [modulePath,backend,romPath,diskPath,scenario,outPath,command='',clockText='40000000',faultClockText='0',reduceText='0']=process.argv.slice(2);
if(!outPath||!['model','firmware'].includes(backend)||!['crc','drop-byte','read-delay','write-delay','sd-delay','sd-write-failure','power-fail','absent','readonly'].includes(scenario))throw Error('Usage: fault-investigation.mjs module model|firmware rom disk scenario new-output-dir [command] [end-clock] [fault-clock] [reduction-attempts]');
const module=resolve(modulePath),out=resolve(outPath),clocks=Number(clockText),faultClock=Number(faultClockText),reductions=Number(reduceText);
if(!Number.isSafeInteger(clocks)||clocks<1||clocks>294960000||!Number.isSafeInteger(faultClock)||faultClock<0||faultClock>=clocks||!Number.isInteger(reductions)||reductions<0||reductions>8)throw Error('Invalid investigation limits');
if([...command].some(c=>c.charCodeAt(0)<1||c.charCodeAt(0)>127)||command.length>4096)throw Error('Invalid ASCII command');
const rom=await readFile(romPath),disk=await readFile(diskPath),moduleHash=await sha256(await readFile(module));
const engine=module.endsWith('.so')?moduleHash:await engineIdentity(moduleHash,await sha256(await readFile(module.replace(/\.mjs$/,'.wasm'))));
const build=JSON.parse(await readFile(resolve(dirname(module),'manifest.json'),'utf8'));
const base={schema:1,kind:'pico1715-experiment',backend,build,rom_sha256:await sha256(rom),disk_sha256:await sha256(disk),engine_sha256:engine,writable:!!command,end_clock:clocks,actions:[{clock:0,type:'capture-start',bytes:16*1048576,mask:0x170,clocks:0}]};
if(command){if(clocks<=30000000)throw Error('Command workloads need more than 30M clocks');for(const c of command.replace(/\n/g,'\r'))base.actions.push({clock:30000000,type:'key',value:c.charCodeAt(0)});}
base.actions.push({clock:clocks,type:'capture-stop'},{clock:clocks,type:'checkpoint',name:'end'});
const injected=structuredClone(base);
if(scenario==='absent')injected.absent=true;
else if(scenario==='readonly')injected.writable=false;
else {
 const value={crc:1,'drop-byte':100,'read-delay':500,'write-delay':500,'sd-delay':10000,'sd-write-failure':1,'power-fail':1}[scenario];
 if(backend==='model'&&FAULTS[scenario].id>4)throw Error('Selected fault requires the firmware backend');
 injected.actions.push({clock:faultClock,type:'fault',fault:scenario,value});
 injected.actions.sort((a,b)=>a.clock-b.clock);
}
await mkdir(out,{recursive:false});
async function run(experiment,name){
 await writeFile(`${out}/${name}.experiment.json`,JSON.stringify(experiment,null,2)+'\n',{flag:'wx'});
 let adapter,execution,bytes,screen,output,capturedClocks;
 try{
  adapter=await loadAdapter(module,rom,disk,experiment.writable,experiment.absent);
  execution=await replay(adapter,experiment);
  if(await adapter.call('capture_status',0)!==2)throw Error('Capture did not drain');
  bytes=await adapter.read('capture_data',await adapter.call('capture_status',2));capturedClocks=await adapter.call('capture_status',4);screen=new TextDecoder().decode(await adapter.read('screen',1920));output=await adapter.read('disk',819200);
 }catch(error){const report={schema:1,hardware_executed:false,scenario,name,execution_error:error.message,first_failure:null,assertions:{results:[{id:'execution',outcome:'inconclusive'}]}};await writeFile(`${out}/${name}.json`,JSON.stringify(report,null,2)+'\n',{flag:'wx'});await writeFile(`${out}/${name}.p1715investigation`,JSON.stringify(await makeBundle(experiment,[{name:'report.json',bytes:new TextEncoder().encode(JSON.stringify(report))}])) ,{flag:'wx'});return report;}finally{adapter?.close();}
 const capture=await Capture.open(new Blob([bytes])),assertions=await evaluate(capture,defaultSuite);
 const first=assertions.results.filter(r=>r.outcome==='fail').sort((a,b)=>(a.first_violation?.record??Infinity)-(b.first_violation?.record??Infinity))[0]||null;
 const observed=assertions.results.filter(r=>r.first_violation).sort((a,b)=>a.first_violation.record-b.first_violation.record)[0]||null;
 const report={schema:1,hardware_executed:false,scenario,name,execution,assertions,suite:defaultSuite,first_failure:first,first_observed_violation:observed,screen,disk_sha256:await sha256(output),disk_changed:await sha256(output)!==experiment.disk_sha256,disk_semantics:'Session-visible image; no implicit flush or physical durability claim'};
 const metadata={schema:1,backend,build,rom_sha256:experiment.rom_sha256,disk_sha256:experiment.disk_sha256,start_clock:0,end_clock:capturedClocks,capture_sha256:capture.summary.sha256,writes_at_start:0,filter:'io',complete:true,observations:[],timing:'Simulated sampled bus events; not physical timing'};
 const encode=value=>new TextEncoder().encode(JSON.stringify(value));
 const bundle=await makeBundle(experiment,[{name:'capture.p1715',bytes},{name:'capture.metadata.json',bytes:encode(metadata)},{name:'report.json',bytes:encode(report)}]);
 await writeFile(`${out}/${name}.p1715investigation`,JSON.stringify(bundle),{flag:'wx'});
 await writeFile(`${out}/${name}.json`,JSON.stringify(report,null,2)+'\n',{flag:'wx'});
 await writeFile(`${out}/${name}.img`,output,{flag:'wx'});
 return report;
}
const control=await run(base,'control'),fault=await run(injected,'fault');
const signature=r=>{const finding=r.first_failure||r.first_observed_violation;return finding?JSON.stringify([finding.id,finding.outcome,finding.reason]):null;};
let reduced=injected,attempts=0,accepted=0;
if(signature(fault)&&!signature(control))for(let i=reduced.actions.length-1;i>=0&&attempts<reductions;i--){
 if(!['key','cancel'].includes(reduced.actions[i].type))continue;
 const candidate=structuredClone(reduced);candidate.actions.splice(i,1);const result=await run(candidate,'reduction-'+ ++attempts);
 if(signature(result)===signature(fault)){reduced=candidate;accepted++;}
}
await writeFile(`${out}/summary.json`,JSON.stringify({schema:1,hardware_executed:false,scenario,control_pass:control.assertions.results.every(r=>r.outcome==='pass'),fault_first_failure:fault.first_failure,first_observed_violation:fault.first_observed_violation,first_failure_is_root_cause:false,reduction:{attempts,accepted,signature:signature(fault),retained_actions:reduced.actions.length},original_preserved:true},null,2)+'\n',{flag:'wx'});
console.log('Investigation recorded:',out,'control all-pass:',control.assertions.results.every(r=>r.outcome==='pass'),'fault:',fault.first_failure?.id||'no conclusive assertion failure');
