// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import {loadAdapter} from './replay.mjs';
import {replay,sha256} from './experiment.mjs';
const [native,wasm]=process.argv.slice(2);if(!wasm)throw Error('Usage: native-build wasm-build');
const rom=new Uint8Array(2048),disk=new Uint8Array(819200);rom.set([0xc3,0,0]);
for(const backend of ['model','firmware'])for(const absent of [false,true]){
 const e={schema:1,kind:'pico1715-experiment',backend,absent,writable:false,rom_sha256:await sha256(rom),disk_sha256:await sha256(disk),engine_sha256:'0'.repeat(64),end_clock:10000,actions:[]};
 if(!absent){for(const [fault,value] of [['crc',1],['drop-byte',100],['read-delay',20],['write-delay',30]])e.actions.push({clock:123,type:'fault',fault,value});
  if(backend==='firmware')e.actions.push({clock:1000,type:'fault',fault:'sd-delay',value:1000},{clock:2000,type:'fault',fault:'power-fail',value:1});
  else e.actions.push({clock:2000,type:'fault',fault:'write-protect',value:1});
 }
 const results=[];
 for(const module of [`${native}/pico1715-${backend}.so`,`${wasm}/pico1715-${backend}.mjs`]){
  const a=await loadAdapter(module,rom,disk,false,absent);
  try{results.push(await replay(a,e));assert((await a.call('sim_fault',99,1))<0);}catch(e){throw Error(module+': '+e.message,{cause:e});}finally{a.close();}
 }
 assert.deepEqual(results[0],results[1]);if(!absent){assert.deepEqual(results[0].final.fault_state.slice(3),[1,100,20,30]);if(backend==='firmware')assert.equal(results[0].final.fault_state[0],2);}
 assert.equal(results[0].final.counters[3],0);
 console.log(`${backend} ${absent?'absent media':'scheduled faults and shutdown'} native/WASM parity PASS`);
}
