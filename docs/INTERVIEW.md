# Voice interview, factual notes, API, MCP and Supabase

## Start locally

The guided interview works without external services:

```sh
python3 -m backend.server
```

Open the app, create/sign in to your own account and choose **Entrevista / Interview**. Select **Guía local**, then **Iniciar entrevista**. Respond by voice or text to one question at a time. Voice uses browser speech recognition and speech synthesis; start/end events come from the browser, not a custom acoustic VAD. The text alternative remains available.

- **Responder con voz** cancels spoken playback before opening the mic. **Terminé de hablar** ends capture. Final transcripts can be sent automatically to the draft; uncheck the automatic-send option to edit first.
- **Pausar entrevista** stops microphone/playback and pauses server state; **Continuar entrevista** resumes. Interrupted audio does not auto-submit.
- Notes show their source and exact quote. Correct any field in the notes form. “Ninguna ahora” allows a participant to need help, offer help, both, or neither. No fabricated filler is required.
- **Preparar resumen para confirmar** validates the editable profile and creates a versioned review token. **Confirmo este resumen y guardo** persists it. Corrections invalidate the token. A stale or missing token cannot save.
- Unconfirmed interview drafts and quote evidence exist only in server memory for two hours and are discarded after restart. A page reload starts a fresh interview from the last confirmed profile. Raw audio is never saved by the app. Confirmed persistence contains profile fields, not interview recordings/transcripts. Browser/provider processing is separate.

## Actual AI adapter

Install optional SDKs in a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-integrations.lock.txt
```

Set `OPENAI_API_KEY` and `OPENAI_MODEL` privately in the server environment, then start the server with `.venv/bin/python -m backend.server`. `.env` files are not auto-loaded. Choose a model that supports Responses Structured Outputs and that your API project can access. No key is bundled; model choice is explicit.

The OpenAI mode is enabled only when configuration and the SDK are present. The participant must opt in to sending interview answers/notes before starting this mode. The adapter calls the real Responses API with a strict JSON schema, `store=False`, a bounded timeout and no automatic retries. It sends current profile facts excluding stored contact, the current question and the participant's answer. Never include credentials/private contact in the spoken answer. API account data-retention policy still applies; `store=False` is not a universal zero-retention guarantee.

The runtime prompt lives in `backend/adapters/interview_ai.py`, separate from the Codex skill. Model notes require verbatim evidence in the current answer; textual values must be present in the evidence. Enum normalization is limited to needs/offers, availability and priority. Invalid output leaves the draft unchanged. The participant remains the final authority before save.

**Current validation:** no API credentials were available during implementation; the live OpenAI call has not been exercised. Tests use an injected model/transport response and explicitly test invalid/fabricated notes. The local guide is a functional non-LLM alternative, not proof of model connectivity.

## API contract

Cookie authentication is required. Every write has JSON content type and `X-Open2Connect: 1`. User IDs are derived from the session. `event` is a query parameter only on start/profile; a draft binds its event and owner server-side.

| Operation | Endpoint | Body |
| --- | --- | --- |
| Start | POST `/api/interviews/start?event=medellin-2026` | `locale`, `mode: guided/openai`, `ai_consent` |
| Turn | POST `/api/interviews/turn` | `id`, `revision`, `text` |
| Get own draft | GET `/api/interviews/draft?id=...` | — |
| Pause/resume/fallback/discard | POST `/api/interviews/control` | `id`, `revision`, `action: pause/resume/guided/discard` |
| Edit draft without saving | POST `/api/interviews/edit` | `id`, `revision`, edited `profile` (web session only) |
| Prepare summary | POST `/api/interviews/summary` | `id`, `revision`, optional edited `profile` |
| Confirm | POST `/api/interviews/confirm` | `id`, current `revision`, `review_token`, `confirmed: true` |

400 means invalid input or missing explicit confirmation; 401 session/token expired; 404 draft inaccessible/expired; 409 revision/state conflict; 502 model failure; 503 missing integration/configuration or storage failure. No profile write occurs on interview turn or summary.

## MCP: real local bridge

`backend/mcp_server.py` uses MCP Python SDK 2.2.0, stdio transport. It forwards only bounded operations to the running app API, with backend authorization on every call. The bridge does not connect directly to SQLite/Supabase, mint credentials, execute SQL or list other users.

In **Entrevista → Conectar mi entrevista a MCP**, generate a private one-hour token. Configure `OPEN2CONNECT_MCP_TOKEN` in the local MCP process environment using your client's private secret mechanism. Do not paste it into an agent prompt or commit it. The token is bound to your user, event and login session. **Revocar mis tokens MCP**, expiry or signing out invalidates it.

Run from the project root:

```sh
.venv/bin/python -m backend.mcp_server
```

Client stdio configuration uses the absolute path to `.venv/bin/python`, arguments `-m backend.mcp_server`, the project root as working directory, and these environment variables:

```text
OPEN2CONNECT_APP_URL=http://127.0.0.1:8000
OPEN2CONNECT_MCP_TOKEN=<privately configured one-hour token>
```

Tools: `start_interview`, `process_interview_turn`, `get_own_interview`, `prepare_interview_summary`, `confirm_interview_profile`, `control_interview`, `get_own_profile`. The client must show the current summary and get explicit confirmation before invoking confirm. The backend independently requires the current review token/revision. No arbitrary profile/owner identifiers are tool parameters.

This is a local stdio integration, not a publicly hosted OAuth MCP service. We did not change any user's Codex/client configuration. The SDK protocol is tested in-memory against the real HTTP backend; cloud/provider calls remain separate.

## Supabase connection and ownership

`PROFILE_STORE=sqlite` is the default. For an approved Supabase project, set:

```text
PROFILE_STORE=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=<server-only secret key>
```

The legacy `SUPABASE_SERVICE_ROLE_KEY` is also accepted. Before selecting Supabase, review/apply `supabase/migrations/202609120001_profiles.sql` to the explicitly chosen project using an authorized administrative connection. No migration runs at app startup. Test access with `supabase/tests/profiles_rls.sql` on an authorized test project; the script rolls back its synthetic record.

The selected repository is the source of truth for confirmed profiles in profile reads, matching and connections. Supabase writes general+event profiles atomically through `o2c_save_profile`; on failure the API returns 503, never a success or a hidden SQLite write. Existing SQLite data is not uploaded. Static demo seeding is intentionally disabled in Supabase mode.

**Auth design:** app account IDs and sessions remain in the private SQLite identity database of a single deployment, along with event registry, invitations, blocks and notifications. Supabase stores only the confirmed profile fields keyed by that app-owned ID. It does not use Supabase Auth. Preserve this identity DB and its backup when operating in Supabase mode; sharing one Supabase project across unrelated identity databases is unsupported. Switching the profile provider reveals that provider's profiles, not a merged view.

**RLS boundary:** anon/authenticated grants are revoked and restrictive deny policies prohibit direct browser/Supabase-Auth access. The server secret/service role bypasses RLS. Ownership is checked by the Python API before repository operations; **RLS does not protect service-role operations**. Never ship the server key to a browser, MCP tool arguments or another client. For future direct-client access, migrate auth to Supabase Auth or a supported trusted JWT provider and implement user policies first.

No Supabase project/credentials were configured and no remote migration, connection test or data write was performed. The adapter path, transaction payload and failure behavior are tested with a test double; SQL tests are supplied but have not run against PostgreSQL.

## Verification

```sh
.venv/bin/python -m unittest discover -s tests -v
node --test tests/speech.test.cjs
python3 /path/to/skill-creator/scripts/quick_validate.py .agents/skills/voice-profile-interview
```

Includes prior matching/connections regressions, interview correction/absence/revision/confirmation/ownership, model validation, provider failures, MCP token revocation and real SDK protocol calls to the app. Speech tests inject browser APIs: they do not prove microphone permission or device accuracy. Test the real microphone on the intended browser/mobile before a live presentation.

Official references used for implementation: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [MCP Python server transports](https://py.sdk.modelcontextprotocol.io/run/), [MCP SDK testing](https://py.sdk.modelcontextprotocol.io/get-started/testing/), [Supabase Python client](https://supabase.com/docs/reference/python/initializing), [Supabase RLS and grants](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Browser verification recorded for this increment

In an isolated local SQLite instance and synthetic account, Chrome verified: registration, first/second interview questions, factual notes, pause, manual correction, explicit no-needs/no-offers, review, confirmation and persisted corrected profile after reload. English interface and disabled OpenAI state were also inspected. Physical microphone input and mobile hardware were not tested. The browser state was not used as evidence of a live OpenAI or Supabase connection.
