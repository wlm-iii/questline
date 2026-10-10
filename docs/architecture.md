# Backend architecture and alignment status

[Product spec](SPEC.md) defines the target. This document describes the current implementation,
not a claim that all Build features are finished.

## Current flow

```text
Create / join trip → member token
          ↓
Structured transcript batch → FastAPI → private questline PostgreSQL schema
          ↓
Request-time snapshot + durable job (same transaction)
          ↓
Procrastinate worker → deterministic fake planner → new draft plan
          ↓
Trip-state polling → accept, or service-only revision-checked replacement
```

The API and worker normally run as separate processes. `RUN_WORKER_IN_PROCESS=true` runs the same
queue worker in FastAPI's lifespan for single-process demo hosting; it does not replace durable
jobs with FastAPI BackgroundTasks. Migrations and queue setup must run before either deployment.

| Path | Responsibility |
| --- | --- |
| `backend/src/questline/api/` | HTTP contracts, validation, access gate, status codes |
| `backend/src/questline/schemas.py` | Shared request, transcript, and graph schemas |
| `backend/src/questline/models.py` | PostgreSQL persistence |
| `backend/src/questline/services/` | Planning orchestration independent of HTTP |
| `backend/src/questline/jobs.py` | Queue wiring, worker entrypoint, queue schema bootstrap |
| `backend/src/questline/providers/` | AI and Maps boundaries; deterministic mock planner |
| `backend/src/questline/integrations/` | Chat platform adapters; `imessage/` is the iMessage relay (SPEC §11.1) |
| `backend/migrations/` | Versioned application schema migrations |

## Implemented contracts

All application routes are under `/api/v1`. Health endpoints also have root aliases for existing
hosting probes. JSON fields are snake_case. `/docs` and `/openapi.json` describe current payloads.

| Method | Path | Access / behavior |
| --- | --- | --- |
| POST | `/trips` | Public; resolves fixture endpoints, creates organizer, returns `{trip, member, member_token}` |
| POST | `/trips/{id}/members` | Public link-based join; returns `{member, member_token}` |
| GET | `/trips/{id}?revision=N` | Member/service; current trip state, or `{unchanged: true, revision}` |
| POST | `/trips/{id}/messages/batch` | Member/service; append-only deduplication, `{inserted, revision}` |
| POST | `/trips/{id}/plan-generations` | Member/service; `{budget_preset}` and `Idempotency-Key`, returns 202 `{generation}` |
| GET | `/plan-generations/{id}` | Member/service; `{generation}` with eventual `plan_id` |
| GET | `/plans/{id}` | Member/service; `{plan}` |
| PATCH | `/plans/{id}` | **Service only**; replace `{revision, content}`, returns `{plan}` |
| POST | `/plans/{id}/accept` | Member/service; expected revision, returns `{plan}` |
| GET | `/health/live`, `/health/ready` | Public; `{ok: true}`; readiness checks DB connectivity only |

Errors use `{error: {code, message}}`; conflict errors may also include `generation_id` inside
`error`. Invalid requests return 422 without echoing potentially sensitive input.

### Access and state

- Create/join returns a random member token once. Only its SHA-256 hash is persisted.
- Browsers send `X-Member-Token`; token membership gates each trip/resource lookup.
- Cross-trip references return 422. The global `API_TOKEN` remains for tooling and bots only.
- Link-based joining is public by design. This is not private/account-based authentication.
- All implemented state-changing writes lock the trip and bump its revision, including job status,
  accepted plans, and edits. Identical message redelivery does not bump revision.
- Trip-state reads hold a shared trip lock so the revision and returned state are consistent.
- Full-content replacement is not a browser editor API. `/operations` and recomputation are pending.

### Jobs

- Snapshots are captured **at request time**, not job start. They contain messages, members, preset,
  timezone, and reserved `places`/`votes` lists. These lists are currently empty because waypoint and
  vote persistence are not implemented; never describe them as a completed candidate pipeline.
- Generation rows and queued jobs commit atomically on the same psycopg connection.
- Conversation rows are now trips. Existing rows, messages, and plans migrate without deletion.
- Per-trip queue locks serialize work. The trip row lock ensures requests find an active build:
  same preset returns it, different preset returns `409 plan_in_progress`.
- Successful output is a **draft** plan, saved atomically with `current_plan_id` and the preset.
- Failure leaves the previous successful plan/preset unchanged. Errors are sanitized.
- Completed task replay does not overwrite edited plans. Each new generation creates a new plan.
- Stalled-job recovery/timeouts and a partial unique active-job index remain Harden work.

## Provider and graph boundaries

`Planner.generate(snapshot, request)` receives the complete immutable request snapshot.
The fake planner intentionally returns an empty, clearly labeled draft, not invented resolved places.
`FakeMaps` resolves only `San Jose, CA` and `Big Sur, CA`, using explicitly labeled fixture data.
These are development fixtures, not Google-verified results.

`PLANNER_PROVIDER=fake|gemini`, `MAPS_PROVIDER=fake|google`, and `GEMINI_MODEL` are recognized.
Real provider adapters are not implemented: selecting them returns a clear 503 on relevant requests,
rather than silently falling back to fake output. Gemini/Maps credentials remain server-side.

Plan schemas accept main/side roles, anchors, coordinates, travel/detour edges, polylines, days,
prices, conflicts, estimates, warnings, and change summaries. Basic graph references, cost ranges,
and timestamps are checked. Full route feasibility and derived-field recomputation are **not** done.

## Remaining Build work

- Places/votes/imports/tasks/check-ins tables, endpoints, and populated trip-state collections.
- Pasted-chat parsing, extraction, FakeExtractor, and Gemini/Google adapters.
- Planner selection contract `{main, side, why}` and code-owned routing/timing/estimate calculations.
- `/operations` validation and recompute; grounded `/resolutions`.
- API-driven seed script and demo chat (the smoke script tests only this foundation).
- Frontend map, creation/join, polling, votes, editor, and quest log; the frontend is still Vite's starter.
- iMessage relay and service-only channel/reaction endpoints.
- Frontend deployment and deployment manifests; actual Supabase/hosting resources are not created.

Divide these by the four roles in SPEC §12. Extend schemas and migrations deliberately; tests
should use fake providers and never consume real Gemini/Maps quota.

## Security boundaries

Keep the `questline` schema out of Supabase's exposed API schemas. Never ship the service token or
DB credentials in the browser. Use synthetic data until consent, transcript deletion/retention,
Google attribution/storage policies, and deployment controls are implemented. Imported messages
are untrusted input and must not grant AI permissions to book, pay, execute tools, or access other trips.
