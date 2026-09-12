# Despliegue en Render (plan gratis)

Complementa [DEPLOYMENT.md](DEPLOYMENT.md): documenta un proveedor concreto
(Render, Web Service nativo de Python, sin Docker) vía `render.yaml`. No
sustituye las pruebas de dos usuarios en HTTPS descritas allí.

## Pasos

1. Crea una cuenta en [render.com](https://render.com).
2. Dashboard → **New** → **Blueprint**.
3. Conecta el repo `Jacobopp27/Open2Connect`. Render lee `render.yaml` y
   propone el servicio `open2connect` (Python, plan free, región Virginia).
4. Antes de confirmar, carga en el panel las variables `sync: false` (nunca
   van en el repo):
   - `KIOSK_KEY` — clave que exigirán `/api/kiosk/*` (inventa una larga).
   - `OPENAI_API_KEY` — solo si usas el kiosco de voz o entrevista OpenAI.
   - `AMBIGUOUS_AGENT_KEY`, `AMBIGUOUS_SHEET_ID`, `AMBIGUOUS_CHANNEL_ID`, `AMBIGUOUS_ORGANIZER_USER_ID` — solo si integras Ambiguous "Mesa 4".
   - `EXA_API_KEY` — solo si usas enriquecimiento público (Exa).
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (y/o `SUPABASE_SECRET_KEY`)
     — solo si usarás `PROFILE_STORE=supabase`.
   - `APP_ORIGIN`, `REGISTER_URL` — déjalas vacías por ahora (paso 6).
5. Deploy. Espera build (`pip install -r requirements-integrations.txt`) y
   arranque; revisa `/api/health` en los logs.
6. Copia la URL pública asignada (p. ej. `https://open2connect.onrender.com`).
   Vuelve a Environment, pon `APP_ORIGIN` y `REGISTER_URL` con esa URL y
   deja que redeploy (automático o manual).

## Limitaciones del plan gratis

- **Disco efímero**: SQLite (usuarios, check-ins, sesiones) vive en el
  contenedor y se reinicia en cada deploy y al despertar: **se pierde todo**.
  Pendiente conocido, no un bug.
- **Se duerme tras ~15 min sin tráfico**, tarda ~50 s en despertar.
- Mitigación hoy: (a) ping externo a `/api/health` cada 5-10 min (UptimeRobot
  o cron-job.org, gratis) para mantenerlo despierto; (b) registra a las
  personas el mismo día del evento, no antes; (c) para persistencia real de
  **perfiles**, usa `PROFILE_STORE=supabase` — pero **cuentas (users)** y
  **check-ins** siguen en SQLite y se pierden igual al reiniciar, hasta
  migrarlos a un almacén compartido.

## Probar tras el deploy

- Abre `/agent` en Chrome sobre HTTPS (el micrófono lo requiere) y prueba el flujo de voz.
- `GET /api/health` debe responder `{"status":"ok"}`.
- Abre `/kiosk` y confirma que el QR apunta a la URL pública real, no a `localhost`.
