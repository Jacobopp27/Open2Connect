'use strict';
/* Kiosco de check-in por voz "Mesa 4". La sesión WebRTC con OpenAI Realtime vive en
   frontend/realtime.js (clase global O2CRealtime, cargada antes que este archivo).
   Este archivo solo conoce la UI del kiosco y las tools propias del check-in;
   el servidor (backend/modules/kiosk.py) crea el token efímero y ejecuta las tools,
   y el audio nunca pasa por este backend. */
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* El generador de QR (`window.renderQR(container, text, size)`) vive en
   frontend/qr.js, cargado antes que este archivo (ver kiosk.html). */

/* ---------------------------------------------------------------------------
 * UI del kiosco: transcripción, tarjetas, QR y despacho de las tools propias
 * del check-in. La sesión de voz en sí (WebRTC, data channel, tools genéricas)
 * la maneja O2CRealtime, definida en frontend/realtime.js.
 * ------------------------------------------------------------------------- */
const state = { personId: null, holding: false, agentBuffer: '', usage: [] };

function kioskKey() {
  const meta = document.querySelector('meta[name="kiosk-key"]');
  return meta && meta.content ? meta.content : '';
}
function apiHeaders() {
  const headers = { 'X-Open2Connect': '1', 'Content-Type': 'application/json' };
  const key = kioskKey();
  if (key) headers['X-Kiosk-Key'] = key;
  return headers;
}
async function api(path, body) {
  const r = await fetch('/api/kiosk/' + path, { method: 'POST', headers: apiHeaders(), body: JSON.stringify(body || {}) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || 'No se pudo completar la solicitud.');
  return data;
}
function setEstado(texto) { $('#status').textContent = texto; }
function appendLinea(rol, texto) {
  if (!texto) return;
  const p = document.createElement('p');
  p.className = 'linea ' + rol;
  p.innerHTML = `<strong>${rol === 'persona' ? 'Tú' : 'Mesa 4'}:</strong> ${esc(texto)}`;
  $('#transcript').appendChild(p);
  $('#transcript').scrollTop = $('#transcript').scrollHeight;
}
function agentDelta(delta) {
  state.agentBuffer += delta || '';
  let last = $('#transcript .linea.agente.pending');
  if (!last) {
    last = document.createElement('p');
    last.className = 'linea agente pending';
    $('#transcript').appendChild(last);
  }
  last.innerHTML = `<strong>Mesa 4:</strong> ${esc(state.agentBuffer)}`;
  $('#transcript').scrollTop = $('#transcript').scrollHeight;
}
function agentDone() {
  const pending = $('#transcript .linea.agente.pending');
  if (pending) pending.classList.remove('pending');
  state.agentBuffer = '';
}

function pintarCandidatos(lista) {
  const cards = $('#cards');
  if (!lista.length) { cards.innerHTML = '<p class="hint">No encontré a nadie con ese nombre registrado.</p>'; return; }
  if (lista.length === 1) {
    const p = lista[0];
    cards.innerHTML = `<article class="kiosk-card"><h3>${esc(p.name)}</h3><p class="muted">${esc(p.role || 'Sin rol')}${p.sector ? ' · ' + esc(p.sector) : ''}</p>${p.busca ? `<p><strong>Busca:</strong> ${esc(p.busca)}</p>` : ''}${p.ofrece ? `<p><strong>Ofrece:</strong> ${esc(p.ofrece)}</p>` : ''}</article>`;
    return;
  }
  cards.innerHTML = `<p class="hint">Hay ${lista.length} personas con ese nombre, confirmando cuál es:</p><div class="kiosk-list">${lista.map((p) => `<article class="kiosk-card small"><h3>${esc(p.name)}</h3><p class="muted">${esc(p.role || '')}${p.sector ? ' · ' + esc(p.sector) : ''}</p></article>`).join('')}</div>`;
}

function pintarRecomendaciones(r) {
  const cards = $('#cards');
  if (!r.recomendaciones || !r.recomendaciones.length) {
    cards.innerHTML = `<p class="hint">${esc(r.sugerencia || 'Todavía no hay una recomendación clara.')}</p>`;
    return;
  }
  cards.innerHTML = `<div class="kiosk-list">${r.recomendaciones.map((p) => `<article class="kiosk-card"><h3>${esc(p.name)}</h3><p class="muted">${esc(p.role || '')}</p><p>${esc(p.razon)}</p><p class="hint">Llegó hace ${esc(p.minutos_desde_llegada)} min · Anda de ${esc(p.sena)}</p></article>`).join('')}</div>`;
  const qrZone = $('#qr');
  qrZone.hidden = false;
  qrZone.innerHTML = '<p class="hint">Tu página personal:</p><div id="qr-target"></div>';
  renderQR($('#qr-target'), window.location.origin + '/');
}

function pintarQRRegistro(url) {
  const qrZone = $('#qr');
  qrZone.hidden = false;
  qrZone.innerHTML = '<p class="hint">Regístrate con este QR o enlace:</p><div id="qr-target"></div>';
  renderQR($('#qr-target'), url);
  $('#cards').innerHTML = '';
}

/* Tools del kiosco que O2CRealtime invoca cuando el agente llama a una function call.
   Cada una recibe los argumentos ya parseados y devuelve el resultado que se le manda de vuelta al modelo. */
const tools = {
  async buscar_persona(args) {
    const r = await api('buscar', { nombre: args.nombre, email: args.email });
    if (r.resultados && r.resultados.length === 1) state.personId = r.resultados[0].id;
    pintarCandidatos(r.resultados || []);
    return r;
  },
  async confirmar_perfil(args) {
    state.personId = args.id || state.personId;
    return api('confirmar', { id: state.personId, cambios: args.cambios || {} });
  },
  async hacer_checkin(args) {
    state.personId = args.id || state.personId;
    return api('checkin', { id: state.personId, sena: args.sena });
  },
  async recomendar(args) {
    state.personId = args.id || state.personId;
    const r = await api('recomendar', { id: state.personId });
    pintarRecomendaciones(r);
    return r;
  },
  async mostrar_qr_registro() {
    const r = await api('qr');
    pintarQRRegistro(r.url);
    return r;
  },
};

const ESTADOS_TEXTO = {
  conectando: 'Conectando…',
  conectado: 'Conectado. Mantén presionado el botón para hablar.',
  escuchando: 'Escuchando…',
  pensando: 'Pensando…',
  hablando: 'Mesa 4 está hablando…',
  inactivo: 'Mantén presionado el botón para hablar.',
};

function onEvent(tipo, datos) {
  switch (tipo) {
    case 'estado':
      if (ESTADOS_TEXTO[datos]) setEstado(ESTADOS_TEXTO[datos]);
      if (datos === 'conectado') rt.decir('Saluda muy brevemente, en una sola frase, y pregunta el nombre de la persona.');
      break;
    case 'transcripcion_persona':
      appendLinea('persona', datos);
      break;
    case 'transcripcion_agente_delta':
      agentDelta(datos);
      break;
    case 'transcripcion_agente_fin':
      agentDone();
      break;
    case 'uso':
      state.usage.push(datos);
      console.log('[realtime usage]', JSON.stringify(datos));
      break;
    case 'error':
      setEstado(datos || 'Ocurrió un error en la sesión de voz.');
      break;
    // 'herramienta' y 'amplitud' no se usan en el kiosco (sin carita robótica aquí; ver frontend/agent.js).
  }
}

const rt = new O2CRealtime({ tokenUrl: '/api/kiosk/token', headers: apiHeaders(), tools, onEvent });

function reset() {
  rt.cerrar();
  state.personId = null;
  state.holding = false;
  state.agentBuffer = '';
  $('#transcript').innerHTML = '';
  $('#cards').innerHTML = '';
  $('#qr').hidden = true;
  $('#qr').innerHTML = '';
  setEstado('Párate aquí y mantén presionado el botón para hablar.');
  rt.conectar().catch((err) => setEstado('No se pudo iniciar: ' + err.message));
}

function onPTTDown(e) {
  e.preventDefault();
  if (state.holding || !rt.estaConectado()) return;
  state.holding = true;
  $('#ptt').classList.add('active');
  rt.empezarAHablar();
}
function onPTTUp(e) {
  e.preventDefault();
  if (!state.holding) return;
  state.holding = false;
  $('#ptt').classList.remove('active');
  rt.terminarDeHablar();
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = $('#ptt');
  btn.addEventListener('pointerdown', onPTTDown);
  btn.addEventListener('pointerup', onPTTUp);
  btn.addEventListener('pointercancel', onPTTUp);
  btn.addEventListener('touchstart', onPTTDown, { passive: false });
  btn.addEventListener('touchend', onPTTUp, { passive: false });
  $('#reset-btn').addEventListener('click', reset);
  rt.conectar().catch((err) => setEstado('No se pudo iniciar: ' + err.message));
});
