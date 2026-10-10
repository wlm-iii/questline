# Backend architecture

This document describes the scaffold as implemented on `main`. The product requirements, the
target data model, and the target API contract (trips, members, waypoints, votes, operations,
resolutions, tasks, check-ins) are in [SPEC.md](SPEC.md); where the two differ, the spec is the
destination and this document is the current state.

## Boundaries

```text
Chat adapter / transcript upload
               ↓
       FastAPI /api/v1
               ↓
 PostgreSQL (private questline schema)
   messages + immutable snapshots + queue
               ↓
     Procrastinate worker
               ↓
  Planner interface → fake provider today
               ↓
      validated draft graph
               ↓
        interactive editor
```

One codebase, separate API and worker processes. Supabase is used as managed PostgreSQL, not as a
frontend-accessible database API. A future Gemini provider implements `providers/planner.py`;
Google Places/Routes implementations belong behind `providers/maps.py`. Keep credentials, timeouts,
rate limiting, and provider-specific payloads inside adapters.

| Path | Responsibility |
| --- | --- |
| `backend/src/questline/api/` | HTTP contracts, validation, access gate, status codes |
| `backend/src/questline/schemas.py` | Shared request, transcript, and graph schemas |
| `backend/src/questline/models.py` | PostgreSQL persistence |
| `backend/src/questline/services/` | Planning orchestration independent of HTTP |
| `backend/src/questline/jobs.py` | Queue wiring, worker entrypoint, queue schema bootstrap |
| `backend/src/questline/providers/` | AI and Maps boundaries; deterministic mock planner |
| `backend/src/questline/integrations/` | Future platform-specific chat adapters |
| `backend/migrations/` | Versioned application schema migrations |

## API contract

All versioned routes require `Authorization: Bearer <API_TOKEN>`. JSON fields use snake_case.
Swagger `/docs` and `/openapi.json` are the source of truth for payload schemas.

| Method | Path under `/api/v1` | Behavior |
| --- | --- | --- |
| POST | `/conversations` | Create a planning context; returns 201 |
| POST | `/conversations/{id}/messages/batch` | Import messages; return inserted count and revision |
| POST | `/conversations/{id}/plan-generations` | Snapshot transcript and enqueue work; returns 202 |
| GET | `/plan-generations/{id}` | Poll status, sanitized error, and eventual `plan_id` |
| GET | `/plans/{id}` | Load draft/accepted graph and current revision |
| PATCH | `/plans/{id}` | Replace full `content` with expected `revision`; stale edits return 409 |
| POST | `/plans/{id}/accept` | Accept expected revision; stale requests return 409 |

`PATCH` replaces plan content, not individual graph operations. Every edit increments the revision
and returns the plan to draft status. Acceptance also increments the revision. Canvas coordinates
are not yet modeled; don't equate editor positions with itinerary ordering.

### Ingestion and generation

- Ingestion is append-only for now. Deduplicate by conversation + external message ID. Identical
  redelivery is ignored; changed content under the same ID returns 409 and rolls back the whole batch.
- Messages require timezone-aware timestamps. Snapshots are ordered by timestamp then stored UUID
  (a stable tie-breaker, not a guarantee of source-platform order for identical timestamps).
- Transcript size is bounded by `MAX_TRANSCRIPT_CHARS` (default 100,000); oversized content gets 413,
  never silent truncation. Real providers must also enforce their model's token budget.
- Ingestion and snapshot creation lock the conversation row so revision and snapshot stay consistent.
- Generation requires `Idempotency-Key`. Within a conversation, repeating the same key and request
  returns the existing generation, even if newer messages have arrived. Changed request parameters
  under that key return 409. Use a new key to generate again from the latest transcript.
- The generation row and queued job commit in **one database transaction**. No in-process background
  tasks are used. API restarts don't lose queued work.
- The worker reads the whole saved snapshot, not the conversation's subsequently changing messages.
- Output is Pydantic-validated; graph IDs must be unique and edges reference existing nodes. Generated
  message references must belong to the snapshot. This does not yet prove itinerary feasibility.
- Each generation creates a **new** plan. Queue locks and a unique generation-to-plan relation prevent
  duplicate outputs; replaying completed work cannot overwrite an edited plan.
- Provider errors become sanitized `failed` status. Automatic paid-provider retries, cancellation,
  and stalled-job recovery are not implemented yet. After a failure, submit a new request/key.
  A killed worker may leave a generation `running`; monitor and implement recovery before production.

### Graph shape

`Plan.content` is validated JSONB containing `title`, `graph`, `assumptions`, `open_questions`, and
`warnings`. Nodes currently represent `place`, `activity`, or `lodging`. Edges represent `precedes`,
`travel`, or `alternative`. This models a suggested plan, not the worldwide road network.

The fake planner deliberately returns a labeled example activity rather than pretending to infer
preferences. Agree on schema extensions (dates, budgets, travel modes, participant preferences,
layout) with the editor and AI owners before building them independently.

## Security and deployment limits

This is a development/private-demo scaffold, **not a multi-tenant production app**.

- The shared bearer token is only a coarse access gate. Anyone holding it can access all records.
  Never embed a shared deployment secret in a publicly distributed frontend bundle.
- Before public access: implement user/bot identities, scoped credentials, conversation membership
  authorization, rate/request-size limits, and retention/deletion controls (including saved snapshots).
- Keep `questline` private in Supabase; don't expose it through PostgREST or grant anonymous access.
  Use separate least-privilege runtime and migration roles before production.
- Chat participation must be visible and opt-in. Verify each platform's permissions and historical
  transcript availability. Do not silently collect chats or send them to Gemini without consent.
- Treat chat messages as untrusted model input. Do not let them grant tool permissions or trigger
  bookings, payments, arbitrary URLs, or access to other conversations.
- Keep uncertain AI suggestions explicit. Validate dates, travel times, and place matches rather than
  presenting generated guesses as verified facts.
- Maps data has caching/attribution restrictions. Store place IDs where appropriate; do not indiscriminately
  persist provider responses. Review the policies for each API you integrate.
- `/health/live` checks the process; `/health/ready` checks database connectivity only, not worker health,
  queue migrations, or third-party APIs. Run migrations before starting services.

## Work streams

1. **AI planning:** implement Gemini behind `Planner`, structured output validation, model configuration,
   transcript-to-constraints extraction, uncertainty, and token/cost limits. Add the official
   `google-genai` dependency and update `uv.lock` when implementing it.
2. **Maps:** implement place resolution and route estimates with HTTPX, bounded timeouts/retries, correct
   attribution, and storage rules; integrate with the planning service rather than HTTP routes.
3. **Bots:** choose one platform, normalize transcript events, verify consent/permissions, ingest through
   the API, request generation, poll status, and post a link. Add edits/deletions deliberately.
4. **Editor:** consume OpenAPI contracts, render graph JSON, edit full content with revision checking,
   handle 409 conflicts, and surface assumptions/questions. The React/TypeScript/Vite scaffold is
   at the repository root; API integration and the interactive editor remain to be implemented.
5. **Platform/auth:** user and bot authentication, conversation membership, deployment, rate limits,
   logging/monitoring, retry/recovery policies, and privacy controls.

Coordinate changes to `schemas.py` and migrations early. Use fake planning for independent development;
keep integration tests deterministic and free of real Gemini/Maps calls.
