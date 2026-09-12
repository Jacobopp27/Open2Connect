const test=require('node:test');
const assert=require('node:assert/strict');
const Voice=require('../frontend/realtime.js');
global.document={removeEventListener(){},addEventListener(){}};
test('closing releases microphone, playback and peer',()=>{
 const v=new Voice();let stops=0,closes=0,pauses=0;
 v.stream={getTracks:()=>[{stop:()=>stops++}]};v.pc={close:()=>closes++};
 v.audioEl={pause:()=>pauses++,srcObject:{}};
 v.cerrar();assert.equal(stops,1);assert.equal(closes,1);assert.equal(pauses,1);assert.equal(v.stream,null);
});
test('a repeated function call executes a tool only once',async()=>{
 let count=0;const v=new Voice({tools:{save:async()=>{count++;return {ok:true}}}});
 const sent=[];v.dc={readyState:'open',send:s=>sent.push(JSON.parse(s))};
 const event={call_id:'one',name:'save',arguments:'{}'};
 await Promise.all([v._ejecutarHerramienta(event),v._ejecutarHerramienta(event)]);
 assert.equal(count,1);assert.equal(sent.filter(e=>e.type==='function_call_output').length,0);
 assert.equal(sent.filter(e=>e.type==='conversation.item.create').length,1);
});
test('closed sessions do not send late tool results',async()=>{
 let resolve;const v=new Voice({tools:{save:()=>new Promise(r=>resolve=r)}});
 const result=v._ejecutarHerramienta({call_id:'one',name:'save',arguments:'{}'});
 v.cerrar();let sent=0;v.dc={readyState:'open',send:()=>sent++};resolve({ok:true});await result;assert.equal(sent,0);
});
test('microphone acquired after cancellation is immediately stopped',async()=>{
 let resolve,stopped=0;
 global.fetch=async()=>({ok:true,json:async()=>({value:'fake'})});
 global.RTCPeerConnection=class{close(){}};
 Object.defineProperty(global,'navigator',{configurable:true,value:{mediaDevices:{getUserMedia:()=>new Promise(r=>resolve=r)}}});
 const v=new Voice();const start=v.conectar();
 while(!resolve)await new Promise(r=>setImmediate(r));
 v.cerrar();resolve({getTracks:()=>[{stop:()=>stopped++}]});await start;assert.equal(stopped,1);
});
