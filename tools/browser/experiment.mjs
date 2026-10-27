// SPDX-License-Identifier: MIT
// Shared orchestration: adapters expose the same session ABI in WASM or native.
export const LIMIT_CLOCKS = 294960000;
export const LIMIT_ACTIONS = 10000;
export const FAULTS=Object.freeze({'crc':{id:0,max:1},'drop-byte':{id:1,max:1030},'read-delay':{id:2,max:2458000},'write-delay':{id:3,max:2458000},'write-protect':{id:4,max:1},'sd-delay':{id:5,max:1000000},'sd-write-failure':{id:6,max:1},'power-fail':{id:7,max:1}});
const hashPattern = /^[0-9a-f]{64}$/;
export async function sha256(bytes) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
}
export async function engineIdentity(javascriptHash, wasmHash) {
  return sha256(new TextEncoder().encode(JSON.stringify({javascript:javascriptHash,wasm:wasmHash})));
}
function integer(value, min, max, name) {
  if (!Number.isSafeInteger(value) || value < min || value > max) throw Error(`Invalid ${name}`);
}
export function validateExperiment(value) {
  if (!value || value.schema !== 1 || value.kind !== 'pico1715-experiment') throw Error('Unsupported experiment');
  if (!['model','firmware'].includes(value.backend) || typeof value.writable !== 'boolean') throw Error('Invalid experiment configuration');
  if(value.absent!==undefined&&typeof value.absent!=='boolean')throw Error('Invalid initial media configuration');
  for (const key of ['rom_sha256','disk_sha256']) if (!hashPattern.test(value[key] || '')) throw Error(`Invalid ${key}`);
  if (!hashPattern.test(value.engine_sha256 || '')) throw Error('Missing engine identity');
  integer(value.end_clock, 0, LIMIT_CLOCKS, 'end clock');
  if (!Array.isArray(value.actions) || value.actions.length > LIMIT_ACTIONS) throw Error('Invalid action count');
  let previous = 0;
  for (const action of value.actions) {
    integer(action.clock, previous, value.end_clock, 'action clock'); previous = action.clock;
    switch (action.type) {
      case 'fault': {if(typeof action.fault!=='string'||!Object.hasOwn(FAULTS,action.fault))throw Error('Unsupported fault');const f=FAULTS[action.fault];integer(action.value,action.fault==='power-fail'?1:0,f.max,'fault value');if(value.backend==='model'&&f.id>4)throw Error('Fault requires firmware backend');if(value.backend==='firmware'&&f.id===4)throw Error('Firmware write protection is an initial session policy');break;}
      case 'key': integer(action.value, 1, 127, 'key'); break;
      case 'cancel': case 'reset': case 'capture-stop': case 'capture-release': break;
      case 'export': integer(action.calls, 1, 100000, 'export calls'); break;
      case 'capture-start':
        integer(action.bytes, 8192, 64*1048576, 'capture bytes');
        integer(action.clocks, 0, LIMIT_CLOCKS, 'capture clocks');
        if (![0x170,0x3fe].includes(action.mask)) throw Error('Invalid capture mask');
        break;
      case 'checkpoint':
        if (typeof action.name !== 'string' || !/^[\w.-]{1,64}$/.test(action.name)) throw Error('Invalid checkpoint name');
        if (action.expected !== undefined && (!action.expected || typeof action.expected !== 'object' || Array.isArray(action.expected))) throw Error('Invalid checkpoint expectation');
        break;
      default: throw Error(`Unsupported experiment action: ${action.type}`);
    }
  }
  return value;
}
export function wasmAdapter(core) {
  return {
    call(name, ...args) { const fn=core['_p1715_'+name]; if (!fn) throw Error(`Missing session capability: ${name}`); const value=fn(...args);return ['run','step','export','init'].includes(name)?core._p1715_result():value; },
    read(name, length) { return core.HEAPU8.slice(core['_p1715_'+name](), core['_p1715_'+name]()+length); },
  };
}
export async function checkpoint(adapter) {
  const registers=[]; for(let i=0;i<23;i++) registers.push(await adapter.call('reg',i));
  const counters=[]; for(let i=0;i<25;i++) counters.push(await adapter.call('stat',i));
  const fault_state=[];for(let i=25;i<32;i++)fault_state.push(await adapter.call('stat',i));
  return {clock:counters[0],registers,counters,fault_state,
    ram_sha256:await sha256(await adapter.read('ram',65536)),
    screen_sha256:await sha256(await adapter.read('screen',1920)),
    disk_sha256:await sha256(await adapter.read('disk',819200))};
}
export async function applyAction(adapter, action) {
  let result;
  switch(action.type) {
    case 'fault': {const f=FAULTS[action.fault],caps=await adapter.call('sim_capabilities');if(!(caps&(1<<f.id)))throw Error('Fault capability unavailable');result=await adapter.call('sim_fault',f.id,action.value);break;}
    case 'key': result=await adapter.call('key',action.value); break;
    case 'reset': await adapter.call('reset'); return;
    case 'cancel': await adapter.call('cancel'); return;
    case 'capture-start': result=await adapter.call('capture_start',action.bytes,action.mask,action.clocks); break;
    case 'capture-stop': await adapter.call('capture_stop'); return;
    case 'capture-release': await adapter.call('capture_release'); return;
    case 'export':
      for(let i=0;i<action.calls;i++) {
        result=await adapter.call('export');
        if(result<0 || (result===1)!==(i===action.calls-1)) throw Error('Export progress diverged');
      }
      return;
    case 'checkpoint': return checkpoint(adapter);
    default: throw Error('Unsupported action');
  }
  if(result<0) throw Error(`${action.type} rejected (${result})`);
}
// Adapter is fresh, initialized, and exclusively owned for the replay duration.
export async function replay(adapter, experiment, {signal,onProgress=()=>{},yieldControl=()=>Promise.resolve(),chunk=16384}={}) {
  validateExperiment(experiment); integer(chunk,1,1048576,'chunk');
  if(await adapter.call('stat',0)!==0) throw Error('Replay requires a fresh session');
  const results=[];
  const check=()=>{if(signal?.aborted)throw Error('Replay cancelled');};
  async function advance(target) {
    let now=await adapter.call('stat',0);
    if(now>target) throw Error('Action clock crossed by preceding operation');
    while(now<target) {
      check(); const budget=Math.min(chunk,target-now),used=await adapter.call('run',budget);
      if(used!==budget) throw Error('Session did not reach scheduled clock');
      now=await adapter.call('stat',0);onProgress(now);await yieldControl();
    }
  }
  await adapter.call('break',-1);
  for(let i=0;i<experiment.actions.length;i++) {
    check(); const action=experiment.actions[i];await advance(action.clock);
    const actual=await applyAction(adapter,action);
    if(action.type==='checkpoint') {
      const differences=action.expected ? Object.keys(action.expected).filter(k=>JSON.stringify(actual[k])!==JSON.stringify(action.expected[k])) : [];
      results.push({index:i,name:action.name,actual,differences,verified:action.expected!==undefined});
      if(differences.length) return {schema:1,status:'diverged',first_divergence:i,checkpoints:results};
    }
  }
  await advance(experiment.end_clock);
  return {schema:1,status:'complete',checkpoints:results,final:await checkpoint(adapter)};
}

// JSON archive: no extraction or execution; names are flat and content addressed.
export async function makeBundle(experiment, files=[]) {
  if(experiment!==null)validateExperiment(experiment);
  if(files.length>64)throw Error('Too many bundle files');
  const result={schema:1,kind:'pico1715-investigation',experiment,files:[]};let total=0;const names=new Set();
  for(const {name,bytes} of files) {
    if(!/^[\w.-]{1,100}$/.test(name)||name==='.'||name==='..'||names.has(name))throw Error('Invalid or duplicate bundle name');
    names.add(name);total+=bytes.length;if(total>128*1048576)throw Error('Bundle exceeds 128 MiB');
    let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
    result.files.push({name,sha256:await sha256(bytes),size:bytes.length,base64:btoa(binary)});
  }
  return result;
}
export async function openBundle(text) {
  if(typeof text!=='string'||text.length>180*1048576)throw Error('Bundle too large');
  const bundle=JSON.parse(text);
  if(bundle?.schema!==1||bundle.kind!=='pico1715-investigation'||!Array.isArray(bundle.files)||bundle.files.length>64)throw Error('Unsupported bundle');
  if(bundle.experiment!==null)validateExperiment(bundle.experiment);const files=[];let total=0;
  for(const file of bundle.files) {
    integer(file.size,0,128*1048576,'file size');total+=file.size;
    if(total>128*1048576||typeof file.base64!=='string'||file.base64.length!==4*Math.ceil(file.size/3))throw Error('Invalid bundle size');
    if(/[^A-Za-z0-9+/=]/.test(file.base64))throw Error('Invalid base64');
    const bytes=Uint8Array.from(atob(file.base64),c=>c.charCodeAt(0));
    if(btoa(atob(file.base64))!==file.base64)throw Error('Noncanonical base64');
    if(bytes.length!==file.size||await sha256(bytes)!==file.sha256)throw Error('Bundle checksum mismatch');
    files.push({name:file.name,bytes});
  }
  // Reuse name/duplicate validation after content checks.
  const names=new Set();for(const {name} of files){if(!/^[\w.-]{1,100}$/.test(name)||name==='.'||name==='..'||names.has(name))throw Error('Invalid or duplicate bundle name');names.add(name);}
  return {experiment:bundle.experiment,files};
}
