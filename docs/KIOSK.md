# Kiosco de check-in por voz "Mesa 4"

WebRTC directo navegador → OpenAI Realtime. El servidor solo crea el token
efímero (`backend/modules/kiosk.py`) y ejecuta las tools; el audio nunca pasa
por este backend. Requiere aplicar `docs/server.py.suggested.patch` a
`backend/server.py` (no aplicado; lo mantiene otro compañero).

## Variables de entorno

- `OPENAI_API_KEY` — obligatoria para `/api/kiosk/token`.
- `KIOSK_KEY` — opcional; si se define, las rutas `/api/kiosk/*` exigen el
  header `X-Kiosk-Key` con este valor (se inyecta solo en `/kiosk` vía
  `<meta name="kiosk-key">`). Sin definir, se permite en local.
- `REGISTER_URL` (o `NEXT_PUBLIC_REGISTER_URL`) — URL de registro mostrada en
  el QR cuando la persona no está registrada. Por defecto, la raíz de la app.
- `REALTIME_MODEL` (`gpt-realtime`), `REALTIME_VOICE` (`marin`).
- `REALTIME_VAD=1` — cambia de push-to-talk a `server_vad` (700 ms de
  silencio). Por defecto push-to-talk, porque la mesa es ruidosa.

## Cómo correrlo

1. Aplicar el parche: `git apply docs/server.py.suggested.patch` (o a mano).
2. `export OPENAI_API_KEY=... KIOSK_KEY=... REGISTER_URL=https://tu-app/`
3. `python3 -m backend.server` y abrir `http://localhost:8000/kiosk`.

## CSP requerida (ya incluida en el parche)

`connect-src 'self' https://api.openai.com; media-src 'self' blob:;`
(`script-src 'self'` se mantiene: todo el JS del kiosco es local, sin CDN).

## Probar sin voz (curl)

```
H='-H X-Open2Connect:1 -H Content-Type:application/json'
curl -s $H -X POST -d '{"nombre":"Ana"}' localhost:8000/api/kiosk/buscar
curl -s $H -X POST -d '{"id":"<id>","sena":"camisa azul"}' localhost:8000/api/kiosk/checkin
curl -s $H -X POST -d '{"id":"<id>"}' localhost:8000/api/kiosk/recomendar
```

## Frases de prueba para el agente

1. "Hola, me llamo Ana Gómez." → debe buscarla y confirmar su perfil.
2. "No, todavía no me he registrado." → debe mostrar el QR y despedirse.
3. "Vengo a resolver cómo conseguir usuarios, y puedo ayudar con diseño UX. Ando de camisa azul." → debe guardar, hacer check-in y recomendar.
