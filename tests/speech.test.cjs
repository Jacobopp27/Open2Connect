const assert = require('node:assert/strict');
const test = require('node:test');
const Speech = require('../frontend/speech.js');
class Recognition {
  start(){this.onstart();}
  stop(){this.onend();}
  abort(){this.onend();}
}
function adapter(){
  const states=[], texts=[], ended=[];
  const speech=new Speech({Recognition,onState:s=>states.push(s),onText:s=>texts.push(s),onEnd:s=>ended.push(s),synthesis:{cancel(){} }});
  return {speech,states,texts,ended};
}
test('speech start/end emits final answer once',()=>{
  const a=adapter();a.speech.listen('es');const r=a.speech.recognition;
  assert.equal(r.lang,'es-CO');r.onspeechstart();
  const result=[{transcript:'Soy Alex'}];result.isFinal=true;
  r.onresult({results:[result]});r.onspeechend();r.onend();
  assert.deepEqual(a.ended,['Soy Alex']);assert.ok(a.states.includes('speech-ended'));
});
test('pausing preserves transcript but does not auto-submit',()=>{
  const a=adapter();a.speech.listen('en');const r=a.speech.recognition;
  const result=[{transcript:'I need design'}];result.isFinal=true;r.onresult({results:[result]});
  a.speech.pause();assert.equal(a.texts[0],'I need design');assert.equal(a.ended.length,0);
});
test('permission errors and unsupported browsers allow fallback',()=>{
  const a=adapter();a.speech.listen('es');const r=a.speech.recognition;
  r.onerror({error:'not-allowed'});r.onend();assert.equal(a.ended.length,0);assert.ok(a.states.includes('error:not-allowed'));
  const states=[];const unsupported=new Speech({onState:s=>states.push(s)});
  assert.equal(unsupported.listen('en'),false);assert.deepEqual(states,['unsupported']);
});
test('starting dictation cancels spoken question and prevents double start',()=>{
  let canceled=0;const s=new Speech({Recognition,synthesis:{cancel(){canceled++}}});
  assert.equal(s.listen('en'),true);assert.equal(s.listen('en'),false);assert.equal(canceled,1);
});
