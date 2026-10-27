// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';import {readFile,writeFile} from 'node:fs/promises';import {pathToFileURL} from 'node:url';
const [build,reference]=process.argv.slice(2);
for(const backend of ['model','firmware'])for(const mode of ['full','io','size','time','reset','empty']){
 const m=await(await import(pathToFileURL(`${build}/pico1715-${backend}.mjs`))).default();
 const rom=new Uint8Array(2048);rom.set(Buffer.from('3150fe3e55d340db40c30300','hex'));const p=m._malloc(2048),q=m._malloc(819200);m.HEAPU8.set(rom,p);m.HEAPU8.fill(0,q,q+819200);assert.equal(m._p1715_init(p,2048,q,819200,0),0);m._free(p);m._free(q);
 assert.equal(m._p1715_capture_start(mode==='size'?8192:1048576,mode==='io'?0x170:0x3fe,mode==='time'?400:0),0);if(mode==='reset')m._p1715_reset();m._p1715_run(mode==='empty'?0:10000);m._p1715_capture_stop();assert.equal(m._p1715_capture_status(0),2);
 const ptr=m._p1715_capture_data(),bytes=Buffer.from(m.HEAPU8.slice(ptr,ptr+m._p1715_capture_status(2)));
 assert.deepEqual(bytes,await readFile(`${reference}/${backend}-${mode}.p1715`),`${backend} ${mode} native/WASM parity`);m._p1715_capture_release();
 console.log(`${backend} ${mode}: native/WASM byte parity PASS`);
}
