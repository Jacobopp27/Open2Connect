# Agenda del equipo · 12 septiembre 2026 · Bogotá

Objetivo: MVP integrado verificable antes de 15:30, ventana de entrega 15:30–16:00; 16:00 es la meta, 17:00 el límite externo. Este plan es una agenda de trabajo; no afirma que haya revisiones automáticas programadas.

| Responsable | Área | Entregable verificable |
| --- | --- | --- |
| Jacob | Backend Python: perfiles, persistencia, matching, privacidad y conexiones | Pruebas HTTP pasan, dos cuentas aisladas, contacto privado antes de aceptación |
| Luis | Frontend JS: flujo móvil ES/EN, perfil y corrección, estados y demo | Formulario → resumen → confirmar → recargar → recuperar; responsive y texto alternativo |
| Juan | Middleware/integración: voz, adaptador de IA, contratos y errores | Voz o texto completa el mismo borrador; no guardar sin confirmación; errores recuperables |

## Revisiones cada 20 minutos

Desde la próxima hora redonda: 12:00, 12:20, 12:40, 13:00, 13:20, 13:40, 14:00, 14:20, 14:40, 15:00 y 15:20. En cada revisión, máximo 3 minutos: enseñar una acción funcionando, indicar bloqueo concreto y acordar una única prioridad para los siguientes 20 minutos.

1. **12:00–12:40 — Base local.** Jacob verifica identidad/perfil; Luis entrada y edición; Juan contrato de extracción. Gate: confirmar, recargar y recuperar datos.
2. **12:40–13:20 — Voz y necesidades/ofertas.** Juan valida micrófono ES/EN y fallback; Luis resumen corregible; Jacob validación. Decidir proveedor/modelo solo si hay credenciales autorizadas. Si no, declarar reglas y conservar demo funcional.
3. **13:20–14:00 — Matching.** Jacob vocabulario y evidencia; Luis tarjetas y estado vacío; Juan pruebas bilingües y filtros. Gate: recomendaciones de registros reales sin contacto privado.
4. **14:00–14:40 — Dos participantes.** Jacob estados/consentimiento; Luis invitaciones y notificaciones; Juan integración entre sesiones. Gate: invitación no es match hasta aceptar, rechazo no filtra contacto.
5. **14:40–15:20 — Verificación local completa.** Luis dispositivo móvil y demo; Jacob regresiones; Juan fallos de micrófono, red y sesión. Congelar funcionalidades nuevas.
6. **15:20–15:30 — Ensayo.** Recorrido de 2 minutos y verificación de repositorio sin secretos/datos personales.
7. **15:30–16:00 — Entrega.** Preparar título, descripción y URL GitHub. Video/post solo si son solicitados; etiquetar patrocinadores únicamente con nombres confirmados y autorización de publicación.

## Gate de producción

**Primero local, después producción.** No desplegar hasta pasar la suite, demostrar dos usuarios, comprobar móviles y disponer de proveedor, cuenta, dominio/HTTPS y almacenamiento persistente acordados. Después del despliegue autorizado, repetir alta, persistencia, matching, invitación, aceptación, rechazo y privacidad en el entorno publicado con cuentas sintéticas. No sustituir estas pruebas por un simple HTTP 200.
