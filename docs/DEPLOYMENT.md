# Preparación de producción — pendiente de proveedor

Estado: implementación y pruebas locales. No se ha desplegado un entorno de producción ni contratado servicios.

Antes de desplegar se requiere acordar proveedor/cuenta, dominio, HTTPS y un volumen persistente privado para SQLite. El servidor estándar de Python es para la demo local; antes de exposición pública se debe usar un servidor y proxy adecuados, límites de peticiones/concurrencia, timeouts y monitorización. Deben resolverse verificación de correo, recuperación de cuenta y control de entrada a eventos privados si van a usarse.

Configuración esperada:

```text
HOST=127.0.0.1
PORT=8000
OPEN2CONNECT_DB=/ruta/privada/persistente/open2connect.db
APP_ORIGIN=https://dominio-aprobado
COOKIE_SECURE=1
ENABLE_DEMO=0
ENABLE_VOICE=1
ENABLE_CONNECTIONS=1
```

No usar una base de datos efímera o el sistema de archivos de una función serverless. Para múltiples instancias o mayor volumen, migrar el adaptador de persistencia a una base compartida y el limitador de autenticación a almacenamiento compartido. Preparar copias de seguridad y probar restauración.

`GET /api/health` es el endpoint de disponibilidad. Tras pasar el gate local del plan del equipo, desplegar solo con autorización y repetir las pruebas de dos usuarios en HTTPS: sesión, persistencia después de reiniciar, ES/EN, dictado/fallback, cero resultados, filtros, aceptación/rechazo y revocación de contacto. Verificar cookies Secure y bloqueo de solicitudes desde otros orígenes. Usar solo cuentas sintéticas de prueba.

## Entrevista, IA, MCP y Supabase

El adaptador real de OpenAI, puente MCP local autenticado y repositorio Supabase están implementados. La configuración, migraciones, fronteras de autorización y limitaciones de prueba están en [INTERVIEW.md](INTERVIEW.md). No se han verificado conexiones remotas: faltan credenciales/proyecto. Antes de exponer el servicio, validar con el proveedor real, ejecutar las pruebas SQL en un proyecto de prueba autorizado y definir retención/consentimiento. El estado transitorio de entrevista vive en un único proceso; escalar requiere un repositorio de borradores con TTL y control de versiones compartido.
