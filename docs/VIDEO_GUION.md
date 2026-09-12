# Open2Connect — contexto y guion del video (45 s, horizontal 1920×1080)

## Contexto en una página (para quien edite el video o lo narre)

**Evento:** AI Tinkerers Medellín, hackathon "Agents, Everywhere" (12 sep 2026, con OpenAI). Equipo: Jacobo Posada, Juan F. Villa, Luis Salda.
**Repo:** https://github.com/Jacobopp27/Open2Connect · **Demo:** https://open2connect.onrender.com

**Problema:** en un evento de networking nadie sabe con quién le conviene hablar. El registro es un formulario muerto, la gente llega, se sienta con conocidos y se va sin la conexión que buscaba.

**Qué es Open2Connect:** un agente de bienvenida que convierte el check-in en el inicio de las conexiones.

1. **Registro web (`/`)**: la persona crea su perfil: qué necesita, qué ofrece, intereses, problema que trae. Al guardar, un agente ("Mesa 4") la perfila cruzando una base de comunidad (simulada, tipo AI Tinkerers, en Supabase) y, con consentimiento, información pública vía Exa.
2. **Check-in por voz (`/agent`)**: un kiosco con una cara de robot blanca habla con OpenAI Realtime (voz a voz, español). Confirma el nombre, hace el check-in, y con permiso mira la cámara y anota una **seña** ("camisa negra, gorra verde") para que otros la encuentren en la sala.
3. **Matching en vivo**: solo entre personas que **ya llegaron**. Complementariedad (lo que uno necesita vs. lo que otro ofrece) pesa más que afinidad. Cada match trae una razón en una línea, hace cuánto llegó y cómo está vestido.
4. **Página personal (`/yo/<id>`)**: se abre desde el QR que muestra el robot al final del check-in. Cuando llega alguien que te sirve, el celular vibra y suena: "tu match acaba de llegar". Botón "Ya nos conocimos" cierra el ciclo.
5. **Ambiguous AI (el workspace del staff)**: el agente Mesa 4 es un miembro del workspace. Crea el contacto en el CRM al registrarse, escribe en el canal del staff cuando alguien llega, llena una hoja de asistentes y conexiones, y marca "se conocieron". Los organizadores ven el evento vivo sin abrir ninguna herramienta nueva.

**Stack:** Python stdlib + SQLite (Render free), vanilla JS, OpenAI Realtime (WebRTC, gpt-realtime, voz marin), visión para la seña, Supabase (comunidad), Exa (enriquecimiento público), Ambiguous AI REST.

**Claims que NO se pueden hacer en el video:** que scrapeamos AI Tinkerers (descartado por sus reglas), que hay datos reales de asistentes (son ficticios), que la proximidad Bluetooth existe (es roadmap), que hay pagos o clientes.

**Categorías a las que apunta:** Best Use of Ambiguous AI + agente conversacional con OpenAI Realtime.

## Guion global (45 s, voz en off en español, ritmo rápido)

| # | t (s) | Escena (pantalla) | Voz en off | Texto en pantalla |
|---|-------|-------------------|-----------|-------------------|
| 1 | 0–5 | Fondo oscuro, logo/título aparece. Una sala llena de gente vista como puntos que no se conectan. | "En un evento hay cien personas. ¿Con cuál te conviene hablar? Nadie lo sabe." | **Open2Connect** — *Llega. Habla. Conecta.* |
| 2 | 5–12 | Captura de `/` (registro). Campos de "qué necesito / qué ofrezco" se resaltan. | "Te registras una sola vez: qué necesitas y qué ofreces. Un agente te perfila con la comunidad y, si aceptas, con tu huella pública." | Registro → perfil vivo |
| 3 | 12–22 | Captura de `/agent`: cara de robot blanca, boca moviéndose. Burbujas de transcripción: "Hola, ¿cómo te llamas?" / "Jacobo" / "Listo, Jacobo, ya quedaste. ¿Me dejas ver cómo estás vestido?" | "Al llegar, un robot te da la bienvenida con voz. Confirma tu nombre, hace tu check-in y, con tu permiso, anota tu seña: camisa negra, gorra verde." | Check-in por voz · OpenAI Realtime · seña visual |
| 4 | 22–31 | Captura de `/yo/<id>` en un celular: banner "Tu match acaba de llegar", tarjeta con razón + "llegó hace 3 min · camisa negra". | "Y cuando llega alguien que te sirve, tu celular vibra: 'tu match acaba de llegar, viste camisa negra, está por la entrada'. Solo entre gente que ya está en la sala." | Match en vivo · complementariedad > afinidad |
| 5 | 31–40 | Captura del workspace de Ambiguous: CRM con contacto, canal del staff con "Llegó Jacobo…", hoja de conexiones. | "Todo lo ve el staff en Ambiguous AI: el agente Mesa 4 es un miembro más. Crea contactos, avisa quién llegó y registra cada conexión." | Mesa 4 vive en Ambiguous AI |
| 6 | 40–45 | Logo, URL, nombres del equipo, logos de OpenAI Realtime / Ambiguous AI / Supabase / Exa como texto. | "Open2Connect. Llega, habla, conecta." | open2connect.onrender.com · Jacobo · Juan F. · Luis |

**Música:** electrónica suave, sin voz, sube en la escena 4.
**Assets necesarios:** capturas 1920×1080 de `/`, `/agent`, `/yo/<id>` y del workspace de Ambiguous (CRM, canal, hoja). Opcional: clip real de 5 s del robot hablando en el kiosco.
