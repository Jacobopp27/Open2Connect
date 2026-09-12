---
name: voice-profile-interview
description: Build or extend a voice-first participant interview in Open2Connect, including speech detection, factual notes, scoped API/MCP operations and optional Supabase persistence. Use for runtime interview development or a participant interview through the configured app MCP tools; not for musical note detection or a transcript-only task.
---

# Voice profile interview

This project skill describes the development and operating workflow. It does not run inside the web application. Runtime behavior belongs to the interview module, voice adapter and model prompt.

## Work in the existing app

Read `docs/INTERVIEW.md` from the project root for current routes, storage boundaries, configuration and verification commands. Preserve the JavaScript frontend, Python modules, event-scoped needs/offers, matching filters and contact consent.

- Use `backend/modules/interviews.py` for interview state; keep one natural question at a time, follow up on uncertainty, and support explicit corrections and absence of needs/offers.
- Use `frontend/speech.js` for browser speech start/end events, interruption, pause/resume, read-aloud and recoverable failures. Always retain written answers as an alternative. Do not describe speech-event detection as a custom acoustic VAD.
- “Note detection” means factual structured extraction. Keep evidence in the current utterance, show editable notes, and do not fill missing facts by inference. Confirm the current reviewed revision before saving.
- A model-backed adapter must use its actual configured service and report failures truthfully. The local guide is functional but is not an LLM. Check credential presence without printing values. Never add API keys to browser bundles.
- Keep drafts and quote evidence transient unless the user explicitly requests different retention. Persist only the confirmed profile to the selected repository; never silently fall back to a different DB after a Supabase failure.

## API and MCP

For MCP operation, use the actual app bridge's bounded tools, bound to a short-lived participant/event token. Derive identity server-side. Do not accept arbitrary user IDs, SQL, service-role keys or cross-event access from tool arguments. Present the summary before calling confirmation with the exact current revision and review token.

For implementation, use the installed maintained MCP SDK and test protocol calls plus backend authorization. Adding a tool declaration alone is not a working integration. Keep MCP stdio local unless a separately authorized authenticated deployment is requested.

## Supabase boundary

The current app keeps authentication in SQLite and uses a server-only Supabase adapter for confirmed general/event profiles. The app checks ownership; service-role access bypasses RLS. Direct anon/authenticated client access is denied by grants and restrictive policies. Do not claim `auth.uid()` protects this service-role design.

A Supabase project and server credential must be explicitly configured. Prepare migrations locally; identify the actual target and authorization before applying them. Do not migrate local sessions or participant data automatically. Preserve SQLite as a deliberate configuration option.

## Verify and report

Run focused tests for revisions/corrections, absence of needs/offers, no-save-before-confirm, user/event isolation, provider failures, speech events and MCP protocol calls. Re-run existing matching/connections tests after repository changes. Run SQL access tests only on an authorized test DB. Distinguish live service checks from injected test doubles and unavailable credentials. Report remaining blockers with exact configuration names, not requests to paste secrets in chat.
