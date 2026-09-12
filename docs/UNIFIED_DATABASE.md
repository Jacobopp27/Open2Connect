# Integración unificada: /agent + Supabase PostgreSQL

## Estado de esta entrega

El usuario indicó que no necesita migrar datos. Se creó el esquema vacío `o2c_app` mediante `backend.setup_database`, con un evento inicial y sin importar cuentas, sesiones ni perfiles anteriores. La instancia principal se reinició con `DATABASE_PROVIDER=postgres`, `PROFILE_STORE=postgres` y demo/sincronización externa desactivados.

Se validó contra PostgreSQL real: registro y sesión, perfiles, invitación/aceptación y contacto, actualización de entrevista, llegada, recomendaciones, encuentro idempotente y bloqueo. Los datos sintéticos se revirtieron; quedaron cero cuentas de prueba. TLS verificado y acceso directo `anon`/`authenticated` al esquema denegado.

Para una instalación nueva sin datos anteriores:

```sh
.venv/bin/python -m backend.setup_database
```

El comando se detiene si el esquema ya existe y no lee SQLite ni las tablas anteriores de perfiles. No ejecutar el importador de datos para este despliegue. Se necesita registrar una cuenta nueva. `OPENAI_API_KEY` sigue vacía, por lo que falta configurar voz real.

## Arquitectura nueva

`DATABASE_PROVIDER=postgres` dirige todas las conexiones de `backend.db` al esquema privado `o2c_app` en Supabase. Usuarios, sesiones, perfiles, eventos, invitaciones, bloqueos, notificaciones, check-ins y encuentros comparten la misma base. La autenticación sigue siendo propia, con las contraseñas derivadas existentes; no se convierte a Supabase Auth.

El repositorio de perfiles usa esas mismas tablas cuando el proveedor global es PostgreSQL. Los adaptadores anteriores de perfiles permanecen para compatibilidad con configuraciones antiguas, pero no se usan en el modo unificado. SQLite queda como opción explícita de pruebas/demo, sin fallback automático cuando falla Supabase.

`/agent` es la única pantalla de entrevista. `/kiosk`, `/interview` y `/interviews` redirigen a ella. La aplicación principal dejó de cargar el cliente de entrevista heredado; sus API internas y el puente MCP se conservan por compatibilidad, sin otra pantalla de entrevista.

## Flujo del participante

1. Crear cuenta/iniciar sesión y confirmar el perfil inicial en `/`.
2. Abrir Entrevista en el menú; se conserva el evento seleccionado.
3. Pulsar Iniciar entrevista, después de leer el aviso de envío de audio a OpenAI.
4. Confirmar en pantalla los cambios propuestos antes de guardarlos y confirmar la seña antes del check-in.
5. Autorizar separadamente una fotografía si se desea; alternativa: descripción verbal.
6. Ver recomendaciones y abrir `/yo/<id>?event=…` con la sesión del mismo participante. En otro dispositivo hay que iniciar sesión con esa cuenta.

Las herramientas de `/api/agent/*` derivan la identidad de la sesión; no permiten buscar/modificar otras cuentas. Este flujo sustituye el antiguo dispositivo público que operaba sobre personas arbitrarias. La clave de kiosco ya no se inserta en HTML. `/api/kiosk/*` no ofrece herramientas operativas.

Las sugerencias de `/agent` y `/yo` reutilizan los filtros de matching web. La consulta de estado no envía avisos externos. `ENABLE_EXTERNAL_SYNC=1` activa los hooks existentes de CRM/staff; queda desactivado por defecto. El acceso por QR no es una credencial.

## Importador opcional — no utilizado ni autorizado en este despliegue

Destino: proyecto Supabase `yjloegnuyjziagppvdif`, esquema nuevo `o2c_app`. Archivo: `supabase/migrations/202609120002_app_database.sql`.

El diagnóstico previo contó 5 usuarios, 1 evento, 3 perfiles locales y 3 sesiones; las restantes tablas estaban vacías. El número exacto puede cambiar si continúa utilizándose la instancia antigua.

`backend.migrate_database` prepara un backup consistente de SQLite, aplica DDL e importación en una transacción y conserva los datos de origen. Los perfiles de las tablas anteriores `public.o2c_*` prevalecen sobre copias locales para identidades/eventos conocidos. Las tablas anteriores no se borran. Si `o2c_app.users` ya existe, el importador se detiene para no sobrescribir datos activos.

La copia incluye hashes de contraseña y sesiones vigentes para conservar cuentas y acceso. Antes del corte, detener la instancia antigua para evitar escrituras durante la copia. Obtener autorización específica de esa operación remota y usar el destino configurado, sin imprimir secretos.

```sh
.venv/bin/python -m backend.migrate_database --check
# Solo después de la aprobación y con la instancia antigua detenida:
.venv/bin/python -m backend.migrate_database --apply
```

Tras éxito, editar `.env` sin reemplazar las demás credenciales:

```dotenv
DATABASE_PROVIDER=postgres
PROFILE_STORE=postgres
SUPABASE_DB_CA=supabase/certs/prod-ca-2021.crt
ENABLE_EXTERNAL_SYNC=0
```

Mantener `SUPABASE_DB_URL` privado, con TLS verificado. Ejecutar `.venv/bin/python -m backend.local`. En despliegue, `render.yaml` define ahora el proveedor global PostgreSQL y dependencias fijadas; no desplegar hasta aplicar la migración.

## Validación y recuperación

Antes de dar el corte por terminado: comprobar conexión real, conteos, login existente, perfil, cambio confirmado, invitación/aceptación, bloqueo, check-in y encuentro; verificar que los permisos `anon`/`authenticated` no acceden al esquema privado. No ejecutar pruebas que borren tablas sobre la base de usuarios reales.

La suite usa una base SQLite temporal y cubre la capa de autorización, consentimiento, filtros, idempotencia de encuentros y el transporte de voz actual. No prueba el micrófono físico ni el servicio OpenAI real.

Si falla la migración, se revierte su transacción y se conserva SQLite. Si falla después del corte, detener escrituras antes de decidir recuperación; no volver a SQLite sin reconciliar los datos creados en PostgreSQL. Nunca borrar el esquema remoto automáticamente como estrategia de rollback.

## Límites pendientes

- Completado: esquema nuevo, validación PostgreSQL real con rollback y reinicio de la instancia principal. No se migraron datos.
- `OPENAI_API_KEY` está vacía en la configuración local comprobada. Configurarla por canal privado y probar una conversación real con micrófono y cámara opcional.
- Los borradores del módulo MCP heredado siguen en memoria; esto no afecta los perfiles confirmados.
- La escritura CRM/staff es opcional y no fue validada contra servicios externos.
