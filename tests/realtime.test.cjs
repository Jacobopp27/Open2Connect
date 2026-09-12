const test=require('node:test');
const assert=require('node:assert/strict');
const Voice=require('../frontend/realtime.js');
const tick=()=>new Promise(r=>setImmediate(r));
function harness(onTurn) {const errors=[],sent=[];const v=new Voice({onTurn,onError:e=>errors.push(e)});v.channel={readyState:'open',send:s=>sent.push(JSON.parse(s)),close(){}};return {v,errors,sent};}
test('committed order wins over transcription completion order and duplicate delivery',async()=>{
  const seen=[];const {v}=harness(async(t,id)=>{seen.push([t,id]);return {question:'Next?'};});
  v.event({type:'input_audio_buffer.committed',item_id:'one'});
  v.event({type:'input_audio_buffer.committed',item_id:'two'});
  v.event({type:'conversation.item.input_audio_transcription.completed',item_id:'two',transcript:'Correction'});
  await tick();assert.deepEqual(seen,[]);
  v.event({type:'conversation.item.input_audio_transcription.completed',item_id:'one',transcript:'Original'});
  await tick();assert.deepEqual(seen,[['Original','one'],['Correction','two']]);
  v.event({type:'conversation.item.input_audio_transcription.completed',item_id:'one',transcript:'Original'});
  await tick();assert.equal(seen.length,2);
});
test('failed extraction retains its item and retries before later corrections',async()=>{
  let fail=true;const seen=[];const {v,errors}=harness(async(t)=>{if(fail)throw Error('retry');seen.push(t);return {question:'Next?'};});
  for(const id of ['one','two'])v.event({type:'input_audio_buffer.committed',item_id:id});
  for(const id of ['one','two'])v.event({type:'conversation.item.input_audio_transcription.completed',item_id:id,transcript:id});
  await tick();assert.equal(errors.length,1);assert.equal(v.queue.length,2);assert.equal(v.failed,true);
  fail=false;await v.retry();assert.deepEqual(seen,['one','two']);assert.equal(v.unsettled,false);
});
test('disposing during microphone permission stops a late stream',async()=>{
  let resolve;let stopped=0;
  const v=new Voice({Peer:class{},media:{getUserMedia:()=>new Promise(r=>resolve=r)}});
  const starting=v.start('Name?');v.dispose();resolve({getTracks:()=>[{stop:()=>stopped++}]});await starting;
  assert.equal(stopped,1);assert.equal(v.active,false);
});
test('stop closes microphone, playback and connection',()=>{
  const {v}=harness(async()=>{});let stopped=0,closed=0,paused=0;
  v.stream={getTracks:()=>[{stop:()=>stopped++}]};v.peer={close:()=>closed++};v.audio={pause:()=>paused++,srcObject:{}};
  v.stop();assert.equal(stopped,1);assert.equal(closed,1);assert.equal(paused,1);assert.equal(v.active,false);
});
test('pause waits for queued extraction and never asks another question',async()=>{
  let resolve;const {v,sent}=harness(()=>new Promise(r=>resolve=r));
  v.peer={close(){}};
  v.event({type:'input_audio_buffer.committed',item_id:'one'});
  v.event({type:'conversation.item.input_audio_transcription.completed',item_id:'one',transcript:'Alex'});
  const finish=v.finish();resolve({question:'Next?'});await finish;
  assert.equal(v.active,false);assert.equal(sent.some(e=>e.type==='response.create'),false);
});
