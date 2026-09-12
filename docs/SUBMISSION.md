# Open2Connect — textos para el formulario de AI Tinkerers (Agents, Everywhere · Medellín 2026)

## Project Name
Open2Connect

## Project Description (pegar tal cual; markdown permitido)

**Open2Connect turns event check-in into the moment connections start.**

**The problem.** At a meetup or hackathon nobody knows who they should be talking to. Registration is a dead form, people arrive, sit with friends and leave without the one conversation they came for. Organizers have no live picture of who is in the room.

**The environment.** The agent, "Mesa 4", lives in three places at once, and each one shapes what it does:

1. **The welcome desk (physical).** A kiosk with a simple robot face greets each arrival by voice using the **OpenAI Realtime API** (WebRTC, `gpt-realtime`, Spanish). It confirms the name, performs the check-in and, with permission, looks at the camera once and records a short *seña* ("black shirt, green cap") so other attendees can find that person in the room. The image is discarded; only the text stays. It ends by showing a QR to the attendee's personal page.
2. **The attendee's phone.** Each person gets a personal page with live matches computed **only among people who have already checked in**. Matching weights complementarity (what you need vs. what someone else offers) above shared interests, and every match comes with a one-line reason, minutes since arrival and how the person is dressed. When a relevant person arrives, the phone vibrates: *"your match just arrived"*. A "we met" button closes the loop.
3. **The organizer's workspace: Ambiguous AI.** Mesa 4 is provisioned as a real member of the organizer's Ambiguous AI workspace. On registration it creates the CRM contact; on arrival it posts to the staff channel, updates a shared sheet of attendees and connections, marks "met" and can assign follow-up tasks to organizers. Staff see the event live without opening a new tool.

**Why an agent here beats a chatbot.** A standalone chatbot cannot see who is physically in the room, cannot describe how someone is dressed, and cannot write into the organizer's CRM. The context (arrival time, presence, appearance, the community's profile data) is what makes the recommendation actionable in the next five minutes, not after the event.

**Profiling.** On registration the attendee states needs, offers, interests and the problem they bring. A background agent enriches the profile against a community database (simulated AI Tinkerers-style members in Supabase; we did not scrape the AI Tinkerers platform, per its rules) and, only with explicit consent, with public information via the **Exa** API.

**Technical execution.** Python standard-library HTTP server + SQLite (deployed on Render), vanilla JS front end. OpenAI Realtime via WebRTC with ephemeral client secrets, push-to-talk, server-side function calling (`buscar_persona`, `hacer_checkin`, `recomendar`, `describir_apariencia`, `mostrar_qr_registro`), input transcription with a name-biased prompt and fuzzy name matching for noisy rooms. Vision model for the appearance note. Ambiguous AI REST API (provision-agent, CRM contacts, channels, sheets, tasks, docs) with best-effort background writes so the kiosk never blocks. Supabase (community schema) and Exa for enrichment. Security: same-origin checks, CSP, per-route body limits, consent gates for web enrichment and camera.

**Built during the hackathon:** everything above. Live demo: https://open2connect.onrender.com · Code: https://github.com/Jacobopp27/Open2Connect

## Prior Work (if applicable)
All code was written during the hackathon (Sept 12, 2026). We started from an empty repository. We relied only on public SDKs/APIs (OpenAI Realtime, Ambiguous AI REST, Supabase, Exa) and a set of fictional community profiles we generated for the demo. No prior codebase, designs or datasets were reused.

## Links
- Live demo: https://open2connect.onrender.com
- Voice check-in kiosk: https://open2connect.onrender.com/agent
- Repo: https://github.com/Jacobopp27/Open2Connect
- Video: (pegar link cuando esté subido)

## Post para redes (LinkedIn · español, con nombres de empresa)

Hoy en el hackathon Agents, Everywhere de AI Tinkerers en Medellín construimos **Open2Connect**: un agente que convierte el check-in de un evento en el inicio de las conexiones.

🤖 Un robot te recibe hablando (OpenAI Realtime), confirma tu nombre, hace tu check-in y anota cómo vas vestido para que te encuentren.
📱 Tu celular vibra cuando llega alguien que te sirve: "tu match acaba de llegar, camisa negra, por la entrada". Solo entre gente que ya está en la sala.
🗂️ El agente vive en el workspace del staff en Ambiguous AI: crea contactos, avisa quién llegó y registra cada conexión.

Equipo: Jacobo Posada, Juan F. Villa y Luis Salda.
Demo: https://open2connect.onrender.com

Gracias AI Tinkerers, OpenAI, Ambiguous AI, Exa, CopilotKit, OpenRouter, Auth0, Trigger.dev, Mozilla.ai y Google Cloud.
#AgentsEverywhere

## Post para X (≤ 280 caracteres)
Construimos Open2Connect en el hackathon de @AITinkerers Medellín: un robot te recibe por voz (@OpenAI Realtime), hace tu check-in y tu celular vibra cuando llega tu match. El staff lo ve todo en @ambiguousio. Con @exaailabs. #AgentsEverywhere
https://open2connect.onrender.com
