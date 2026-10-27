#!/usr/bin/env node
// SPDX-License-Identifier: MIT
import {readFile,writeFile} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {resolve,dirname,basename} from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {replay,sha256,validateExperiment,wasmAdapter,engineIdentity,openBundle} from './experiment.mjs';

export async function nativeAdapter(module,rom,disk,writable,absent=false) {
  const env=Object.fromEntries(Object.entries(process.env).filter(([k])=>!k.startsWith('PICO1715_')));
  const child=spawn('python3',[fileURLToPath(new URL('./native-session.py',import.meta.url)),resolve(module)],{stdio:['pipe','pipe','inherit'],env});
  const pending=[];let failed;
  const fail=error=>{failed=error;for(const p of pending.splice(0))p.reject(error);};
  child.on('error',fail);child.on('exit',code=>fail(Error(`Native session exited (${code})`)));
  createInterface({input:child.stdout}).on('line',line=>{const p=pending.shift();if(!p)return;try{const r=JSON.parse(line);r.error?p.reject(Error(r.error)):p.resolve(r.result);}catch(e){p.reject(e);}});
  const request=value=>new Promise((resolve,reject)=>{if(failed)return reject(failed);pending.push({resolve,reject});child.stdin.write(JSON.stringify(value)+'\n');});
  const close=()=>{child.stdin.end();child.kill();};
  try {
    if(await request({op:'init',rom:Buffer.from(rom).toString('hex'),disk:Buffer.from(disk).toString('hex'),writable,absent})!==0)throw Error('Session initialization failed');
    return {call:(name,...args)=>request({op:'call',name,args}),read:async(name,length)=>new Uint8Array(Buffer.from(await request({op:'read',name,length}),'hex')),close};
  }catch(e){close();throw e;}
}
export async function loadAdapter(module,rom,disk,writable,absent=false) {
  if(module.endsWith('.so'))return nativeAdapter(module,rom,disk,writable,absent);
  const core=await(await import(pathToFileURL(resolve(module)))).default();
  const p=core._malloc(rom.length),q=core._malloc(disk.length);
  try{core.HEAPU8.set(rom,p);core.HEAPU8.set(disk,q);if(absent&&(!core._p1715_sim_config||core._p1715_sim_config(1)!==0))throw Error('Absent-media capability unavailable');if(core._p1715_init(p,rom.length,q,disk.length,+writable)!==0)throw Error('Session initialization failed');}finally{core._free(p);core._free(q);}
  return {...wasmAdapter(core),close(){}};
}
async function main() {
  const args=process.argv.slice(2),rebind=args.includes('--rebind-engine');
  const [module,script,romPath,diskPath,output]=args.filter(a=>a!=='--rebind-engine');
  if(!output)throw Error('Usage: replay.mjs module.so|module.mjs experiment.json|bundle rom|- disk|- new-report.json [--rebind-engine]');
  const text=await readFile(script,'utf8'),parsed=JSON.parse(text),bundle=parsed.kind==='pico1715-investigation'?await openBundle(text):null;
  const experiment=validateExperiment(bundle?bundle.experiment:parsed);
  async function input(path,name){if(path!=='-')return readFile(path);const file=bundle?.files.find(f=>f.name===name);if(!file)throw Error('Missing input '+name);return file.bytes;}
  const rom=await input(romPath,'initial.rom'),disk=await input(diskPath,'initial.img');
  if(await sha256(rom)!==experiment.rom_sha256||await sha256(disk)!==experiment.disk_sha256)throw Error('Input identity mismatch');
  const jsHash=await sha256(await readFile(module));
  const engine=module.endsWith('.so')?jsHash:await engineIdentity(jsHash,await sha256(await readFile(module.replace(/\.mjs$/,'.wasm'))));
  if(engine!==experiment.engine_sha256){
    if(!rebind)throw Error('Engine identity mismatch');
    const manifest=JSON.parse(await readFile(resolve(dirname(module),'manifest.json'),'utf8'));
    if(![`pico1715-${experiment.backend}.so`,`pico1715-${experiment.backend}.mjs`].includes(basename(module))||manifest.dirty||!experiment.build||experiment.build.dirty||manifest.pico!==experiment.build.pico||manifest.dac!==experiment.build.dac||manifest.sha256[basename(module)]!==jsHash)throw Error('Rebinding requires matching clean source revisions and checked target artifacts');
  }
  const adapter=await loadAdapter(module,rom,disk,experiment.writable,experiment.absent);
  try{const result=await replay(adapter,experiment);result.engine={recorded:experiment.engine_sha256,executed:engine,rebound:engine!==experiment.engine_sha256};await writeFile(output,JSON.stringify(result,null,2)+'\n',{flag:'wx'});if(result.status!=='complete')process.exitCode=1;}finally{adapter.close();}
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href)main().catch(e=>{console.error(e.message);process.exitCode=2;});
