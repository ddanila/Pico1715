// SPDX-License-Identifier: MIT
// Headless browser-module runner for parity checks; no UI, sleep or backpressure.
import {readFile,writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const [modulePath,romPath,diskPath,output,limit='20000000',command='']=process.argv.slice(2);
const factory=(await import(pathToFileURL(modulePath))).default;
const m=await factory({printErr:()=>{},preRun:[m=>{for(const [k,v] of Object.entries(process.env))if(k.startsWith('PICO1715_'))m.ENV[k]=v;}]});
const rom=await readFile(romPath),disk=await readFile(diskPath),p=m._malloc(rom.length),q=m._malloc(disk.length);
m.HEAPU8.set(rom,p);m.HEAPU8.set(disk,q);
m._p1715_init(p,rom.length,q,disk.length,1);if(m._p1715_result())throw Error('init failed');m._free(p);m._free(q);
let sent=false;
for(let tick=0;tick<Number(limit);){
 if(tick>=20000000&&!sent){for(const c of command)m._p1715_key(c.charCodeAt(0));sent=true;}
 const n=Math.min(1024,Number(limit)-tick,tick<20000000?20000000-tick:1024);m._p1715_run(n);tick+=m._p1715_result();
}
let r;do{m._p1715_export();r=m._p1715_result();}while(!r);if(r<0)throw Error('export failed');
// Continue after a nonterminal export, and optionally reset with no event replay.
m._p1715_run(8192);
if(process.env.PICO1715_TEST_RESET){m._p1715_reset();m._p1715_run(8192);}
do{m._p1715_export();r=m._p1715_result();}while(!r);if(r<0)throw Error('second export failed');
await writeFile(output+'.ram',m.HEAPU8.slice(m._p1715_ram(),m._p1715_ram()+65536));
await writeFile(output+'.img',m.HEAPU8.slice(m._p1715_disk(),m._p1715_disk()+819200));
await writeFile(output+'.json',JSON.stringify({registers:Array.from({length:23},(_,i)=>m._p1715_reg(i)),stats:Array.from({length:25},(_,i)=>m._p1715_stat(i))}));
console.log(new TextDecoder().decode(m.HEAPU8.slice(m._p1715_screen(),m._p1715_screen()+1920)));
