# Realtime para frontend (frontend/realtime.js)

Módulo reutilizable de sesión OpenAI Realtime por WebRTC. Sin módulos ES (CSP
`script-src 'self'`, sin CDN): expone la clase global `O2CRealtime`. Cárgalo
con `<script src="/realtime.js" defer>` **antes** de tu script. Referencia
visual funcionando: `/agent` (frontend/agent.html + agent.js).

## Uso
```js
const rt = new O2CRealtime({
  tokenUrl: '/api/kiosk/token', // ruta propia que da el token efímero
  headers: { 'X-Open2Connect': '1', 'Content-Type': 'application/json' },
  tools: { mi_tool: async (args) => ({ ok: true }) }, // nombre -> async (args) => resultado
  onEvent: (tipo, datos) => { /* ver abajo */ },
});
await rt.conectar();           // token → WebRTC → mic apagado → data channel
rt.empezarAHablar();           // push-to-talk: enciende el mic (botón abajo)
rt.terminarDeHablar();         // suelta el botón: apaga el mic, pide respuesta
rt.decir('Saluda brevemente'); // el agente dice algo por su cuenta
rt.cerrar();                   // termina la sesión
```

## Eventos de `onEvent(tipo, datos)`
- `estado`: `conectando|conectado|escuchando|pensando|hablando|inactivo|error`
- `transcripcion_persona`: texto final de lo que dijo la persona
- `transcripcion_agente_delta` / `transcripcion_agente_fin`: texto del agente
- `herramienta`: `{ nombre, args, resultado }` de cada tool ejecutada
- `uso`: `usage` de `response.done` (para estimar costo)
- `amplitud`: número 0..1, ~20 veces/seg mientras el agente habla — para
  animar una boca: `mouth.setAttribute('ry', 4 + amplitud * 30)`

## Cambiar las tools
Pasa tu propio mapa `tools` al constructor; cada función recibe los args ya
parseados y su retorno se envía de vuelta al modelo. Si pide una tool que no
existe en el mapa, se responde `{error:'herramienta no disponible'}`.

## Nota de costo/ruido
El micrófono va **apagado entre pulsaciones**: solo se enciende mientras se
mantiene presionado el botón (push-to-talk). Es intencional — el audio se
cobra por tiempo de sesión y evita que el ruido de fondo dispare respuestas.
