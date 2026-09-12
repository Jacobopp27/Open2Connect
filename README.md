<div align="center">

# Open2Connect

**An AI check-in agent that turns event registration into the moment connections start.**

Built in one day at the AI Tinkerers **Agents, Everywhere** hackathon · Medellín · September 12, 2026

[Live demo](https://open2connect.onrender.com) · [Voice check-in kiosk](https://open2connect.onrender.com/agent) · [Video (46 s)](https://youtu.be/PICCCs5HuuU) · [Submission text](docs/SUBMISSION.md)

</div>

---

## The problem

At a meetup or hackathon nobody knows who they should be talking to. Registration is a dead form, people arrive, sit with the friends they came with and leave without the one conversation they came for. Organizers have no live picture of who is actually in the room.

## What Open2Connect does

| Step | Where | What happens |
| --- | --- | --- |
| **1. Sign up** | Web app (`/`) | You state what you need, what you offer, your interests and the problem you bring. A background agent enriches your profile against a community database and, only with your consent, public information via Exa. |
| **2. Voice check-in** | Kiosk at the door (`/agent`) | A robot face greets you by voice (OpenAI Realtime API). It confirms your name, checks you in and, with permission, looks at the camera once and keeps a short note of how to spot you ("black shirt, green cap"). The image is discarded. It ends by showing a QR to your personal page. |
| **3. Live matching** | Your phone (`/yo/<id>`) | Matches are computed **only among people already checked in**. Complementarity (what you need vs. what someone offers) weighs more than shared interests. Each match comes with a one-line reason, minutes since arrival and how to spot the person. When a relevant person arrives, your phone buzzes: *"your match just arrived"*. A **We met** button closes the loop. |
| **4. Staff view** | Ambiguous AI workspace | The agent, **Mesa 4**, is provisioned as a real member of the organizer's workspace. It creates the CRM contact on sign-up, posts arrivals to the staff channel, fills a sheet of attendees and connections, marks "met" and can assign follow-up tasks. |

Why an agent in this environment beats a chatbot: a standalone chatbot cannot see who is physically in the room, cannot describe how someone is dressed and cannot write into the organizer's tools. Presence, arrival time and appearance are what make a recommendation actionable in the next five minutes instead of after the event.

## Architecture

```mermaid
flowchart LR
  subgraph Venue
    K[Kiosk /agent<br/>robot face · mic · camera]
    P[Attendee phone /yo/id]
    W[Web sign-up /]
  end
  subgraph Server["Python stdlib HTTP server + SQLite (Render)"]
    S[server.py<br/>auth · CSP · rate limits]
    KI[modules/kiosk.py<br/>tools: find · confirm · check-in · recommend · QR · appearance]
    EN[modules/encuentros.py<br/>live matching]
    PF[modules/perfilador.py<br/>community profiling]
    EX[modules/enriquecedor.py<br/>consent-gated Exa]
    AM[modules/ambiguous.py<br/>agent "Mesa 4"]
  end
  O[(OpenAI Realtime<br/>WebRTC · gpt-realtime)]
  V[(OpenAI vision)]
  SB[(Supabase<br/>community schema)]
  XA[(Exa API)]
  AA[(Ambiguous AI<br/>CRM · channel · sheet · tasks)]

  K -- ephemeral token --> S
  K <-- audio + data channel --> O
  O -- function calls --> K -- /api/kiosk/* --> KI
  KI --> V
  KI --> AM --> AA
  W --> S --> PF --> SB
  PF --> EX --> XA
  PF --> AM
  P -- polls /api/yo/estado --> EN
```

**Voice pipeline.** The browser talks to OpenAI Realtime directly over WebRTC; the server only mints ephemeral client secrets and executes tools. Push-to-talk, Spanish input transcription with a name-biased prompt, fuzzy name matching and an explicit name-confirmation step handle noisy rooms. The mic is muted between presses.

**Matching.** Complementarity (needs ↔ offers) weight 3 (+3 if mutual), shared problem 2, shared interests 1. Only checked-in, non-demo profiles are considered.

**Ambiguous AI.** All writes are best-effort background threads so the kiosk never blocks. Without `AMBIGUOUS_AGENT_KEY` the module logs locally and the app keeps working.

**Security baseline.** Same-origin checks (Origin vs. host), `SameSite=Strict` cookies, strict CSP (`connect-src` limited to the app and `api.openai.com`), per-route body limits (2 MB only for the camera frame), rate limits on auth, consent gates for camera and web enrichment.

## Run it locally

Requires Python 3.10+ (standard library only for the core app).

```bash
python3 -m backend.server
```

Open http://127.0.0.1:8000. The database is created at `data/open2connect.db`.

To enable the voice kiosk and integrations, export the variables from [.env.example](.env.example) (at minimum `OPENAI_API_KEY`) before starting:

```bash
set -a; source .env.local; set +a; python3 -m backend.server
```

Optional dependencies for the interview adapter, MCP bridge and Supabase profile store:

```bash
pip install -r requirements-integrations.txt
```

### Demo data

The hosted demo runs on Render's free tier, whose disk is ephemeral: every deploy wipes SQLite. Re-seed four demo attendees (three already checked in) with:

```bash
python3 scripts/seed_demo.py https://open2connect.onrender.com
```

Demo password for the seeded accounts: `PruebaHackaton2026!` (emails end in `@example.invalid`).

### Tests

```bash
python3 -m unittest discover -s tests -v
```

Two adapter tests need optional packages (`psycopg`, `openai`) and are expected to error without them.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Web app: sign-up, profile, discover, connections (ES/EN) |
| `/agent` | On-site voice check-in kiosk with the robot face |
| `/yo/<id>` | Attendee's personal page with live matches and arrival alerts |
| `POST /api/kiosk/{token,buscar,confirmar,checkin,recomendar,qr,apariencia}` | Tools called by the voice agent (optionally protected by `KIOSK_KEY`) |
| `GET /api/yo/estado`, `POST /api/yo/confirmar` | Live matches and "we met" confirmation |
| `GET /api/health` | Health check used by Render and the keep-alive workflow |

## Deploy

`render.yaml` is a Render Blueprint (free plan). Secrets are set in the Render dashboard. See [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md). A GitHub Actions cron ([.github/workflows/keepalive.yml](.github/workflows/keepalive.yml)) pings the health endpoint so the free instance stays warm during the event.

## Repository map

```
backend/            stdlib HTTP server, SQLite, modules and adapters
  modules/kiosk.py        voice agent tools and Realtime token
  modules/encuentros.py   live matching and personal page API
  modules/perfilador.py   community profiling (Supabase)
  modules/enriquecedor.py consent-gated public enrichment (Exa)
  modules/ambiguous.py    Ambiguous AI agent "Mesa 4"
frontend/           vanilla JS: app, agent (robot face), personal page, realtime.js client
db/                 SQL seed with 40 fictional community profiles
scripts/            ambiguous_setup.py (provision agent, sheet, channel) · seed_demo.py
video/              HyperFrames project for the demo video
docs/               deployment, kiosk, realtime client, submission, video script
```

More docs: [docs/KIOSK.md](docs/KIOSK.md) · [docs/REALTIME_FRONT.md](docs/REALTIME_FRONT.md) · [docs/WEB_APP_ES.md](docs/WEB_APP_ES.md) (original web-app guide, Spanish) · [docs/team-notes/](docs/team-notes/)

## What is real and what is simulated

- The community database is **fictional** (40 generated profiles). We did not scrape the AI Tinkerers platform, following its rules.
- Web enrichment via Exa runs only with explicit consent and one person at a time.
- Proximity alerts between phones (Bluetooth) are on the roadmap, not implemented.

## Team

- **Jacobo Posada** ([@Jacobopp27](https://github.com/Jacobopp27)) — architecture, voice check-in agent, matching, Ambiguous AI integration, profiling and enrichment, deployment, video
- **Juan Fernando Villa** ([@juanfdovilla](https://github.com/juanfdovilla)) — community data exploration, AI Tinkerers API cross-search, profiling inputs and on-site testing
- **Luis Miguel Saldarriaga** — web application (sign-up, profiles, discovery, connections), interview adapter, MCP bridge, Supabase store and tests

Sponsors and tools we used: OpenAI (Realtime API, vision), Ambiguous AI, Exa, Supabase, Render.

## License

[MIT](LICENSE)
