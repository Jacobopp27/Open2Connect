# Open2Connect

Aplicación local interactiva para conectar participantes de hackatones y eventos LATAM: quién eres, qué necesitas y qué puedes aportar. Interfaz en español/inglés, JavaScript sin dependencias y backend Python modular con SQLite.

## Arranque

Requiere Python 3.10+ con SQLite. Desde la raíz del repositorio:

```sh
python3 -m backend.server
```

Abre **http://127.0.0.1:8000**. No requiere paquetes ni claves API. La base se crea automáticamente en `data/open2connect.db` y el perfil confirmado persiste al recargar o volver a iniciar sesión. Detén el servidor con Ctrl+C. Reinícialo después de modificar código Python; el frontend se actualiza al recargar.

## Entrevista por voz y nuevas integraciones

Abre **Entrevista / Interview** para conversar una pregunta a la vez, dictar o escribir, pausar/reanudar, corregir notas y confirmar el perfil. La guía local funciona sin claves; el adaptador real de OpenAI requiere configuración y consentimiento. Se incluyen un puente MCP autenticado y un repositorio de perfiles Supabase configurable. Ninguna integración remota está activada por defecto. [Configuración, pruebas y límites](docs/INTERVIEW.md).

## Demo interactiva

1. Crea una cuenta local con un correo de prueba y una contraseña de al menos 10 caracteres. Para pruebas, utiliza direcciones ficticias `@example.invalid`.
2. En **Mi perfil**, completa el formulario o pega el texto de ejemplo siguiente en **Escribe o corrige tu dictado** y pulsa **Organizar borrador**.
3. Revisa todos los campos, pulsa **Revisar mi resumen** y después **Confirmo y guardo mi perfil**. La extracción nunca guarda por sí sola.
4. En **Descubrir**, pulsa **Añadir 3 perfiles ficticios de demo**. Verás hasta tres recomendaciones sustentadas en datos de SQLite. Estos perfiles están marcados DEMO y no aceptan invitaciones.
5. Para probar una conexión real entre dos cuentas controladas por ti, crea una segunda cuenta en una ventana privada. Usa el perfil complementario de abajo, confirma ambos perfiles, envía una invitación y acéptala desde **Conexiones** en la segunda sesión. Pulsa **Actualizar** en la primera.
6. El contacto aparece solo después de aceptar y si su dueño marcó el consentimiento para compartirlo. La invitación inicial constituye el consentimiento del emisor; la aceptación, el del receptor. Rechazar mantiene el contacto privado.

Ejemplo A, persona ficticia:

```text
Nombre: Alex DEMO; rol: Desarrollador backend; experiencia: 3 años; sector: Educación; intereses: IA y educación; idiomas: Español, English; propósito: Crear un prototipo educativo; problema: Necesito diseño UX; necesito: Diseño UX; prioridad: alta; resultado: Prototipo validado; ofrezco: Python y APIs; conocimiento: Backend; servicios: Desarrollo de APIs; recursos: Herramientas de código abierto; disponibilidad: disponible; contacto: alex@example.invalid
```

Ejemplo B, persona ficticia complementaria (selecciona EN si vas a dictarlo):

```text
Name: Bea DEMO; role: Product designer; experience: 4 years; sector: Education; interests: AI and education; languages: English, Spanish; purpose: Build an education prototype; problem: I need a Python backend; I need: Python APIs; priority: high; outcome: Working Python API; I offer: UX design; knowledge: User research; services: Interface design; resources: Design kit; availability: available; contact: bea@example.invalid
```

Puedes tener dos sesiones aisladas también usando `http://127.0.0.1:8000` y `http://localhost:8000` en el mismo equipo. Usa consistentemente cada dirección; sus cookies son distintas.

Para repetir desde cero **sin borrar datos existentes**, arranca otra base con un nombre nuevo y otro puerto:

```sh
OPEN2CONNECT_DB=data/demo-ensayo-02.db PORT=8001 python3 -m backend.server
```

No se crean participantes de manera silenciosa. Puedes indicar explícitamente que no tienes necesidades u ofertas; no es obligatorio tener ambas. El botón DEMO añade los mismos tres perfiles una sola vez y conserva cualquier cuenta existente.

## Qué funciona y qué está limitado

- Perfiles generales reutilizables; propósito, necesidades, ofertas, disponibilidad y contacto separados por evento.
- Sesiones con cookie HttpOnly/SameSite, contraseñas scrypt, acceso por usuario, límites básicos de intentos de acceso y protección de solicitudes de escritura entre orígenes.
- Dictado **real del navegador**, si existe `SpeechRecognition`/`webkitSpeechRecognition`. Puede requerir permisos, conexión y servicios del navegador. En contextos no compatibles siempre queda texto. No se guarda audio en el backend. No se ha validado el micrófono con una persona hablando en esta entrega.
- Extracción **basada en reglas**, no un LLM: reconoce etiquetas explícitas en ES/EN, propone cambios y muestra campos faltantes. Usa punto o `;` entre campos. No entiende toda conversación libre, negaciones complejas ni correcciones ambiguas. Corrige los campos manualmente si hace falta. El módulo Entrevista añade guía interactiva y un adaptador OpenAI real configurable; no se ha probado la conexión a un modelo por falta de credenciales.
- Matching real desde la base de datos, con vocabulario bilingüe limitado y coincidencias literales. Considera complementariedad en ambas direcciones, necesidad compartida o afinidad, sin exigir las tres. Excluye otros eventos, el propio usuario, perfiles ocultos, bloqueos, falta de disponibilidad y ausencia de idioma conocido compartido. Idiomas reconocidos: ES, EN, PT, FR. No usa porcentajes inventados ni cercanía física.
- Invitaciones, aceptación/rechazo, bloqueo y consentimiento de contacto. Las notificaciones son internas y requieren actualizar; no hay push, correo, chat, desbloqueo ni reenvío de una invitación rechazada en este MVP.
- Interfaz responsive ES/EN. No se ha validado en dispositivos móviles físicos. Para voz en un móvil real hace falta un origen seguro accesible desde ese dispositivo; `localhost` del móvil no es el equipo servidor.
- El registro es abierto para demo: no verifica email, no recupera contraseñas y no valida entradas privadas a eventos. No es una versión de producción endurecida.

Pagos, Bluetooth, NFC y hardware están fuera del MVP.

## Pruebas

```sh
python3 -m unittest discover -s tests -v
```

Suite de pruebas HTTP de integración (incluye las 12 originales y pruebas de entrevista/adaptadores), con base temporal aislada y puerto efímero: persistencia/login/logout, aislamiento de cuentas y eventos, confirmación y validación, extracción sin guardado, matching bilingüe y privacidad, filtros, cero resultados, perfiles demo, aceptación/rechazo y consentimiento revocable, acceso indebido, CSRF y conexiones opcionales. No modifican la base local. El sistema debe permitir abrir puertos en loopback.

## Arquitectura y colaboración

- `backend/server.py`: rutas HTTP, validación de transporte, configuración y archivos estáticos.
- `backend/db.py`: esquema SQLite y conexiones.
- `backend/modules/events.py`: eventos y ejemplos explícitos.
- `backend/modules/profiles.py`: perfil general y por evento, confirmación.
- `backend/modules/interviews.py`: entrevista, notas, revisiones, confirmación y estado transitorio.
- `backend/adapters/`: adaptadores OpenAI y SQLite/Supabase.
- `backend/mcp_server.py`: puente MCP stdio autenticado y acotado.
- `frontend/interview.js`, `frontend/speech.js`: entrevista y ciclo de voz separados.
- `.agents/skills/voice-profile-interview/SKILL.md`: skill de desarrollo/operación; no ejecuta el runtime web.
- `backend/modules/conversation.py`: adaptador de extracción reemplazable, contrato `extract(text, profile)`.
- `backend/modules/matching.py`: vocabulario bilingüe, filtros y evidencia.
- `backend/modules/connections.py`: invitaciones, respuestas, contacto y bloqueos.
- `backend/modules/notifications.py`: notificaciones internas.
- `backend/modules/auth.py`: autenticación y sesiones.
- `frontend/app.js`, `frontend/styles.css`: UI y adaptador de voz del navegador.

La API JSON usa cookie de sesión. Las escrituras requieren `Content-Type: application/json` y `X-Open2Connect: 1`. Rutas principales: `/api/register`, `/api/login`, `/api/me`, `/api/events`, `/api/profile?event=medellin-2026`, `/api/conversation`, `/api/recommendations`, `/api/connections`, `/api/connections/invite`, `/api/connections/respond`, `/api/notifications`, `/api/block`. El evento por defecto es `medellin-2026`.

Variables: `HOST`, `PORT`, `OPEN2CONNECT_DB`, `ENABLE_VOICE`, `ENABLE_CONNECTIONS`, `ENABLE_DEMO`, `COOKIE_SECURE`, `APP_ORIGIN`. Exportarlas desde el shell; `.env` no se carga automáticamente. Con `ENABLE_VOICE=0` queda texto; con `ENABLE_CONNECTIONS=0` queda búsqueda.

Plan del equipo y gate local antes de producción: [docs/TEAM_PLAN.md](docs/TEAM_PLAN.md). Guion de presentación: [docs/DEMO.md](docs/DEMO.md). Preparación de despliegue: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
