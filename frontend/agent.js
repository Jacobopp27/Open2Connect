'use strict';
/* Página de referencia para el equipo de frontend: una carita robótica (SVG inline) que
   habla cuando el agente habla, usando el mismo módulo que el kiosco (frontend/realtime.js,
   clase global O2CRealtime) y las mismas tools de check-in que /kiosk. Sin dependencias.

   A diferencia de la versión anterior de esta página, aquí sí se dibuja el QR real
   (mismo generador que /kiosk, ver frontend/qr.js) y se pintan las tarjetas de match,
   para poder probar el flujo completo desde /agent. */
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const state = { personId: null, holding: false, agentBuffer: '' };

const eventQuery = '?event=' + encodeURIComponent(new URLSearchParams(location.search).get('event') || 'medellin-2026');
function apiHeaders() { return {'X-Open2Connect':'1','Content-Type':'application/json'}; }
async function api(path, body) {
  if (path === 'confirmar') {
    const changes = Object.entries(body.cambios || {}).map(([k,v]) => k + ': ' + v).join('\n');
    if (!confirm('¿Guardar estos cambios en tu perfil?\n' + changes)) return {cancelado:true};
    body.confirmed = true;
  }
  if (path === 'checkin') {
    if (!confirm('¿Registrar tu llegada con esta seña?\n' + (body.sena || 'Sin seña'))) return {cancelado:true};
    body.confirmed = true;
  }
  const r = await fetch('/api/agent/'  + path + eventQuery, { method: 'POST', headers: apiHeaders(), body: JSON.stringify(body || {}) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || 'No se pudo completar la solicitud.');
  return data;
}

function appendLinea(rol, texto) {
  if (!texto) return;
  const p = document.createElement('p');
  p.className = 'linea ' + rol;
  p.innerHTML = `<strong>${rol === 'persona' ? 'Tú' : 'Agente'}:</strong> ${esc(texto)}`;
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
  last.innerHTML = `<strong>Agente:</strong> ${esc(state.agentBuffer)}`;
  $('#transcript').scrollTop = $('#transcript').scrollHeight;
}
function agentDone() {
  const pending = $('#transcript .linea.agente.pending');
  if (pending) pending.classList.remove('pending');
  state.agentBuffer = '';
}
function logHerramienta(nombre, resultado) {
  const log = $('#tool-log');
  const p = document.createElement('p');
  p.textContent = `→ ${nombre}: ${JSON.stringify(resultado).slice(0, 140)}`;
  log.appendChild(p);
  log.scrollTop = log.scrollHeight;
}

/* Panel de QR de registro: se muestra cuando el agente llama a mostrar_qr_registro.
   La URL ya viene absoluta desde el backend (backend/modules/kiosk.py), se usa tal cual. */
function pintarQRRegistro(url) {
  const panel = $('#qr-panel');
  panel.hidden = false;
  renderQR($('#qr-target'), url, 260);
}

/* Tarjetas de match al final del flujo (después de recomendar): nombre, razón,
   minutos desde que llegó y la seña para reconocerla. Mismo shape que usa /kiosk
   (backend/modules/kiosk.py → recomendar). */
/* QR final con la página personal (matches por celular): se pinta dentro de #matches-panel,
   creando su propio contenedor la primera vez (agent.html solo trae el panel vacío). */
function pintarQRPersonal(url) {
  if (!url) return;
  const panel = $('#matches-panel');
  let qrWrap = $('#matches-qr');
  if (!qrWrap) {
    qrWrap = document.createElement('div');
    qrWrap.id = 'matches-qr';
    const texto = document.createElement('p');
    texto.textContent = 'Tus matches en tu celular';
    const target = document.createElement('div');
    target.id = 'matches-qr-target';
    qrWrap.appendChild(texto);
    qrWrap.appendChild(target);
    panel.appendChild(qrWrap);
  }
  $('#matches-qr-target').innerHTML = '';
  renderQR($('#matches-qr-target'), url, 200);
}

function pintarRecomendaciones(r) {
  const panel = $('#matches-panel');
  const cards = $('#matches-cards');
  const lista = r.recomendaciones || [];
  if (!lista.length) {
    panel.hidden = false;
    cards.innerHTML = `<p class="hint">${esc(r.sugerencia || 'Todavía no hay una recomendación clara.')}</p>`;
    pintarQRPersonal(r.pagina_personal);
    return;
  }
  panel.hidden = false;
  cards.innerHTML = lista.map((p) => `
    <article class="match-card">
      <h3>${esc(p.name)}</h3>
      ${p.role ? `<p class="rol">${esc(p.role)}${p.sector ? ' · ' + esc(p.sector) : ''}</p>` : ''}
      <p class="razon">${esc(p.razon || '')}</p>
      <p class="meta">Llegó hace ${esc(p.minutos_desde_llegada)} min · Anda de ${esc(p.sena)}</p>
    </article>
  `).join('');
  pintarQRPersonal(r.pagina_personal);
}

/* Aviso breve al tomar la foto de la seña (2 s): confirma que no se guarda.
   Estilos puestos por CSSOM (propiedad a propiedad), no por atributo style=,
   para respetar la CSP del proyecto (style-src 'self'). */
function mostrarAvisoFoto() {
  const aviso = document.createElement('div');
  aviso.textContent = '📷 Foto tomada solo para la seña; no se guarda';
  aviso.style.position = 'fixed';
  aviso.style.top = '16px';
  aviso.style.left = '50%';
  aviso.style.transform = 'translateX(-50%)';
  aviso.style.background = '#0a1f1b';
  aviso.style.color = '#fff';
  aviso.style.padding = '10px 16px';
  aviso.style.borderRadius = '8px';
  aviso.style.zIndex = '9999';
  aviso.style.fontSize = '14px';
  aviso.style.boxShadow = '0 4px 14px rgba(0,0,0,.35)';
  document.body.appendChild(aviso);
  setTimeout(() => aviso.remove(), 2000);
}

/* Captura una foto de la cámara del kiosco (con permiso verbal ya dado por la persona al
   agente), la reduce a máx. 640px de ancho, la manda como data URL a /api/kiosk/apariencia
   para describirla, y apaga la cámara de inmediato. La imagen nunca se guarda en disco ni
   se logea; solo vive en memoria del navegador durante esta llamada. */
async function tomarFotoSena() {
  if (!confirm("¿Permites tomar una foto y enviarla a OpenAI para describir tu ropa? La aplicación no guardará la imagen.")) return {sena:"",cancelado:true};
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 640 } });
  } catch (err) {
    return { sena: '', error: 'sin cámara' };
  }
  try {
    const video = $('#cam');
    video.srcObject = stream;
    video.hidden = false;
    await video.play().catch(() => {});
    await new Promise((resolve) => setTimeout(resolve, 600));
    const w = Math.min(640, video.videoWidth || 640);
    const h = video.videoWidth ? Math.round((w * video.videoHeight) / video.videoWidth) : 480;
    const canvas = $('#cam-canvas');
    canvas.width = w;
    canvas.height = h;
    canvas.getContext('2d').drawImage(video, 0, 0, w, h);
    const imagen = canvas.toDataURL('image/jpeg', 0.7);
    mostrarAvisoFoto();
    return await api('apariencia', { imagen, photo_consent:true });
  } catch (err) {
    return { sena: '', error: 'sin cámara' };
  } finally {
    stream.getTracks().forEach((t) => t.stop());
    const video = $('#cam');
    video.srcObject = null;
    video.hidden = true;
  }
}

/* Las mismas tools del kiosco (buscar_persona, confirmar_perfil, hacer_checkin, recomendar,
   mostrar_qr_registro), llamando a las mismas rutas /api/kiosk/*. */
const tools = {
  async buscar_persona(args) {
    const r = await api('buscar', { nombre: args.nombre, email: args.email });
    if (r.resultados && r.resultados.length === 1) state.personId = r.resultados[0].id;
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
  async describir_apariencia() {
    return tomarFotoSena();
  },
};

/* ---------------------------------------------------------------------------
 * Carita: cabeza blanca con pantalla oscura, ojos y boca cian.
 * - Parpadeo periódico cada 3-5 s (independiente del estado).
 * - 'escuchando': ojos entrecerrados y hacia arriba (ver agent.css).
 * - 'pensando': ojos se mueven juntos hacia un lado y vuelven (ver agent.css).
 * - 'inactivo': respiración lenta de toda la cabeza (ver agent.css).
 * - Boca: un arco de sonrisa en reposo que hace crossfade hacia una forma
 *   cian cuya altura sigue la 'amplitud' del audio, suavizada por interpolación
 *   cuadro a cuadro (para que no salte de golpe entre lecturas de amplitud).
 * ------------------------------------------------------------------------- */
const face = $('#face');
const mouthSmile = $('#mouth-smile');
const mouthShape = $('#mouth-shape');
const MOUTH_H_MIN = 4, MOUTH_H_MAX = 28;
const MOUTH_SUAVIZADO = 0.25; // qué tan rápido currentAmp alcanza a targetAmp por cuadro

let targetAmp = 0;
let currentAmp = 0;

function cuadroBoca() {
  currentAmp += (targetAmp - currentAmp) * MOUTH_SUAVIZADO;
  const amp = Math.max(0, Math.min(1, currentAmp));
  // Crossfade sonrisa -> forma de habla entre amp 0.03 y 0.15, para que la
  // sonrisa se mantenga en silencio y no "parpadee" con ruido de fondo.
  const t = Math.max(0, Math.min(1, (amp - 0.03) / 0.12));
  mouthSmile.style.opacity = String(1 - t);
  mouthShape.style.opacity = String(t);
  const h = MOUTH_H_MIN + amp * (MOUTH_H_MAX - MOUTH_H_MIN);
  mouthShape.setAttribute('height', h.toFixed(1));
  mouthShape.setAttribute('y', (-h / 2).toFixed(1));
  mouthShape.setAttribute('rx', Math.min(MOUTH_H_MAX / 2, h / 2).toFixed(1));
  requestAnimationFrame(cuadroBoca);
}
requestAnimationFrame(cuadroBoca);

function actualizarAmplitud(amplitud) {
  targetAmp = Math.max(0, Math.min(1, amplitud));
}

function programarParpadeo() {
  const espera = 3000 + Math.random() * 2000; // cada 3-5 s
  setTimeout(() => {
    face.classList.add('blink');
    setTimeout(() => face.classList.remove('blink'), 120);
    programarParpadeo();
  }, espera);
}
programarParpadeo();

const ESTADOS_TEXTO = {
  conectando: 'Conectando…',
  conectado: 'Conectado. Mantén presionado el botón para hablar.',
  escuchando: 'Escuchando…',
  pensando: 'Pensando…',
  hablando: 'Hablando…',
  inactivo: 'Mantén presionado el botón para hablar.',
  error: 'Ocurrió un error en la sesión de voz.',
};
const ESTADOS_CLASE = ['escuchando', 'pensando', 'inactivo'];

function setEstado(estado, textoOverride) {
  $('#status-text').textContent = textoOverride || ESTADOS_TEXTO[estado] || estado;
  ESTADOS_CLASE.forEach((c) => face.classList.toggle(c, c === estado));
}

function onEvent(tipo, datos) {
  switch (tipo) {
    case 'estado':
      setEstado(datos);
      if (datos === 'error' || (datos === 'inactivo' && !rt.pc)) $('#start-btn').disabled = false;
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
    case 'herramienta':
      logHerramienta(datos.nombre, datos.resultado);
      break;
    case 'amplitud':
      actualizarAmplitud(datos);
      break;
    case 'uso':
      console.log('[realtime usage]', JSON.stringify(datos));
      break;
    case 'error':
      setEstado('error', datos);
      break;
  }
}

const rt = new O2CRealtime({ tokenUrl: '/api/agent/token' + eventQuery, tokenBody:{ai_consent:true}, headers: apiHeaders(), tools, onEvent });

function reset() {
  rt.cerrar();
  $('#start-btn').disabled = false;
  state.personId = null;
  state.holding = false;
  state.agentBuffer = '';
  $('#ptt').classList.remove('active');
  $('#transcript').innerHTML = '';
  $('#tool-log').innerHTML = '';
  $('#qr-panel').hidden = true;
  $('#qr-target').innerHTML = '';
  $('#matches-panel').hidden = true;
  $('#matches-cards').innerHTML = '';
  setEstado('inactivo', 'Mantén presionado el botón para hablar.');
  setEstado('inactivo', 'Pulsa Iniciar entrevista para comenzar.');
}

function onPTTDown(e) {
  e.preventDefault();
  if (state.holding || !rt.estaConectado()) return;
  state.holding = true;
  if (e.pointerId !== undefined) e.currentTarget.setPointerCapture(e.pointerId);
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
  $('#reset-btn').addEventListener('click', reset);
  $('#start-btn').addEventListener('click', async () => {
    const start = $('#start-btn'); start.disabled = true;
    try {
      const me = await fetch('/api/me');
      if (!me.ok) throw new Error('Inicia sesión desde el enlace de abajo para continuar.');
      await rt.conectar();
    } catch (err) { setEstado('error', err.message); }
    finally { start.disabled = !!rt.pc; }
  });
  window.addEventListener('pagehide', () => rt.cerrar());
  setEstado('inactivo', 'Pulsa Iniciar entrevista para comenzar.');
});
