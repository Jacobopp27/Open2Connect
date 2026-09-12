'use strict';
/* Página personal del asistente (/yo/<id>), abierta desde el QR de su celular.
   Sondea backend/modules/encuentros.py cada 10s (sin sesión: el id de 32 hex del QR
   es el único secreto) y avisa con vibración + sonido cuando un match hace check-in. */
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const POLL_MS = 10000;
const eventQuery = 'event=' + encodeURIComponent(new URLSearchParams(location.search).get('event') || 'medellin-2026');
const myId = decodeURIComponent((location.pathname.match(/\/yo\/([^/]+)/) || [, ''])[1]);

// checked_in_at previo por match id, para detectar la transición "no llegado" -> "llegado".
const previo = new Map();
let audioCtx = null;

function crearAudioCtx() {
  if (audioCtx) return audioCtx;
  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  } catch (e) {
    audioCtx = null;
  }
  return audioCtx;
}

function beep() {
  const ctx = audioCtx;
  if (!ctx) return;
  try {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.16);
  } catch (e) { /* best-effort */ }
}

function avisar() {
  if (navigator.vibrate) {
    try { navigator.vibrate([200, 100, 200]); } catch (e) { /* best-effort */ }
  }
  beep();
}

function mostrarBanner(match) {
  const banner = $('#banner');
  $('#banner-titulo').textContent = `${match.name} acaba de llegar`;
  $('#banner-detalle').textContent = match.sena ? `Reconócela por: ${match.sena}` : '';
  banner.hidden = false;
  clearTimeout(mostrarBanner._t);
  mostrarBanner._t = setTimeout(() => { banner.hidden = true; }, 12000);
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || 'No se pudo completar la solicitud.');
  return data;
}

async function confirmarConocidos(otroId, btn) {
  btn.disabled = true;
  btn.textContent = 'Guardando…';
  try {
    await api('/api/yo/confirmar?' + eventQuery, {
      method: 'POST',
      headers: { 'X-Open2Connect': '1', 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: myId, otro: otroId }),
    });
    btn.textContent = 'Ya se conocieron';
  } catch (e) {
    btn.disabled = false;
    btn.textContent = 'Ya nos conocimos';
    alert(e.message || 'No se pudo guardar.');
  }
}

function tarjeta(match) {
  const div = document.createElement('div');
  div.className = 'match-card';
  const llego = !!match.checked_in_at;
  const llegadaTexto = llego
    ? `llegó hace ${match.minutos_desde_llegada <= 0 ? 'menos de 1' : match.minutos_desde_llegada} min`
    : 'aún no ha llegado';
  div.innerHTML = `
    <h3>${esc(match.name)}</h3>
    <p class="role">${esc(match.role || '')}</p>
    <p class="razon">${esc(match.razon)}</p>
    <div class="llegada ${llego ? 'llego' : ''}"><span class="punto"></span>
      <span>${esc(llegadaTexto)}${llego && match.sena ? ' · seña: ' + esc(match.sena) : ''}</span>
    </div>
    <button class="conocer-btn" type="button" ${match.conocidos ? 'disabled' : ''}>
      ${match.conocidos ? 'Ya se conocieron' : 'Ya nos conocimos'}
    </button>`;
  div.querySelector('.conocer-btn').addEventListener('click', (ev) => confirmarConocidos(match.id, ev.currentTarget));
  return div;
}

function render(estado) {
  $('#nombre').textContent = estado.yo.name || 'ahí';
  $('#actualizado').textContent = 'Actualizado ' + new Date(estado.actualizado * 1000).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });

  const lista = $('#lista');
  lista.innerHTML = '';
  $('#vacio').hidden = estado.matches.length > 0;

  for (const match of estado.matches) {
    const antes = previo.get(match.id);
    const acabaDeLlegar = antes !== undefined && !antes && !!match.checked_in_at;
    if (acabaDeLlegar) {
      avisar();
      mostrarBanner(match);
    }
    previo.set(match.id, !!match.checked_in_at);

    const card = tarjeta(match);
    if (acabaDeLlegar) card.classList.add('recien-llegado');
    lista.appendChild(card);
  }
}

async function poll() {
  try {
    const estado = await api(`/api/yo/estado?id=${encodeURIComponent(myId)}&${eventQuery}`, { method: 'GET' });
    if (estado.error) {
      $('#nombre').textContent = '';
      $('#vacio').hidden = false;
      $('#vacio').textContent = 'No encontramos tu registro. Verifica el enlace del QR.';
      return;
    }
    render(estado);
  } catch (e) {
    $('#vacio').hidden = false;
    $('#vacio').textContent = e.message + ' Inicia sesión en Open2Connect con tu cuenta para ver esta página.';
  }
}

function initAudioBoton() {
  const btn = $('#activar-avisos');
  if (!('AudioContext' in window || 'webkitAudioContext' in window)) return;
  btn.hidden = false;
  btn.addEventListener('click', () => {
    const ctx = crearAudioCtx();
    if (ctx && ctx.state === 'suspended') ctx.resume();
    btn.hidden = true;
  }, { once: true });
}

if (!myId) {
  $('#vacio').hidden = false;
  $('#vacio').textContent = 'Enlace inválido: falta tu identificador personal.';
} else {
  initAudioBoton();
  poll();
  setInterval(poll, POLL_MS);
}
