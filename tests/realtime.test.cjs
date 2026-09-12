const test = require('node:test');
const assert = require('node:assert/strict');
const O2CRealtime = require('../frontend/realtime.js');

function mockDataChannel() {
  const sent = [];
  const listeners = {};
  return {
    readyState: 'open',
    send(s) { sent.push(JSON.parse(s)); },
    addEventListener(evt, fn) { listeners[evt] = fn; },
    close() { this.readyState = 'closed'; if (listeners.close) listeners.close(); },
    _trigger(evt, data) { if (listeners[evt]) listeners[evt]({ data: JSON.stringify(data) }); },
    sent,
    listeners
  };
}

function mockStream() {
  let trackEnabled = false;
  return {
    getAudioTracks() {
      return [{
        get enabled() { return trackEnabled; },
        set enabled(v) { trackEnabled = v; }
      }];
    },
    getTracks() { return this.getAudioTracks(); }
  };
}

test('O2CRealtime constructor initializes defaults', () => {
  const r = new O2CRealtime();
  assert.equal(r.tokenUrl, '/api/kiosk/token');
  assert.equal(r.estaConectado(), false);
});

test('push-to-talk empezarAHablar and terminarDeHablar toggle tracks and send data channel events', () => {
  const events = [];
  const r = new O2CRealtime({ onEvent: (t, d) => events.push([t, d]) });
  const dc = mockDataChannel();
  const stream = mockStream();
  r.dc = dc;
  r.stream = stream;

  assert.equal(r.estaConectado(), true);

  r.empezarAHablar();
  assert.equal(stream.getAudioTracks()[0].enabled, true);
  assert.deepEqual(dc.sent, [{ type: 'input_audio_buffer.clear' }]);
  assert.equal(events[events.length - 1][1], 'escuchando');

  r.terminarDeHablar();
  assert.equal(stream.getAudioTracks()[0].enabled, false);
  assert.deepEqual(dc.sent[1], { type: 'input_audio_buffer.commit' });
  assert.deepEqual(dc.sent[2], { type: 'response.create' });
  assert.equal(events[events.length - 1][1], 'pensando');
});

test('data channel transcription event emits transcripcion_persona', () => {
  const events = [];
  const r = new O2CRealtime({ onEvent: (t, d) => events.push([t, d]) });
  const dc = mockDataChannel();
  r._wireDataChannel(dc);

  dc._trigger('message', {
    type: 'conversation.item.input_audio_transcription.completed',
    transcript: 'Hola, soy Alex'
  });

  assert.deepEqual(events, [['transcripcion_persona', 'Hola, soy Alex']]);
});

test('data channel tool execution invokes tool function and sends output', async () => {
  const events = [];
  let toolCalledWith = null;
  const tools = {
    buscar_persona: async (args) => {
      toolCalledWith = args;
      return { resultados: [{ id: 'u1', name: 'Alex' }] };
    }
  };
  const r = new O2CRealtime({ tools, onEvent: (t, d) => events.push([t, d]) });
  const dc = mockDataChannel();
  r.dc = dc;
  r._wireDataChannel(dc);

  dc._trigger('message', {
    type: 'response.function_call_arguments.done',
    name: 'buscar_persona',
    call_id: 'call_123',
    arguments: JSON.stringify({ nombre: 'Alex' })
  });

  await new Promise(r => setTimeout(r, 20));

  assert.deepEqual(toolCalledWith, { nombre: 'Alex' });
  assert.equal(dc.sent[0].type, 'conversation.item.create');
  assert.equal(dc.sent[0].item.call_id, 'call_123');
  assert.equal(JSON.parse(dc.sent[0].item.output).resultados[0].name, 'Alex');
  assert.equal(dc.sent[1].type, 'response.create');
});

test('cerrar cleans up stream and resets state to inactivo', () => {
  const events = [];
  let stopped = 0;
  const r = new O2CRealtime({ onEvent: (t, d) => events.push([t, d]) });
  r.dc = mockDataChannel();
  r.stream = { getTracks: () => [{ stop: () => stopped++ }] };

  r.cerrar();

  assert.equal(stopped, 1);
  assert.equal(r.pc, null);
  assert.equal(r.dc, null);
  assert.equal(events[events.length - 1][1], 'inactivo');
});
