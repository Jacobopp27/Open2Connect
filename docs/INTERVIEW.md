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

## Intelligent continuous voice (Realtime increment)

Select **Voz inteligente · conversación continua**. This uses OpenAI Realtime over
WebRTC, a generated `marin` voice and semantic VAD (`eagerness=low`). The participant
can interrupt speech. The browser sends an SDP offer to the authenticated,
CSRF-protected `POST /api/interviews/voice`; the Python server exchanges it using
`/v1/realtime/calls`. Neither a standard nor an ephemeral API key is returned to
the browser. Audio travels directly between the browser and OpenAI.

The session uses `gpt-realtime-2.1` by default (override `OPENAI_REALTIME_MODEL`).
Input transcription uses `gpt-4o-mini-transcribe`. Each completed transcript is
processed by the existing Responses structured extractor (`OPENAI_MODEL`, suggested
`gpt-4.1-mini`). Then Realtime speaks an acknowledgment and the next adaptive
question. Automatic Realtime responses are disabled to keep questions in sync
with validated notes. This adds extraction latency compared with a pure
speech-to-speech loop; this is a custom interview, not ChatGPT's voice product.

Committed item order determines extraction order, even if transcription completes
out of order. Per-turn IDs make HTTP retries idempotent. Failed extraction retains
the pending text in browser memory and pauses capture for retry. A separate,
explicit discard control lets the participant abandon a pending reply and repeat
it or type. Notes remain drafts; the voice model has no save or connection tools.
Manual note editing requires stopping voice. Stop/pause/review drains received
turns before closing media. Leaving the page immediately closes the microphone;
a very recent, untranscribed utterance may need to be repeated. Permission failures,
provider errors and blocked audio playback have visible recovery controls.

### Local activation

In ignored `.env`, configure `OPENAI_API_KEY` privately. Use `OPENAI_MODEL=gpt-4.1-mini`
and `OPENAI_REALTIME_MODEL=gpt-realtime-2.1`, or models supported by your API project.
Run `.venv/bin/python -m backend.local`; this explicit launcher reads literal
`NAME=value` entries without shell execution or variable interpolation. Existing
exported environment variables take precedence. Restart after editing `.env`.
API credentials/access/billing are separate from the application's login.

Voice consent covers sending audio, responses and interview facts to OpenAI.
Raw audio is not recorded by the app; provider data policies still apply. The UI
closes a voice connection after 15 minutes; this is a client lifecycle guard,
not a server-enforced spending quota. Session exchange is limited to 3 attempts
per minute per draft. Review provider/project usage controls before public rollout.
Supabase configuration and SQLite storage are unchanged by voice activation.

Verification: Python HTTP tests cover consent, scoping, CSRF, rate limiting,
transcript idempotence, evidence validation, provider error redaction, and SDP
configuration through an injected transport. Node tests cover transcript ordering,
retry, delayed microphone permission cleanup and final-turn draining. These are
not live OpenAI, actual microphone or network-quality tests. At implementation time
`OPENAI_API_KEY` was absent, so live voice remains pending activation and device QA.

References: [Realtime](https://developers.openai.com/api/docs/guides/realtime),
[WebRTC](https://developers.openai.com/api/docs/guides/voice-webrtc?api=realtime),
[semantic VAD](https://developers.openai.com/api/docs/guides/realtime-vad).

### PostgreSQL connection diagnostic

Run `.venv/bin/python -m backend.check_database` to load the ignored `.env` and
verify `SUPABASE_DB_URL` using the public CA in `supabase/certs`. It checks TLS,
read-only transaction state and existence of the two expected profile tables;
it does not read participant rows, create tables or migrate data. Error messages
omit the URL and credentials. PostgreSQL diagnostics require Psycopg 3.

On 2026-09-12 the supplied pooler reached password authentication with full TLS
verification after installing the official Supabase CA. Authentication failed;
clarification of the backslash in the supplied password was requested. No remote
schema or data was changed. `PROFILE_STORE` remains `sqlite`. The current
`supabase` application adapter uses its server API key; a PostgreSQL URL by itself
does not activate that adapter.


### Supabase PostgreSQL configured — 2026-09-12

The corrected credentials were verified with `sslmode=verify-full` and the official
CA. Migration `202609120001_profiles.sql` was applied to project
`yjloegnuyjziagppvdif`, creating the two profile tables and atomic save function.
Live tests verified reading/writing, owner/event predicates, atomic failure rollback,
RLS enabled and denied anon/authenticated grants. Synthetic records were rolled back.
The diagnostic now confirms both tables and `transaction_read_only=on`; transaction
mode is set explicitly because startup `options` were not sufficient through the pooler.

`PROFILE_STORE=postgres` selects `backend/adapters/postgres_profiles.py`, using
`SUPABASE_DB_URL` and `SUPABASE_DB_CA`. No Supabase HTTP API key is required for this
provider. The URL is stored only in ignored `.env` (0600). The database account is
privileged: application authorization scopes access; RLS is not owner enforcement
for this account. No credential is sent to the browser.

Only profiles move to this storage provider. Accounts, sessions, events and connections
continue in the existing local SQLite database. No existing local profiles have been
copied; switching providers shows the selected provider's profiles. Keep the original
identity database, and do not use unrelated identity databases with this cloud store.

Private configuration is prepared for the next `.venv/bin/python -m backend.local`
start. Existing running servers still use their previous configuration. Restarting
the main instance was previously blocked by automatic review because of unsaved
in-memory interview drafts and awaits explicit user authorization.

Validation: 38 Python tests passed, plus the live rollback checks above. The prior
missing-certificate/password notes describe earlier diagnostic attempts, not the
current connection status.
