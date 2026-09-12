# Open2Connect — flujo de skills

Base: `d584c14`, 2026-09-12. Este archivo documenta cómo construir y mantener la aplicación. No instala skills ni se ejecuta dentro del producto. Contexto: [index.md](index.md); contratos: [sdd.md](sdd.md); entorno: [agents.md](agents.md).

## Skills y capacidades

| Skill o capacidad | Cuándo usarla | Resultado esperado |
| --- | --- | --- |
| [voice-profile-interview](.agents/skills/voice-profile-interview/SKILL.md) | Modificar entrevista, notas, voz, alcance MCP o persistencia de perfiles | Cambios que preservan evidencia, propietario/evento y confirmación |
| `openai-docs`, si está disponible en el catálogo del agente | Cambiar APIs, modelos, contratos Realtime/Responses o comportamiento dependiente de OpenAI | Contrato contrastado con documentación oficial vigente; distinguir prueba simulada y real |
| `skill-creator`, si está disponible | Solicitud de crear o mantener una skill ejecutable | `SKILL.md` acotado y validado; no confundir con este documento |
| `plugin-management:plugin-management`, si está disponible | Una integración necesaria no tiene herramientas accesibles | Identificar capacidad y permisos; no instalar plugins por mera afinidad |
| Lectura de código/Git, edición, terminal, navegador | Trabajo habitual sobre esta aplicación | Implementación revisable y evidencia apropiada |

La única skill específica del proyecto referenciada aquí está en `.agents/skills/voice-profile-interview/SKILL.md`. Las skills de sistema se localizan desde el catálogo del entorno actual; sus rutas personales no son dependencias del proyecto. No se necesita una skill de React, imágenes o hosting para editar el frontend actual. Usarlas solo si el encargo correspondiente lo exige.

## Flujo de construcción

| Fase | Entrada y trabajo | Salida / criterio para avanzar |
| --- | --- | --- |
| 1. Contexto | Leer petición más reciente, estos cuatro documentos, `git status` y diff | Alcance claro, cambios ajenos preservados y base identificada |
| 2. Especificación | Elegir requisitos de `sdd.md`; distinguir implementado, brecha y propuesta | Escenarios de aceptación y exclusiones explícitas |
| 3. Contratos | Leer rutas, validadores, almacenamiento y frontend involucrados; consultar documentación oficial si cambia un proveedor | Payloads, identidad, errores y persistencia definidos |
| 4. Implementación | Cambiar el módulo responsable y su consumidor | Flujo completo, sin rutas ficticias ni fallback silencioso |
| 5. Verificación | Pruebas enfocadas y regresiones relevantes con DB temporal | Resultados con conteos reales; fallos analizados, sin usar datos personales |
| 6. Experiencia | Comprobar interfaz aislada, errores, permisos y recuperación | Escenarios observables; voz/cámara reales identificados como pendientes si no se prueban |
| 7. Servicios externos | Solo cuando el encargo lo requiera y haya configuración autorizada | Evidencia remota separada de mocks; ninguna credencial en salida |
| 8. Entrega | Actualizar especificación, historial y reconstrucción | Diff coherente, limitaciones claras y acciones autorizadas completadas |

No publicar, migrar una base remota ni enviar comunicaciones por el simple hecho de llegar a la fase 8. Utilizar la autorización concreta de la sesión y resolver primero todo el trabajo preparatorio que corresponda.

## Recetas por área

### Perfil y entrevista

1. Leer `profiles.py`, `interviews.py` y la skill del proyecto.
2. Mantener perfil general separado de necesidades/ofertas del evento.
3. Permitir corrección y ausencia explícita de necesidades/ofertas; no inventar evidencia.
4. Mantener alternativa escrita en el flujo de entrevista que la ofrece.
5. Validar propietario, evento, revisión, reintentos y confirmación antes de persistir.
6. Revisar cuál interfaz está activa: la pestaña web está oculta en esta base y `/agent` tiene otro contrato.

### Voz y visión presencial

1. Leer `kiosk.py`, `agent.js` y `realtime.js`; no sustituir su clase con la de entrevista heredada.
2. Separar transporte de audio, invocación de herramientas y almacenamiento.
3. Definir y comprobar permisos de micrófono/cámara, consentimiento y alternativa si falla la captura.
4. Para fotos, limitar descripción a ropa/accesorios, no inferir atributos sensibles y no registrar la imagen.
5. Probar cancelación, repetición de herramientas y desconexión. Documentar acceso del dispositivo y páginas personales como límites específicos.

Esta receta no reabre por sí sola el arreglo del kiosco pospuesto por el usuario.

### Persistencia

1. Determinar `PROFILE_STORE` y qué módulos evitan el adaptador.
2. Preparar cambios de esquema versionados; identificar la base de destino antes de ejecutarlos.
3. Mantener consultas parametrizadas, guardado atómico y TLS verificado.
4. Validar error del proveedor sin escrituras ocultas en SQLite.
5. Probar identidad/evento y continuidad de IDs locales al usar nube.

### MCP

Usar el SDK y puente existentes, token acotado a participante/evento y pruebas de protocolo reales con servidor de prueba. No exponer SQL, claves de servicio ni IDs arbitrarios como mecanismo de autorización. La declaración de una herramienta no demuestra una integración funcional.

### Integraciones y entrega

Ambiguous puede escribir registros y avisar al staff; Exa y OpenAI envían datos a servicios externos. Aislar o simular estos adaptadores durante QA. No enviar mensajes a terceros sin autorización explícita. Comprobar despliegue solo si es parte del encargo; un healthcheck no valida toda la aplicación.

## Coordinación y mantenimiento

El reparto histórico fue backend/Jacobo, frontend/Luis e integraciones-voz/Juan; es contexto, no una asignación obligatoria actual. No crear tareas ni subagentes automáticamente. Si se autoriza delegación, repartir módulos independientes con contratos y una integración final.

Antes de declarar terminado un cambio, registrar: requisito, archivos, verificaciones ejecutadas, limitaciones y estado de integración. Si se modifica una skill ejecutable, mantenerla alineada con el contrato actual; este archivo por sí solo no cambia instrucciones de la skill ni capacidades instaladas.
