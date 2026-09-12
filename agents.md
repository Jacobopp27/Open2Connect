# Open2Connect — instrucciones para agentes y reconstrucción

> **Actualización posterior: integración /agent + Supabase.** La petición actual reemplaza el alcance anterior: toda la app tiene una capa PostgreSQL preparada y `/agent` es la única pantalla de entrevista. El usuario decidió iniciar sin migrar datos. Se creó el esquema vacío `o2c_app` en Supabase y la instancia principal ya usa `DATABASE_PROVIDER=postgres`; los datos anteriores se conservan sin importar. Ver [estado, contratos y corte](docs/UNIFIED_DATABASE.md). Los apartados anteriores sobre SQLite obligatorio y kiosco pospuesto describen la base histórica.

Base documental: `d584c14`, 2026-09-12. Este archivo se entrega en minúsculas por petición del usuario. Herramientas que solo descubren `AGENTS.md` deben cargarlo explícitamente; no asumir descubrimiento automático ni crear una segunda copia divergente.

## 1. Lectura y autoridad

Leer en orden: petición vigente, [index.md](index.md), [sdd.md](sdd.md), [skills.md](skills.md), documentación específica y código afectado. Consultar `git status` y commit actual antes de editar. Estas instrucciones describen el proyecto y no sustituyen las instrucciones superiores del entorno ni autorizaciones del usuario.

La última tarea pidió documentación de los nuevos cambios. El usuario había pospuesto corregir el kiosco. No convertir una tarea documental en migración, despliegue, cambio de framework o arreglo de funcionalidades. Preservar cambios ajenos; no hacer reset, checkout destructivo ni sobreescritura de configuración privada.

## 2. Mapa mínimo

- Backend Python: `backend/server.py`, módulos en `backend/modules`, adaptadores en `backend/adapters`.
- Frontend sin build: `frontend/index.html`, `app.js`, CSS y componentes JavaScript.
- Presencial: `/agent`, `/kiosk`; página personal: `/yo/<id>`.
- La entrevista web está oculta; su código y tests permanecen con inconsistencias descritas en `sdd.md`.
- SQLite es obligatorio para identidad y operaciones locales. Supabase es opcional para perfiles.
- Dependencias opcionales en `requirements-integrations.txt`; versiones fijadas en `requirements-integrations.lock.txt`.
- Node se usa para pruebas JavaScript, no para arrancar el producto. No ejecutar `npm install` ni crear Vite por suposición.

## 3. Reconstruir código y dependencias

Repositorio histórico: `https://github.com/Jacobopp27/Open2Connect.git`. Para una instalación nueva, clonar y seleccionar el commit requerido; para continuar trabajo existente, usar el checkout actual y preservar su diff. Un clon solo recupera archivos confirmados: debe incluir también cualquier parche o archivo sin seguimiento que forme parte de la entrega.

```sh
git clone https://github.com/Jacobopp27/Open2Connect.git
cd Open2Connect
git log -1 --oneline
git status --short
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-integrations.lock.txt
```

Python 3.12 fue utilizado en la sesión; Node 22.15 en pruebas anteriores. El modo SQLite guiado puede funcionar con la biblioteca estándar, pero instalar el lock permite reconstruir las integraciones y pruebas. No afirmar que otras versiones fueron verificadas. El Blueprint actual instala el archivo no fijado: existe esa diferencia respecto al entorno reproducible local.

## 4. Configuración local

Si no existe `.env`, copiar `.env.example` y asignarle permisos restrictivos. Si existe, conservarlo y modificar solo lo necesario sin imprimir su contenido.

```sh
cp -n .env.example .env
chmod 600 .env
```

Configuración mínima orientativa para una instancia local nueva:

```dotenv
HOST=127.0.0.1
PORT=8000
OPEN2CONNECT_DB=data/open2connect.db
PROFILE_STORE=sqlite
ENABLE_VOICE=1
ENABLE_CONNECTIONS=1
ENABLE_DEMO=1
COOKIE_SECURE=0
```

El cargador `backend.local` acepta líneas literales `NAME=value`, comentarios en líneas separadas y comillas exteriores opcionales. No realiza expansión de shell ni de variables; el entorno exportado tiene prioridad. No colocar comentarios al final del valor ni ejecutar `.env` con `source`. `.env.example` contiene comentarios históricos: complementar con estas instrucciones y los lectores de configuración reales.

Variables opcionales, solo si se utiliza la función correspondiente:

| Área | Variables |
| --- | --- |
| Entrevista con modelo | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| Voz de entrevista heredada | `OPENAI_REALTIME_MODEL`; la ruta HTTP falta actualmente |
| Voz presencial | `OPENAI_API_KEY`, `REALTIME_MODEL`, `REALTIME_VOICE`, `REALTIME_VAD` |
| Seña mediante imagen | `VISION_MODEL`; comparte `OPENAI_API_KEY` |
| Dispositivo y QR | `KIOSK_KEY`, `REGISTER_URL` o alias `NEXT_PUBLIC_REGISTER_URL` |
| Origen y cookies | `APP_ORIGIN`, `COOKIE_SECURE`, `SESSION_COOKIE_NAME` |
| Supabase REST | `PROFILE_STORE=supabase`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY` o `SUPABASE_SERVICE_ROLE_KEY` |
| PostgreSQL | `PROFILE_STORE=postgres`, `SUPABASE_DB_URL`, `SUPABASE_DB_CA` |
| Perfilado comunitario | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| Ambiguous | `AMBIGUOUS_AGENT_KEY`, `AMBIGUOUS_SHEET_ID`, `AMBIGUOUS_CHANNEL_ID`, `AMBIGUOUS_ORGANIZER_USER_ID` |
| Setup administrativo opcional | `AMBIGUOUS_ADMIN_KEY`, `EVENTO_NOMBRE` para scripts; no requisito de arranque |
| Enriquecimiento | `EXA_API_KEY` |
| MCP local | `OPEN2CONNECT_APP_URL`, `OPEN2CONNECT_MCP_TOKEN` |

La presencia de una variable no demuestra que el proveedor funcione. No insertar claves de servidor en HTML/JS, logs, documentación o argumentos públicos. El defecto actual que inserta `KIOSK_KEY` en HTML está documentado; definir esa clave no vuelve privado el dispositivo.

## 5. PostgreSQL/Supabase

Para el proyecto autorizado en la sesión, el patrón de configuración es:

```dotenv
PROFILE_STORE=postgres
SUPABASE_URL=https://yjloegnuyjziagppvdif.supabase.co
SUPABASE_DB_URL=postgresql://postgres.yjloegnuyjziagppvdif:<URI_ENCODED_PASSWORD>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
SUPABASE_DB_CA=supabase/certs/prod-ca-2021.crt
```

Sustituir el marcador por una credencial obtenida por canal privado; codificar caracteres reservados de la contraseña como componente URI. No copiar una contraseña desde el historial a documentos. La URL REST no sirve por sí sola como credencial PostgreSQL ni la contraseña de base como clave API de Supabase.

El adaptador fuerza verificación TLS de host y CA. Mantener la CA pública y su procedencia documentada en `supabase/certs/README.md`; no desactivar TLS para resolver errores.

```sh
.venv/bin/python -m backend.check_database
```

Este diagnóstico carga `.env` y consulta en modo de solo lectura; no aplica migraciones. Requiere conectividad al destino. Evitar copiar excepciones sin revisar si contienen secretos.

La migración `supabase/migrations/202609120001_profiles.sql` se aplicó al proyecto durante la sesión previa. No es un script general idempotente: no repetirlo ciegamente. Para otra base, preparar y revisar la migración, identificar destino y autorización antes de ejecutarla. No migrar perfiles locales, sesiones o identidades automáticamente.

## 6. Recuperar datos, no solo código

Git no contiene `.env`, credenciales ni la base SQLite privada. Una reconstrucción desde Git recupera la aplicación y sus esquemas, no el estado personal ni los servicios externos. Para continuidad, restaurar un respaldo autorizado de SQLite y mantener sus IDs compatibles con perfiles remotos.

Con la aplicación en funcionamiento, usar la API de backup de SQLite o una copia consistente que incluya el estado WAL; no copiar únicamente el archivo principal abierto. Restaurar en una ruta nueva, verificarla y configurar `OPEN2CONNECT_DB` antes de reemplazar cualquier base. No versionar respaldos.

Los módulos de check-in y encuentros inicializan tablas al importarse. Establecer la ruta de una DB de prueba antes de importar `backend.server`; cambiarla después puede haber tocado ya la base predeterminada.

Kiosco y `/yo` consultan perfiles SQLite directamente aunque `PROFILE_STORE=postgres`. El respaldo local continúa siendo necesario y cambiar de proveedor no sincroniza esas vistas. No prometer coherencia que el código aún no implementa.

## 7. Arranque y navegador

Desde la raíz:

```sh
.venv/bin/python -m backend.local
```

Abrir `http://127.0.0.1:8000/` en el navegador integrado cuando se solicite. `python -m backend.server` no carga `.env`: usarlo cuando el entorno esté configurado explícitamente, como en el despliegue.

Comprobación básica:

```sh
curl --fail http://127.0.0.1:8000/api/health
```

Antes de reiniciar, identificar qué proceso posee el puerto. No matar todos los procesos Python ni reutilizar IDs de sesiones anteriores. Para QA paralela, usar otro puerto, DB temporal y nombre de cookie distinto. El estado de servidores de sesiones anteriores no es garantía de que sigan vivos.

`/agent` requiere conectividad y clave para voz; la cámara/micrófono necesitan permisos del navegador y un contexto seguro admitido. Un QR de teléfono debe apuntar a un origen alcanzable por ese teléfono, no a su propio loopback. Configurar `REGISTER_URL` según la instancia real.

## 8. Pruebas aisladas

Preparar un directorio temporal y ejecutar sin cargar `.env` ni credenciales externas. Este ejemplo conserva PATH para localizar Node y configura únicamente lo necesario; ajustar rutas si el entorno requiere herramientas adicionales.

```sh
qa_dir=$(mktemp -d)
env -i PATH="$PATH" HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" \
  OPEN2CONNECT_DB="$qa_dir/test.db" PROFILE_STORE=sqlite \
  .venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.cjs
```

No usar `backend.local` para iniciar QA con configuración privada. Revisar las pruebas antes de habilitar proveedores; simular salidas externas de perfilado/Ambiguous/Exa. Los tests de PostgreSQL no reemplazan una prueba real del destino autorizado.

La base actual tiene una discrepancia conocida entre pruebas Realtime, clase del frontend y ruta de voz. No cambiar la especificación para esconder fallos ni reutilizar los conteos históricos de 39 Python/10 JavaScript como resultado nuevo. Registrar comando, commit, conteos y errores efectivamente observados.

Smoke funcional en instancia aislada: registrar dos usuarios sintéticos; guardar perfiles complementarios; descubrir; invitar/aceptar y verificar contacto; bloquear y comprobar filtros; comprobar aislamiento de entrevista si se trabaja ese módulo. Para el flujo nuevo, comprobar cámara denegada, corrección de seña, check-in, consulta `/yo` y repetición de encuentro. Habilitar mensajes externos solo con autorización explícita; un encuentro puede avisar al staff.

No añadir tests para simples cambios documentales. Validar referencias y secretos en ese caso. Las pruebas con mocks y las verificaciones reales de audio, cámara y proveedor deben informarse por separado.

## 9. MCP, despliegue e integraciones

El puente local se inicia con `.venv/bin/python -m backend.mcp_server`, con URL de aplicación y token temporal generado por la aplicación. Mantener transporte stdio y alcance participante/evento; no exponerlo públicamente sin diseño y autorización específicos.

Para despliegue leer `render.yaml` y `docs/DEPLOY_RENDER.md`. Confirmar origen, HTTPS, cookies, secretos, DB durable y diagnóstico de integraciones. El Blueprint selecciona SQLite por defecto y autoDeploy; un push puede tener consecuencias de publicación. El keepalive apunta a una URL concreta y oculta errores del ping; no acredita operación sana ni persistencia. No crear otra automatización a partir de esta documentación.

El perfilado al guardar `/api/profile` puede consultar comunidad y escribir en Ambiguous. `encuentros.confirmar` puede actualizar una hoja y avisar al staff. No llamar a estas rutas sobre datos reales solo para comprobar una pantalla si producirían comunicaciones no autorizadas.

## 10. Entrega y continuidad

Usar la skill del proyecto cuando corresponda a desarrollo de entrevista; consultar documentación oficial vigente cuando se cambien contratos externos. No crear skills, plugins, frameworks ni agentes paralelos por defecto. Seguir el alcance autorizado y completar el trabajo reversible necesario sin pedir confirmaciones repetidas.

Antes de entregar:

1. Revisar diff y preservar archivos ajenos.
2. Comprobar criterios de `sdd.md` relevantes.
3. Revisar que no se incluyan secretos, DB, fotos, logs privados o respaldos.
4. Actualizar `index.md` con decisión, commit y evidencia; actualizar instrucciones si cambia el arranque.
5. Informar qué cambió, qué se comprobó y qué sigue pendiente.

No afirmar que una URL externa funciona sin verificarla, que una propuesta React está integrada, que la pestaña oculta elimina su código, ni que una prueba de una versión anterior valida esta. No publicar la rama histórica de respaldo ni hacer force push. Publicación, cambios remotos y comunicaciones requieren autorización aplicable al acto concreto.
