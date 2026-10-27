// SPDX-License-Identifier: MIT
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {checkpoint,replay,validateExperiment,makeBundle,openBundle,sha256,wasmAdapter} from './experiment.mjs';
const base=()=>({schema:1,kind:'pico1715-experiment',backend:'model',writable:false,rom_sha256:'a'.repeat(64),disk_sha256:'b'.repeat(64),engine_sha256:'c'.repeat(64),end_clock:100,actions:[]});
function adapter(){let clock=0,value=0,exports=0;return {get exports(){return exports;},async call(name,...args){if(name==='stat')return args[0]===0?clock:value;if(name==='reg')return value;if(name==='run'){clock+=args[0];return args[0];}if(name==='key'){value=args[0];return 0;}if(name==='reset')value=0;if(name==='export'){exports++;return exports%3===0?1:0;}return 0;},async read(name,size){return new Uint8Array(size).fill(value);}};}
test('clock boundaries, stable same-clock ordering and chunk invariance',async()=>{
 const e=base();e.actions=[{clock:17,type:'key',value:65},{clock:17,type:'reset'},{clock:17,type:'key',value:66},{clock:18,type:'checkpoint',name:'after'}];
 const a=await replay(adapter(),e,{chunk:7}),b=await replay(adapter(),e,{chunk:100});assert.deepEqual(a,b);assert.equal(a.checkpoints[0].actual.clock,18);assert.equal(a.final.registers[0],66);
});
test('checkpoint does not flush and divergence stops at first checkpoint',async()=>{
 const a=adapter();await checkpoint(a);assert.equal(a.exports,0);const e=base();e.actions=[{clock:10,type:'checkpoint',name:'wrong',expected:{clock:11}},{clock:20,type:'export',calls:3}];
 const r=await replay(a,e);assert.equal(r.status,'diverged');assert.equal(r.first_divergence,0);assert.equal(a.exports,0);
});
test('export firmware progress is explicit and checked',async()=>{
 const e=base();e.actions=[{clock:0,type:'export',calls:3}];assert.equal((await replay(adapter(),e)).status,'complete');e.actions[0].calls=2;await assert.rejects(replay(adapter(),e),/Export progress/);
});
test('reject invalid schedules, unsupported actions and excessive work',()=>{
 for(const mutate of [e=>e.end_clock=Infinity,e=>e.actions=[{clock:-1,type:'reset'}],e=>e.actions=[{clock:30,type:'reset'},{clock:20,type:'reset'}],e=>e.actions=[{clock:1,type:'shell'}],e=>e.actions=[{clock:1,type:'key',value:128}],e=>e.actions=Array(10001).fill({clock:1,type:'reset'}),e=>e.engine_sha256='']){const e=base();mutate(e);assert.throws(()=>validateExperiment(e));}
});
test('cancellation stops before an action',async()=>{const c=new AbortController();c.abort();const e=base();e.actions=[{clock:0,type:'reset'}];await assert.rejects(replay(adapter(),e,{signal:c.signal}),/cancelled/);});
test('bundle roundtrip and corrupt/traversal/duplicate controls',async()=>{
 const bytes=new Uint8Array([0,1,255]);const bundle=await makeBundle(base(),[{name:'capture.p1715',bytes}]);assert.deepEqual((await openBundle(JSON.stringify(bundle))).files[0].bytes,bytes);
 for(const mutate of [b=>b.files[0].sha256='0'.repeat(64),b=>b.files[0].name='../rom',b=>b.files.push(b.files[0]),b=>b.files[0].size++,b=>b.schema=2]){const b=structuredClone(bundle);mutate(b);await assert.rejects(openBundle(JSON.stringify(b)));}
 assert.equal(bundle.files[0].sha256,await sha256(bytes));
});
test('fault validation rejects inherited names and unsupported backend actions',()=>{
 for(const [backend,fault,value] of [['model','__proto__',0],['model','sd-delay',10],['firmware','write-protect',1],['firmware','power-fail',0],['model','crc',2]]){const e=base();e.backend=backend;e.actions=[{clock:0,type:'fault',fault,value}];assert.throws(()=>validateExperiment(e));}
});
test('WASM execution uses the explicit result slot after a context switch',()=>{
 const adapter=wasmAdapter({_p1715_run:()=>undefined,_p1715_result:()=>37});assert.equal(adapter.call('run',37),37);
});
