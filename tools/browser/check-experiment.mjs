// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {loadAdapter} from './replay.mjs';
import {replay,sha256} from './experiment.mjs';
const [native,wasm]=process.argv.slice(2);
if(!wasm)throw Error('Usage: check-experiment.mjs native-build wasm-build');
const rom=new Uint8Array(2048),disk=new Uint8Array(819200);
rom.set(Buffer.from('3150fe3e55d340db40c30300','hex'));
for(const backend of ['model','firmware']){
 const e={schema:1,kind:'pico1715-experiment',backend,writable:false,rom_sha256:await sha256(rom),disk_sha256:await sha256(disk),engine_sha256:'0'.repeat(64),end_clock:14000,actions:[
  {clock:0,type:'capture-start',bytes:1048576,mask:0x170,clocks:0},
  {clock:117,type:'key',value:65},{clock:117,type:'key',value:66},
  {clock:501,type:'checkpoint',name:'first'},
  {clock:1101,type:'cancel'},{clock:2033,type:'reset'},
  {clock:8001,type:'capture-stop'},{clock:13000,type:'checkpoint',name:'last'}]};
 const results=[],captures=[];
 for(const [module,chunk] of [[`${native}/pico1715-${backend}.so`,7],[`${wasm}/pico1715-${backend}.mjs`,16384]]){
  const a=await loadAdapter(module,rom,disk,false);
  try{results.push(await replay(a,e,{chunk}));captures.push(await a.read('capture_data',await a.call('capture_status',2)));}finally{a.close();}
 }
 assert.deepEqual(results[0],results[1],`${backend} state/checkpoint native-WASM parity`);assert.deepEqual(captures[0],captures[1],`${backend} scheduled capture parity`);
 // Replay recorded checkpoints and deliberately corrupt one independent expectation.
 e.actions[3].expected=results[0].checkpoints[0].actual;
 e.actions[7].expected={...results[0].checkpoints[1].actual,ram_sha256:'0'.repeat(64)};
 const a=await loadAdapter(`${native}/pico1715-${backend}.so`,rom,disk,false);
 try{const r=await replay(a,e);assert.equal(r.status,'diverged');assert.equal(r.first_divergence,7);assert.deepEqual(r.checkpoints.at(-1).differences,['ram_sha256']);}finally{a.close();}
 console.log(`${backend}: native/WASM scheduled replay, capture and divergence PASS`);
}
