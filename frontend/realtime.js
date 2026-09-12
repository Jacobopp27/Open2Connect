'use strict';
/* Módulo reutilizable de sesión OpenAI Realtime vía WebRTC directo navegador → OpenAI.
   Sin módulos ES (la CSP del repo solo permite script-src 'self' y no hay CDN):
   se expone la clase global `O2CRealtime`. Cárgalo con <script src="/realtime.js">
   ANTES del script que lo use (ver frontend/kiosk.js y frontend/agent.js).

   El servidor solo crea el token efímero (POST a tokenUrl) y ejecuta las tools;
   el audio nunca pasa por el backend propio, solo por OpenAI. */
(function (global) {
  const AMPLITUD_HZ = 20; // ~20 veces por segundo, según lo pedido.
  const AMPLITUD_INTERVALO_MS = Math.round(1000 / AMPLITUD_HZ);
  const UMBRAL_HABLANDO = 0.04; // nivel de amplitud a partir del cual se considera "audio remoto detectado"

  class O2CRealtime {
    /**
     * @param {Object} opts
     * @param {string} [opts.tokenUrl] - Ruta del backend que devuelve el token efímero Realtime.
     * @param {Object} [opts.headers] - Headers a enviar al pedir el token (p. ej. X-Open2Connect, X-Kiosk-Key).
     * @param {Object<string,Function>} [opts.tools] - Mapa nombre → async (args) => resultado.
     * @param {Function} [opts.onEvent] - (tipo, datos) => void. Ver tipos en el README del módulo.
     */
    constructor(opts) {
      opts = opts || {};
      this.tokenUrl = opts.tokenUrl || '/api/kiosk/token';
      this.headers = opts.headers || {};
      this.tools = opts.tools || {};
      this.onEvent = typeof opts.onEvent === 'function' ? opts.onEvent : () => {};
      this.pc = null;
      this.dc = null;
      this.stream = null;
      this.audioEl = null;
      this.audioCtx = null;
      this.analyser = null;
      this._amplitudTimer = null;
      this._agentHablando = false; // entre el primer indicio de audio de salida y response.done
      this._resumeCtx = this._resumeCtx.bind(this);
    }

    _emit(tipo, datos) {
      try { this.onEvent(tipo, datos); } catch (e) { /* un error del consumidor no debe romper la sesión */ }
    }
    _estado(valor) { this._emit('estado', valor); }

    _resumeCtx() {
      // Autoplay policy: si el AudioContext quedó "suspended" hasta la primera interacción, se reanuda aquí.
      if (this.audioCtx && this.audioCtx.state === 'suspended') this.audioCtx.resume().catch(() => {});
      if (this.audioEl && this.audioEl.paused) this.audioEl.play().catch(() => {});
    }

    _send(obj) {
      if (this.dc && this.dc.readyState === 'open') this.dc.send(JSON.stringify(obj));
    }

    /** Token → RTCPeerConnection (mic apagado) → data channel → SDP a OpenAI. */
    async conectar() {
      this._estado('conectando');
      try {
        const resp = await fetch(this.tokenUrl, { method: 'POST', headers: this.headers, body: JSON.stringify({}) });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.error || 'No se pudo obtener el token de sesión.');
        const clientSecret = data.value;
        if (!clientSecret) throw new Error('Respuesta de token inválida.');

        const pc = new RTCPeerConnection();
        this.pc = pc;
        pc.ontrack = (e) => this._wireRemoteAudio(e.streams[0]);

        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this.stream = stream;
        // El audio se cobra al entrar a la sesión: el micrófono va apagado y solo se enciende
        // mientras se mantiene presionado el botón (push-to-talk), por costo y por ruido de fondo.
        stream.getAudioTracks().forEach((t) => { t.enabled = false; });
        stream.getTracks().forEach((t) => pc.addTrack(t, stream));

        const dc = pc.createDataChannel('oai-events'); // verificar: nombre exacto del canal de eventos
        this.dc = dc;
        this._wireDataChannel(dc);

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        // verificar: endpoint y forma exactos del intercambio de SDP en la versión vigente de la API
        const sdpResp = await fetch('https://api.openai.com/v1/realtime/calls', {
          method: 'POST',
          headers: { Authorization: `Bearer ${clientSecret}`, 'Content-Type': 'application/sdp' },
          body: offer.sdp,
        });
        if (!sdpResp.ok) throw new Error('No se pudo conectar con OpenAI Realtime (' + sdpResp.status + ').');
        const answerSdp = await sdpResp.text();
        await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });

        document.addEventListener('pointerdown', this._resumeCtx, { once: true });
        document.addEventListener('keydown', this._resumeCtx, { once: true });
      } catch (err) {
        this._estado('error');
        throw err;
      }
    }

    _wireRemoteAudio(stream) {
      if (!this.audioEl) {
        this.audioEl = document.createElement('audio');
        this.audioEl.autoplay = true;
      }
      this.audioEl.srcObject = stream;
      this.audioEl.play().catch(() => { /* algunos navegadores requieren interacción previa; se reintenta al reanudar el AudioContext */ });
      if (this.audioCtx) return; // ya conectado (p. ej. reconexión de la misma pista)
      try {
        const Ctx = global.AudioContext || global.webkitAudioContext;
        this.audioCtx = new Ctx();
        const source = this.audioCtx.createMediaStreamSource(stream);
        const analyser = this.audioCtx.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);
        this.analyser = analyser;
        this._iniciarBucleAmplitud();
      } catch (e) {
        // Sin AudioContext (navegador antiguo o política de permisos): no hay animación de amplitud,
        // pero la sesión de voz sigue funcionando con normalidad.
      }
    }

    _iniciarBucleAmplitud() {
      if (this._amplitudTimer) return;
      const buffer = new Uint8Array(this.analyser.fftSize);
      this._amplitudTimer = setInterval(() => {
        this.analyser.getByteTimeDomainData(buffer);
        let sumaCuadrados = 0;
        for (let i = 0; i < buffer.length; i++) {
          const v = (buffer[i] - 128) / 128;
          sumaCuadrados += v * v;
        }
        const rms = Math.sqrt(sumaCuadrados / buffer.length);
        const amplitud = Math.min(1, rms * 4); // ganancia empírica para que la boca se note al hablar
        this._emit('amplitud', amplitud);
        if (!this._agentHablando && amplitud > UMBRAL_HABLANDO) this._marcarHablando();
      }, AMPLITUD_INTERVALO_MS);
    }

    _marcarHablando() {
      if (this._agentHablando) return;
      this._agentHablando = true;
      this._estado('hablando');
    }

    _wireDataChannel(dc) {
      dc.addEventListener('open', () => this._estado('conectado'));
      dc.addEventListener('message', (e) => {
        let evt;
        try { evt = JSON.parse(e.data); } catch (err) { return; }
        // verificar: nombres exactos de los eventos del canal de datos (pueden variar entre versiones de la Realtime API)
        switch (evt.type) {
          case 'conversation.item.input_audio_transcription.completed':
            this._emit('transcripcion_persona', evt.transcript);
            break;
          case 'response.output_audio_transcript.delta':
            this._marcarHablando(); // 'hablando' se activa al primer delta de transcripción de audio
            this._emit('transcripcion_agente_delta', evt.delta);
            break;
          case 'response.output_audio_transcript.done':
            this._emit('transcripcion_agente_fin', evt.transcript);
            break;
          case 'response.function_call_arguments.done':
            this._ejecutarHerramienta(evt);
            break;
          case 'response.done': {
            this._agentHablando = false;
            this._estado('inactivo');
            // Consumo de tokens por respuesta (audio y texto), para estimar el costo por sesión.
            const usage = evt.response && evt.response.usage;
            if (usage) this._emit('uso', usage);
            break;
          }
          case 'error':
            this._estado('error');
            this._emit('error', (evt.error && evt.error.message) || 'Ocurrió un error en la sesión de voz.');
            break;
        }
      });
      dc.addEventListener('close', () => this._estado('inactivo'));
    }

    async _ejecutarHerramienta(evt) {
      let args = {};
      try { args = JSON.parse(evt.arguments || '{}'); } catch (e) { /* argumentos vacíos o inválidos */ }
      const tool = this.tools[evt.name];
      let resultado;
      if (typeof tool !== 'function') {
        resultado = { error: 'herramienta no disponible' };
      } else {
        try { resultado = await tool(args); } catch (err) { resultado = { error: err.message }; }
      }
      this._emit('herramienta', { nombre: evt.name, args, resultado });
      // verificar: nombre exacto del evento/campo de salida de function call en la versión vigente de la API
      this._send({ type: 'conversation.item.create', item: { type: 'function_call_output', call_id: evt.call_id, output: JSON.stringify(resultado) } });
      this._send({ type: 'response.create' });
    }

    /** true si el data channel está abierto y listo para push-to-talk. */
    estaConectado() {
      return !!(this.dc && this.dc.readyState === 'open');
    }

    /** Push-to-talk: enciende el micrófono y limpia el buffer de entrada. */
    empezarAHablar() {
      if (!this.stream || !this.dc || this.dc.readyState !== 'open') return;
      this.stream.getAudioTracks().forEach((t) => { t.enabled = true; });
      this._send({ type: 'input_audio_buffer.clear' });
      this._estado('escuchando');
    }

    /** Push-to-talk: apaga el micrófono, confirma el turno y pide respuesta. */
    terminarDeHablar() {
      if (!this.stream) return;
      this.stream.getAudioTracks().forEach((t) => { t.enabled = false; });
      this._send({ type: 'input_audio_buffer.commit' });
      this._send({ type: 'response.create' });
      this._estado('pensando');
    }

    /** Pide al agente que diga algo por su cuenta (p. ej. el saludo inicial). */
    decir(instrucciones) {
      this._send({ type: 'response.create', response: { instructions: instrucciones } });
      this._estado('pensando');
    }

    cerrar() {
      if (this._amplitudTimer) { clearInterval(this._amplitudTimer); this._amplitudTimer = null; }
      if (this.audioCtx) { try { this.audioCtx.close(); } catch (e) { /* ya cerrado */ } this.audioCtx = null; }
      if (this.dc) { try { this.dc.close(); } catch (e) { /* ya cerrado */ } }
      if (this.pc) { try { this.pc.close(); } catch (e) { /* ya cerrado */ } }
      if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
      document.removeEventListener('pointerdown', this._resumeCtx);
      document.removeEventListener('keydown', this._resumeCtx);
      this.pc = this.dc = this.stream = this.analyser = null;
      this._agentHablando = false;
      this._estado('inactivo');
    }
  }

  global.O2CRealtime = O2CRealtime;
})(window);
