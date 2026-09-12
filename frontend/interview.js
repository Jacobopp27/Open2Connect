/* Interview UI is separate from the profile form and voice transport adapter. */
window.InterviewUI = (() => {
  let context, session = null, answer = '', pending = false, error = '', speech;
  let voiceState = 'idle', autoSend = true, readAloud = true, mode = 'guided';
  let manual = null, mcpToken = '', realtime, rtState='paused', caption='', generation=0;
  const inputId = 'interview-answer';
  const copy = (es, en) => context.t(es,en);
  function init(c) {
    context = c;
    if(c.config.realtime?.configured) mode='realtime';
    realtime = new O2CRealtime({
      connect: sdp => action('voice',{sdp}),
      onTurn: async (text,turn_id) => {
        const activeGeneration=generation;
        const currentId=session?.id;
        if(!currentId) throw Error('Entrevista cerrada. / Interview closed.');
        if(manual) {const edited=await action('edit',{profile:manual});if(activeGeneration!==generation || session?.id!==currentId)return edited;install(edited);}
        const next=await action('turn',{text,turn_id});
        if(activeGeneration!==generation || session?.id!==currentId) return next;
        install(next);context.render();return next;
      },
      onState: value => {rtState=value;const el=document.getElementById('realtime-status');if(el)el.textContent=rtStatus();},
      onCaption: (who,text) => {caption=(who==='user'?copy('Tú: ','You: '):copy('Asistente: ','Assistant: '))+text;const el=document.getElementById('realtime-caption');if(el)el.textContent=caption;},
      onError: message => {if(!context.state.user || context.state.page!=='interview')realtime.stop();error=message;context.render();}
    });
    window.addEventListener('pagehide',()=>realtime.dispose());
    speech = new O2CSpeech({
      Recognition: window.SpeechRecognition || window.webkitSpeechRecognition,
      synthesis: window.speechSynthesis, Utterance: window.SpeechSynthesisUtterance,
      onState: state => {
        voiceState = state;
        const status = document.querySelector('#interview-voice-status');
        if (status) status.textContent = statusText();
      },
      onText: text => {
        answer = text;
        const box = document.getElementById(inputId);
        if (box) box.value = answer;
      },
      onEnd: text => {
        answer = text;
        if (autoSend && context.state.page === 'interview' && session?.status === 'active') sendAnswer();
      }
    });
  }
  function statusText() {
    const map = {
      idle: copy('Listo para escuchar.','Ready to listen.'),
      listening: copy('Escuchando…','Listening…'),
      speech: copy('Voz detectada…','Speech detected…'),
      'speech-ended': copy('Fin de voz detectado. Procesando dictado…','End of speech detected. Finishing transcript…'),
      paused: copy('Micrófono pausado.','Microphone paused.'),
      unsupported: copy('Este navegador no admite dictado. Usa texto o el dictado del teclado.','This browser does not support dictation. Use text or keyboard dictation.')
    };
    return map[voiceState] || copy('Error de voz; puedes escribir. Detalle: ','Speech error; you can type. Detail: ') + voiceState.replace('error:','');
  }
  const button = (action, text, style='') => `<button type="button" data-iv="${action}" class="${style}" ${pending?'disabled':''}>${text}</button>`;
  function current() {
    if (session && (session.event !== context.state.event || session.owner !== context.state.user?.id)) reset();
  }
  function reset() {
    generation++;realtime?.dispose();caption='';speech?.dispose(); session = null; answer = ''; manual = null; error = ''; mcpToken = '';
  }
  function install(next) {
    session = {...next, owner:context.state.user.id};
    manual = null;
  }
  function view() {
    current();
    const {esc,config} = context;
    const configured = config.interview?.configured;
    const rtConfigured=config.realtime?.configured;
    return `<section class="hero"><div><div class="eyebrow">${copy('ENTREVISTA · TU VOZ, TUS PALABRAS','INTERVIEW · YOUR VOICE, YOUR WORDS')}</div><h1>${copy('Hablemos de lo<br>que puedes construir.','Let’s talk about<br>what you can build.')}</h1><p class="muted">${copy('Una pregunta a la vez. Revisa tus notas y decide cuándo guardarlas.','One question at a time. Review your notes and decide when to save.')}</p></div><span class="badge">${session?.mode==='realtime'?'VOZ IA · REALTIME':session?.mode==='openai'?'OPENAI':copy('GUÍA LOCAL · SIN LLM','LOCAL GUIDE · NO LLM')}</span></section>
      <div class="notice">${copy('Las notas sin confirmar duran hasta 2 horas en memoria del servidor; no se guarda audio. El dictado depende del navegador.','Unconfirmed notes last up to 2 hours in server memory; audio is not stored. Dictation depends on the browser.')} ${copy('Almacenamiento confirmado: ','Confirmed storage: ')}${esc(config.storage?.provider||'sqlite')}.</div>
      ${error?`<div class="notice error" role="alert">${esc(error)}</div>`:''}
      ${!session ? `<div class="card"><h2>${copy('Elige cómo conversar','Choose how to converse')}</h2><label>${copy('Modo de entrevista','Interview mode')}<select id="interview-mode"><option value="realtime" ${mode==='realtime'?'selected':''} ${rtConfigured?'':'disabled'}>${copy('Voz inteligente · conversación continua','Intelligent voice · continuous conversation')}${rtConfigured?'':copy(' · pendiente de activar',' · activation pending')}</option><option value="guided" ${mode==='guided'?'selected':''}>${copy('Guía local (sin claves, respuestas directas)','Local guide (no keys, direct answers)')}</option><option value="openai" ${mode==='openai'?'selected':''} ${configured?'':'disabled'}>${copy('Entrevista adaptativa con OpenAI','Adaptive OpenAI interview')}${configured?'':copy(' · sin configurar',' · not configured')}</option></select></label><p class="hint">${copy('Voz inteligente permite conversar, hacer pausas e interrumpir al asistente. OpenAI por texto también interpreta respuestas naturales. La guía local usa preguntas por campos.','Intelligent voice lets you converse, pause and interrupt the assistant. OpenAI text mode also understands natural answers. The local guide asks field-based questions.')}</p>${!configured?`<p class="hint">${copy('Falta configurar en servidor: ','Missing server configuration: ')}${esc((config.interview?.missing||[]).join(', '))}.</p>`:''}<label class="check"><input id="ai-consent" type="checkbox">${copy('Si elijo OpenAI, autorizo enviar audio, respuestas y notas al proveedor para conversar y preparar mi perfil. Escucharé una voz generada por IA. No incluiré contraseñas ni datos privados de contacto.','If I choose OpenAI, I consent to sending audio, answers and notes to the provider to converse and prepare my profile. I will hear an AI-generated voice. I will not include passwords or private contact details.')}</label>${button('start',copy('Iniciar entrevista →','Start interview →'))}</div>` : session.status==='confirmed'?`<div class="card"><h2>${copy('Tu perfil está confirmado.','Your profile is confirmed.')}</h2><p>${copy('Puedes descubrir conexiones o iniciar otra entrevista para corregirlo.','You can discover connections or start another interview to edit it.')}</p><div class="actions"><button data-page="discover">${copy('Descubrir personas','Discover people')}</button>${button('new',copy('Nueva entrevista','New interview'),'ghost')}</div></div>`: `<div class="grid"><div><section class="card dark"><div class="eyebrow">${copy('PREGUNTA ACTUAL','CURRENT QUESTION')} · ${session.mode==='realtime'?'REALTIME':session.mode==='openai'?'OPENAI':copy('GUÍA LOCAL','LOCAL GUIDE')}</div><h2 id="interview-question">${esc(session.question)}</h2><p class="muted">${copy('Faltantes por conversar: ','Fields left to discuss: ')}${session.missing.length} · ${copy('Revisión','Revision')} ${session.revision}</p>${session.status==='active'?`${session.mode==='realtime'?realtimePanel():''}<div class="actions">${context.state.features.voice && session.mode!=='realtime'?button('listen',copy('● Responder con voz','● Answer by voice')):''}${session.mode!=='realtime'?button('finish',copy('Terminé de hablar','Finished speaking'),'secondary'):''}${session.mode!=='realtime'?button('speak',copy('Escuchar pregunta','Hear question'),'secondary'):''}</div><p id="interview-voice-status" role="status" aria-live="polite">${esc(statusText())}</p><label for="${inputId}">${copy('Tu respuesta (editable)','Your answer (editable)')}</label><textarea id="${inputId}" maxlength="5000" placeholder="${copy('Responde a la pregunta con tus propias palabras…','Answer the question in your own words…')}">${esc(answer)}</textarea><div class="actions">${button('send',pending?copy('Procesando…','Processing…'):copy('Enviar respuesta →','Send answer →'))}${button('pause',copy('Pausar entrevista','Pause interview'),'secondary')}</div><label class="check"><input id="interview-auto-send" type="checkbox" ${autoSend?'checked':''}>${copy('Enviar respuesta al detectar fin del dictado (solo al borrador).','Send answer when dictation ends (draft only).')}</label><label class="check"><input id="interview-read" type="checkbox" ${readAloud?'checked':''}>${copy('Leer cada pregunta en voz alta.','Read each question aloud.')}</label>`: `<p>${copy('Entrevista pausada para revisar.','Interview paused for review.')}</p>${button('resume',copy('Continuar entrevista','Continue interview'),'secondary')}`}${['openai','realtime'].includes(session.mode)?`<div class="actions">${button('guided',copy('Cambiar a guía local','Switch to local guide'),'secondary')}</div>`:''}</section><div class="card"><h3>${copy('Revisar y corregir notas','Review & correct notes')}</h3><p class="hint">${copy('Puedes corregir un campo aquí. Cambiar necesidades/ofertas a «ninguna» elimina esos detalles al confirmar.','You can correct a field here. Setting needs/offers to “none” clears their details when confirmed.')}</p><div class="fields">${fields()}</div><label class="check"><input id="iv-visible" type="checkbox" ${realtime?.active?'disabled':''} ${(manual||session.draft).visible!==false?'checked':''}>${copy('Mostrar perfil en este evento','Show profile at this event')}</label><label class="check"><input id="iv-contact-consent" type="checkbox" ${realtime?.active?'disabled':''} ${(manual||session.draft).share_contact?'checked':''}>${copy('Compartir mi contacto privado solo con conexiones aceptadas','Share my private contact only with accepted connections')}</label><div class="actions">${button('review',copy('Preparar resumen para confirmar','Prepare summary to confirm'))}${button('discard',copy('Descartar entrevista','Discard interview'),'ghost')}</div></div></div><aside><div class="card accent"><h3>${copy('Tus notas, con evidencia','Your notes, with evidence')}</h3>${Object.entries(session.notes).length?Object.entries(session.notes).map(([key,n])=>`<div class="summary-row"><span>${esc(name(key))}</span><p>${esc(noteValue(key,n.value))}</p><details><summary>${copy('Ver origen','View source')}</summary><p>${esc(n.source)}: “${esc(n.evidence)}”</p></details></div>`).join(''):`<p>${copy('Aquí aparecerán los datos que compartas.','The facts you share will appear here.')}</p>`}</div>${session.status==='review'&&session.review_token?`<div class="card"><h3>${copy('Resumen listo para guardar','Summary ready to save')}</h3><p>${copy('La última revisión del resumen incluye los campos de la izquierda. Si cambias algo, prepara el resumen de nuevo.','The latest summary includes the fields on the left. If you edit anything, prepare the summary again.')}</p>${button('confirm',copy('Confirmo este resumen y guardo','Confirm this summary & save'))}</div>`:''}</aside></div>`}
      <details class="card"><summary>${copy('Conectar mi entrevista a MCP','Connect my interview to MCP')}</summary><p>${copy('Genera un token de una hora limitado a tu perfil y a este evento. No lo compartas en el chat ni lo subas a Git. Al cerrar sesión se invalida.','Generate a one-hour token limited to your profile and this event. Do not share it in chat or commit it to Git. Signing out invalidates it.')}</p><div class="actions">${button('mcp',copy('Generar token MCP','Generate MCP token'),'ghost')}${button('revoke',copy('Revocar mis tokens MCP','Revoke my MCP tokens'),'ghost')}</div>${mcpToken?`<label>${copy('Token privado: configúralo como OPEN2CONNECT_MCP_TOKEN','Private token: set as OPEN2CONNECT_MCP_TOKEN')}<input type="password" readonly value="${esc(mcpToken)}" autocomplete="off"></label>`:''}<p class="hint">${copy('Ejecuta el puente con .venv/bin/python -m backend.mcp_server. Configuración completa en docs/INTERVIEW.md.','Run the bridge with .venv/bin/python -m backend.mcp_server. Full setup in docs/INTERVIEW.md.')}</p></details>`;
  }
  function rtStatus() {
    return ({connecting:copy('Conectando voz…','Connecting voice…'),listening:copy('Te escucho. Habla con naturalidad.','Listening. Speak naturally.'),thinking:copy('Organizando tu respuesta…','Organizing your answer…'),speaking:copy('El asistente está hablando. Puedes interrumpirlo.','The assistant is speaking. You can interrupt.'),paused:copy('Micrófono desconectado.','Microphone disconnected.'),error:copy('Voz pausada: revisa el aviso.','Voice paused: check the notice.'),'play-required':copy('Pulsa «Escuchar audio» para habilitar el sonido.','Press “Play audio” to enable sound.')})[rtState] || rtState;
  }
  function realtimePanel() {
    return `<div class="realtime-panel"><div class="voice-orb" aria-hidden="true">◉</div><p id="realtime-status" role="status" aria-live="polite">${context.esc(rtStatus())}</p><p id="realtime-caption">${context.esc(caption)}</p><div class="actions">${button('rt-connect',copy('Conectar voz','Connect voice'),'secondary')}${button('rt-stop',copy('Detener voz','Stop voice'),'secondary')}${button('rt-play',copy('Escuchar audio','Play audio'),'secondary')}${realtime.failed || realtime.unsettled?button('rt-retry',copy('Reintentar notas pendientes','Retry pending notes'),'secondary')+button('rt-discard',copy('Descartar respuesta pendiente','Discard pending reply'),'secondary'):''}</div><p class="hint">${copy('Voz generada por IA. Puedes interrumpir y corregir. Las notas se actualizan tras cada respuesta; detén la voz para editarlas y revisa su exactitud antes de confirmar. Para escribir, detendremos la voz.','AI-generated voice. You can interrupt and correct it. Notes update after each reply; stop voice to edit them and review accuracy before confirming. Typing stops voice.')}</p></div>`;
  }
  function name(k) {
    return ({needs_status:copy('Necesidades','Needs'),offers_status:copy('Aportes','Offers')})[k] || context.fieldName(k);
  }
  function noteValue(key,value) {
    if (!value) return copy('Omitido explícitamente','Explicitly skipped');
    if (key==='needs_status'||key==='offers_status') return value==='none'?copy('Ninguna ahora','None now'):copy('Sí','Yes');
    return context.valueText(key,value);
  }
  function fields() {
    const d = manual || session.draft;
    return ['name','role','experience','sector','interests','languages','purpose','needs_status','problem','help','priority','outcome','offers_status','skills','knowledge','services','resources','availability','contact'].map(k => {
      const choices = ({needs_status:['','present','none'],offers_status:['','present','none'],priority:['','high','medium','low'],availability:['','available','limited','unavailable']})[k];
      const label = v => v==='present'?copy('Sí','Yes'):v==='none'?copy('Ninguna ahora','None now'):v?context.valueText(k,v):copy('Sin indicar','Not specified');
      return `<label>${context.esc(name(k))}${choices?`<select data-iv-field="${k}" ${realtime?.active?'disabled':''}>${choices.map(v=>`<option value="${v}" ${d[k]===v?'selected':''}>${context.esc(label(v))}</option>`).join('')}</select>`:`<input data-iv-field="${k}" ${realtime?.active?'disabled':''} maxlength="1500" value="${context.esc(d[k]||'')}">`}</label>`;
    }).join('');
  }
  function readFields() {
    if (!session || !document.querySelector('[data-iv-field]')) return;
    manual = {...session.draft};
    document.querySelectorAll('[data-iv-field]').forEach(el => manual[el.dataset.ivField]=el.value);
    manual.visible = document.querySelector('#iv-visible').checked;
    manual.share_contact = document.querySelector('#iv-contact-consent').checked;
  }
  async function action(endpoint, extra={}) {
    return context.api('interviews/'+endpoint, {id:session.id, revision:session.revision, ...extra});
  }
  async function sendAnswer() {
    if (pending || !answer.trim()) return;
    pending = true; error = ''; context.render();
    try {
      if(session.mode==='realtime') await realtime.finish();
      if (manual) install(await action('edit',{profile:manual}));
      install(await action('turn',{text:answer})); answer = '';
      if (readAloud && session.mode!=='realtime') speech.speak(session.question,session.locale);
    } catch (e) { error = e.message; }
    finally { pending=false; context.render(); }
  }
  document.addEventListener('input', e => {
    if (e.target.id===inputId) answer=e.target.value;
    if (e.target.matches('[data-iv-field], #iv-visible, #iv-contact-consent')) {
      readFields();
      if (session) session.review_token=null;
    }
  });
  document.addEventListener('change', e => {
    if(e.target.id==='interview-mode') mode=e.target.value;
    if(e.target.id==='interview-auto-send') autoSend=e.target.checked;
    if(e.target.id==='interview-read') readAloud=e.target.checked;
  });
  document.addEventListener('click', async e => {
    const button=e.target.closest('[data-iv]');
    if(!button || pending) return;
    const a=button.dataset.iv;
    if(a==='rt-discard'){realtime.dispose();error=copy('Respuesta pendiente descartada. Puedes escribirla o reconectar y repetirla.','Pending reply discarded. Type it or reconnect and repeat it.');context.render();return;}
    if(a==='rt-play'){try{await realtime.play();}catch(_){error=copy('Pulsa de nuevo para escuchar.','Press again to listen.');context.render();}return;}
    if(a==='rt-retry'){await realtime.retry();context.render();return;}
    if(a==='rt-connect'){
      pending=true;error='';
      try{
        if(realtime.unsettled) await realtime.retry();
        if(realtime.unsettled) throw Error(copy('Reintenta las notas pendientes antes de conectar.','Retry pending notes before connecting.'));
        if(manual)install(await action('edit',{profile:manual}));
        await realtime.start(session.question);
      }catch(e){error=e.message;}finally{pending=false;context.render();}return;
    }
    if(a==='rt-stop'){pending=true;try{await realtime.finish();}catch(e){error=e.message;}finally{pending=false;context.render();}return;}
    if(a==='listen'){speech.listen(session.locale);return;}
    if(a==='finish'){speech.finish();return;}
    if(a==='speak'){speech.speak(session.question,session.locale);return;}
    if(a==='send'){await sendAnswer();return;}
    const consent = document.querySelector('#ai-consent')?.checked;
    if(a==='review' && !realtime.active) readFields();
    pending=true;error='';
    try {
      if(a==='start'){install(await context.api('interviews/start?event='+encodeURIComponent(context.state.event),{mode,locale:document.documentElement.lang,ai_consent:consent}));if(mode==='realtime')await realtime.start(session.question);else if(readAloud)speech.speak(session.question,session.locale);}
      else if(a==='new'){reset();}
      else if(['pause','resume','guided','discard'].includes(a)) {
        speech.pause();
        if(a==='discard')realtime.dispose();else await realtime.finish();
        const next=await action('control',{action:a});
        if(a==='discard')reset();else install(next);
        if(a==='resume' && session.mode==='realtime')await realtime.start(session.question);
      }
      else if(a==='review'){speech.pause();await realtime.finish();readFields();install(await action('summary',{profile:manual}));}
      else if(a==='confirm'){
        if(!session.review_token)throw Error(copy('Prepara el resumen después de corregir.','Prepare the summary after editing.'));
        install(await action('confirm',{confirmed:true,review_token:session.review_token}));
        context.state.draft=await context.api('profile?event='+encodeURIComponent(context.state.event));
        context.state.saved=true;context.state.dirty=false;context.state.recs=null;
      }
      else if(a==='mcp'){mcpToken=(await context.api('mcp/token?event='+encodeURIComponent(context.state.event),{})).token;}
      else if(a==='revoke'){await context.api('mcp/revoke',{});mcpToken='';}
    }catch(e){error=e.message;}
    finally{pending=false;context.render();}
  });
  return {init,view,reset,leave:()=>{speech?.pause();realtime?.stop();}};
})();
