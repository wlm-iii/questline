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
- Full-content replacement is not a browser editor API. Browsers use `/operations`, which recomputes
  derived fields before taking the trip lock and rechecks the revision under it.

### Jobs

- Snapshots are captured **at request time**, not job start. They include actual persisted messages,
  members, places, votes, preset, timezone, trip context, previous plan, and lookup limits. Subsequent
  edits never mutate a snapshot. Discovery is a separate private provider-facts overlay with no
  later group votes/evidence, even when its local ID collides with a waypoint added after enqueue.
- Generation rows and queued jobs commit atomically on the same psycopg connection.
- Conversation rows are now trips. Existing rows, messages, and plans migrate without deletion.
- Per-trip queue locks serialize work. The trip row lock ensures requests find an active build:
  same preset returns it, different preset returns `409 plan_in_progress`.
- Successful output is a **draft** plan, saved atomically with `current_plan_id` and the preset.
- Failure leaves the previous successful plan/preset unchanged. Errors are sanitized.
- Completed task replay does not overwrite edited plans. Each new generation creates a new plan.
- A periodic task (every minute) requeues jobs whose worker missed heartbeats for 30 seconds, so a
  killed or restarted worker doesn't strand a trip's queue lock. A build still queued or running
  after 5 minutes is failed when a new one is requested, and failed builds never save a plan.
  The in-process worker restarts itself after a crash. A partial unique active-job index remains
  Harden work.

## Provider and graph boundaries

`Planner.generate(snapshot, request)` receives the complete immutable request snapshot.
It also carries the plan that was current at request time (`previous_plan`) so changes can be
reported. The fake planner is the same code-owned builder with vote-based picks and straight-line
drive estimates; it never invents places, prices, or hours.
`FakeMaps` resolves endpoints `San Jose, CA` / `Big Sur, CA` and waypoint fixtures `McWay Falls` /
`Big Sur Bakery`. `FakeExtractor` recognizes those waypoint names plus unresolved `Mystery Cafe`.
These are explicitly labeled development fixtures, not Google-verified results.

`PLANNER_PROVIDER=fake|gemini`, `MAPS_PROVIDER=fake|google`, and `GEMINI_MODEL` are recognized.
Google Places (New) Text Search is implemented for trip endpoints and manually added waypoints.
It uses an explicit field mask, a 10-second HTTP timeout with a 12-second total deadline,
no automatic retries, and sanitized 503
errors. Missing keys fail explicitly; selecting Google never falls back to fake output. Build
uses the top result and displays its resolved label; callers should include city/region. Category
is a coarse mapping of place types; waypoint `priceLevel` maps to disclosed app estimates, not
menu/admission quotes. Endpoint masks omit prices; opening hours remain unknown. Imports resolve mentions
with a padded trip bounding-box bias and reject out-of-region or implausible name matches.
Unresolved mentions remain visible; the matcher is conservative, not a guarantee of unique identity.
Gemini extraction uses `google-genai` structured output, constrained message IDs, exact source
substrings, a 30-second deadline, and no automatic retries. It never infers votes. The extraction
pipeline has a 120-second overall deadline. `PLANNER_PROVIDER=gemini` selects it, requiring a key
and explicit model. Gemini also picks main/side membership and candidate-specific evidence IDs
(`providers/gemini_selector.py`); code owns order, routing (`providers/routes.py`, Google Routes
`computeRoutes` or straight-line estimates), timing, detours, estimates (`pricing.py`) and
conflicts (`services/questline_plan.py`). `services/suggestions.py` bounds real search-along-route
lookups and registers local waypoint IDs through a short trip-locked transaction. No provider call
holds a trip write lock. Price refresh/reimport updates coarse facts without replacing explicit
estimates or rewriting plans/snapshots. Credentials remain server-side. Public real-provider deployment
also needs Google attribution and content retention/refresh/removal across places, endpoints, snapshots,
and route content. See [Level 1](level-one-planning.md) for lookup/deadline budgets and limitations.

Plan schemas accept main/side roles, anchors, coordinates, travel/detour edges, polylines, days,
prices, conflicts, estimates, warnings, and change summaries. Basic graph references, cost ranges,
and timestamps are checked. Builds and structural edits use the same bounded `compose()` recomputation;
owners/notes remain follow-through edits. Stay ends a day; overnight resumption stays at the previous
endpoint, without invented accommodation or transfers. Other daily-window overflows remain editable
conflicts/warnings. Opening-hours validation and automatic feasibility repair remain Level 2.

## Persistence and relay endpoints

The `questline` schema now includes trips, members, messages, imports, places, votes,
plan generations, plans, tasks, and check-ins. Place IDs and member IDs are checked against the trip
on writes. Unique constraints prevent duplicate place IDs, votes, handles, and completion records;
coordinate/price ranges have database checks. All state writes are serialized by a trip row lock.

Additional implemented endpoints:

- `POST /trips/{id}/import`: parse `Name: text` and indented continuation lines, persist messages,
  enqueue extraction atomically, and report an import job in trip state. Synthetic paste timestamps
  are stable ordering markers, not claimed original timestamps. Reimporting identical text does not
  duplicate messages, evidence, or waypoints; it creates a new import job so failed extraction can retry.
- `POST /trips/{id}/places`: resolve a fixture and upsert by local trip + provider place ID.
- `POST /places/{id}/price-refresh`: one authenticated coarse-price lookup for a food/activity
  waypoint; preserves explicit ranges and updates only future snapshots. Failures leave state unchanged.
- `POST /places/{id}/votes`: explicit member choice; choosing it again removes it. Service callers
  supply `member_id`, whereas browser callers are always bound to their member token.
- Task create/update and check-in create/delete endpoints from SPEC §10. Check-ins and tasks reference
  waypoints, not plan revisions, so rebuilding preserves them.
- All service-only iMessage link/lookup/unlink, batch, reaction, and rename endpoints now exist.
  Members are upserted by `(trip_id, imessage_handle)`; display names never merge identities.
- Messages preserve `reply_to_guid` and resolve `reply_to_id` within the trip, including out-of-order
  parents. The relay now forwards this context. Replies become evidence for a single parent waypoint,
  **not inferred votes**. Reactions explicitly set/remove votes and never toggle on redelivery.
  Unresolved or multi-place targets are skipped; reactions arriving before extraction must be resent.

Trip-state responses include `imports` and `messages` as well as the spec's other collections so the
frontend can show job statuses and exact evidence quotes. Tallies and contested flags are derived
from vote rows, not cached counters. Tokens/hashes are never serialized.

Run `alembic upgrade head` before starting the new API/worker. Downgrading the persistence migration
removes its new tables and is destructive; it refuses relay-only members that the older schema cannot
represent. Back up any non-disposable database before changing schemas.

## Remaining Build work

- Level 2 planning: opening-hours checks and demote-and-retry when a day overflows. Gemini-written
  resolution options remain separate work (current options are deterministic and vote-grounded).
  The existing disclosed routing fallback during edits does not yet implement the spec's
  preserve-derived-values/`derived_stale` policy.
- Historical iMessage import and optional deferred reactions; the web organizer and their
  iMessage handle still become two members.
- Frontend deployment and deployment manifests; actual Supabase/hosting resources are not created.
- Google attribution and content retention for real Places data before any public deployment.

Divide these by the four roles in SPEC §12. Extend schemas and migrations deliberately; tests
should use fake providers and never consume real Gemini/Maps quota.

## Security boundaries

Keep the `questline` schema out of Supabase's exposed API schemas. Never ship the service token or
DB credentials in the browser. Use synthetic data until consent, transcript deletion/retention,
Google attribution/storage policies, and deployment controls are implemented. Imported messages
are untrusted input and must not grant AI permissions to book, pay, execute tools, or access other trips.
