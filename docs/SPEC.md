# Questline — Product and Implementation Spec

Hackathon build: 30 hours, Saturday 9:00 AM → Sunday 3:00 PM. Track: Productivity. Team of four.
Revised October 10, 2026. Supersedes the Tripchat spec.

This spec is the implementation handoff for the team. Build the Must-have features first, using the
data model (§9) and API contract (§10) below. The demo succeeds when a group can import their chat,
see every place they mentioned as a waypoint on a shared map, vote, get a routed questline with main
and side quests, resolve one contested stop, accept the plan, and check off the first quest.

**How to read this spec: Build vs. Harden.** Everything here is a Build requirement unless it is
listed in §19 *Harden if there's time*. Build the end-to-end flow first (§13 build order), get it
deployed and demoable, and only then work through §19. Harden rules describe the correct long-term
behavior; skipping them during the hackathon is expected, not a bug.

## What changed from the Tripchat spec

- **Name:** Tripchat → **Questline**.
- **Interface:** no chat UI. Questline is an **interactive map**. The group's existing chat is an
  *input* (pasted in, later via bots), not the place where planning happens.
- **Vocabulary:** place cards → **waypoints**; the plan → the **questline**; stops are **main
  quests** (committed, solid line) or **side quests** (optional, dotted line).
- **Thesis:** Questline doesn't just generate plans. It helps groups **decide** (votes on
  waypoints), **resolve conflicts** (contested waypoints get grounded options), and **follow
  through** (an accepted questline becomes a quest log with owners, tasks, and check-offs).
- **Team:** four people. Roles in §12.
- **Stack:** aligned with what is on `main` today: React + TypeScript + Vite (`frontend/`); FastAPI + SQLAlchemy +
  Alembic + Procrastinate; Supabase as managed PostgreSQL only. The browser never talks to the
  database; all reads and writes go through FastAPI. Live updates use polling (Build) with
  server-sent events as Harden.
- **Plan JSON:** a graph (nodes + edges) that extends the scaffold's `PlanContent`. The UI edits it
  through operations (`POST /plans/{id}/operations`) applied server-side with revision checks; code
  recomputes routes, times, costs, and conflicts after every edit.
- **iMessage bot (§11.1):** the group keeps chatting in their real iMessage group. A silent
  Questline bot in that group feeds messages into the trip as they're sent, turns tapbacks on
  messages into votes, and replies only when someone calls it (`@questline …`). Chatting happens
  only in iMessage; the web app is the map/dashboard. Pasting a chat stays as the baseline input
  and the demo fallback.

## 1. One-liner

A shared map that turns a group's chat into a trip they will actually take. Every place anyone
mentioned becomes a waypoint. The group votes, Questline routes the committed stops into a main
quest and hangs the maybes off it as side quests, flags where people disagree and offers ways out,
and once the questline is accepted it becomes a quest log the group checks off on the day.

**Pitch line:** "Your group chat has 300 messages and no plan. Questline turns it into a map you can
vote on, a route you agree on, and a quest log you actually finish."

## 2. Problem

- Group trip planning happens in messy chats (Instagram DMs, iMessage, WhatsApp). Ideas get buried,
  nobody knows what was agreed, and one person ends up doing all the work.
- Chat fails at three specific points: nobody *decides*, disagreements stall *quietly*, and the plan
  that does get made isn't *followed*.
- Product hypothesis: putting candidate places on a shared map with explicit votes, surfacing
  disagreement instead of burying it, and turning the accepted plan into a checklist reduces the
  organizer's work and raises follow-through. The demo should prove that benefit without relying on
  unverified claims about competing products.

Target user: the friend who always ends up organizing (4–8 person friend groups, weekend road
trips). Everyone else votes and taps.

## 3. How it works (user flow)

1. **Create a trip.** Organizer enters trip name, origin, destination, dates, and time zone. Gets a
   share link (`/t/abc123`) to drop in the group chat.
2. **Join.** Friends open the link and type their name. No accounts. A member token is saved in the
   browser.
3. **Seed the map.** The organizer pastes the group chat into the Import sheet. Questline extracts
   place mentions, resolves them on Google Places, and drops them on the map as waypoints, each
   showing who mentioned it and the quote. Anyone can also add a waypoint by searching. Mentions
   that can't be resolved are listed under "Couldn't place" with a one-tap search; nothing is
   invented.
   **Or connect the iMessage group (§11.1):** someone adds the Questline bot to the group and
   sends `@questline link abc123`. From then on, new messages flow in automatically and waypoints
   appear on the map without anyone pasting anything.
4. **Vote.** Tap a waypoint → *I'm in* / *Sure* / *Skip*. Tallies show on the marker. A waypoint
   with at least one *I'm in* and one *Skip* is marked **contested**. In a connected iMessage
   group, a tapback on a message that mentions exactly one waypoint also counts as a vote
   (❤️ → *I'm in*, 👍 → *Sure*, 👎 → *Skip*).
5. **Build the questline.** Tap *Build*. The AI proposes which waypoints are main quests and which
   are side quests, orders the main quest, and writes a grounded "why" for each. Code routes the
   main quest (solid line), computes arrival and departure times, attaches side quests to the leg
   they detour from (dotted line, "+N min"), and estimates per-person cost. Budget presets rebuild
   the questline and highlight what changed.
6. **Decide and resolve.** Anyone can promote a side quest to the main quest, demote, reorder, or
   drop a waypoint directly on the map. For a contested waypoint, tap *Resolve*: Questline returns
   up to three options grounded in the votes and quotes (make it a side quest, swap for a nearby
   alternative, move it, drop it). Picking one applies it as an edit everyone sees.
7. **Accept.** Anyone taps *Accept the questline*. The current revision is locked and the map
   switches to quest-log mode. Edits after acceptance return it to draft.
8. **Follow through.** Each main quest can have an owner ("Sam books the campsite") and tasks. On
   the day, tap *Quest complete* as you go; the map shows progress ("3 of 7 quests done") and
   *Next up* with a leave-by time.

## 4. Screens and layout

- **Map (main screen).** Google map fitted to all waypoints.
  - Main-quest waypoints: numbered solid markers in travel order, connected by a **solid**
    polyline that follows the driving route (one decoded leg polyline per edge).
  - Side-quest waypoints: hollow markers connected to their anchor leg by a **dotted** line with a
    "+N min" label. Build version: a straight dashed line from the anchor waypoint to the side
    quest (Maps JS symbol icon with `repeat`); routed dotted detours are Harden.
  - Candidate waypoints not yet in the questline: small grey markers.
  - Badges: contested (⚠), over budget, done (✓). Origin and destination use distinct markers.
  - Tapping a marker opens its waypoint card; the matching row in the side panel highlights.
- **Side panel** (right sidebar on desktop; bottom sheet on mobile). Tabs:
  - **Waypoints:** every candidate grouped by category — Eat, Do, Stay, Along the way. Each row:
    name, category, est. price range, vote tallies, who mentioned it, quest status (main / side /
    not in questline). Stats line: "11 waypoints from 47 messages" (counts derived from rows).
  - **Questline:** empty state with a *Build* button until a plan exists; then day-by-day list of
    main quests with arrive/depart times, side quests nested under the leg they hang off, budget
    preset switcher, "est. food + activities / person" with exclusions, conflicts list, warnings,
    and the *Accept* button. Each row has promote / demote / drop controls and drag-to-reorder.
  - **Quest log** (after acceptance): main quests as a checklist with owner, tasks, *Quest complete*,
    progress bar, and *Next up*.
- **Waypoint card** (sheet over the map): name, address, Google attribution, category, est. price,
  hours status, vote buttons and tallies with names, evidence quotes from the imported chat, the
  AI "why" when in the questline, detour minutes for side quests, owner and tasks, and actions:
  *Make main quest* / *Make side quest* / *Drop* / *Resolve* (contested only).
- **Import sheet:** a textarea for pasted chat (one message per line, `Name: text`), a *Looks right*
  preview of parsed messages, and an *Import* button. Shows extraction progress and the "Couldn't
  place" list afterwards.
- **Create / Join:** simple forms. Origin and destination must resolve to Google Places; ambiguous
  entries get a validation message before a trip is created. The Create and Join screens state
  that the trip is visible to anyone with the link.
- **Loading and failure states:** the map stays usable while extraction or planning runs. Preserve
  the last successful questline during rebuilds; show progress and a retry action after failure.
  An empty map explains that importing a chat or adding a waypoint puts places on it.

## 5. Scope

### Must-have (the demo)

1. Create a trip and join by link (no accounts, name only).
2. Seed the map: paste a chat → extraction → resolved waypoints with evidence quotes; add a
   waypoint by search.
3. Interactive map with votes: tallies on markers, contested detection, everyone sees updates.
4. *Build* → questline: main quest routed and timed (solid), side quests with detour minutes
   (dotted), "why" notes, sources, per-person estimate, budget presets with change highlights.
5. Decide and resolve: promote / demote / reorder / drop as revisioned edits; *Resolve* on a
   contested waypoint returns grounded options and applies the chosen one; *Accept*.
6. Follow through: owners, tasks, *Quest complete*, progress, *Next up*.
7. **iMessage bot (§11.1):** link a group with `@questline link <trip>`; live ingestion of new
   messages into extraction; tapback votes; `@questline build`, `@questline add <place>`, and
   `@questline link` replies. Silent otherwise. Pasted import (item 2) stays as the fallback, so
   items 1–6 never depend on the bot. *Priority vs. items 5–6 is an open decision (§18).*

### Must-have tooling (not user-facing, but required)

- **Fake providers:** deterministic `FakePlanner`, `FakeExtractor`, and `FakeMaps` so every track
  can run end to end without keys. Selected by `PLANNER_PROVIDER` and `MAPS_PROVIDER`.
- **Seed script (§20):** creates a trip, joins members, imports the demo chat, casts votes, and
  requests a build through the public API. Used for testing, prompt tuning, seeding, and as the
  demo fallback.

### Stretch (in priority order)

1. Constraint extraction from the chat ("Sam can't hike", "back by 6 on Sunday") shown as chips and
   fed to the planner. Extend it into a **Group notes** panel: dates/timing, budget hints, dietary
   or mobility constraints, and open questions nobody answered ("who's bringing the speaker?"),
   each quoting the source message. Same honesty rules: quotes only, never invented agreement.
2. `@questline <question>` answers in the iMessage group ("how long is Monterey → Big Sur?").
3. Private budget max + one anonymous veto per person (needs a member-authorized design first).
4. Live check-in: geolocation marks a quest complete when you arrive.
5. Split-the-bill screen ("Alex paid $240 → each person's share + Venmo link").
6. Discord bot that forwards channel messages into the trip (§11.2).

### Not in the hackathon (later)

- Instagram screenshot import (the iMessage relay already sees attachment file paths, so
  screenshots sent in the group are a cheap later path); WhatsApp / iMessage export parsers
  (Harden if cheap).
- iMessage groups that include Android/SMS members; a hosted iMessage provider instead of the
  team's Mac.
- Multiple trips detected in one chat; drive-vs-fly decisions.
- Full expense ledger, booking, accounts/login.
- Yelp or Tripadvisor data. Google Places already provides ratings, review counts, price levels,
  hours, and photos; a second provider adds key setup, cross-provider matching, and separate
  display terms.

### Demo boundaries and acceptance

Use a domestic road trip in one time zone, lasting one to three days. Dates are inclusive; routes
are one-way from origin to destination unless the organizer enters the same endpoint. Default days
run 9:00 AM–7:00 PM in the trip time zone. These defaults appear as plan assumptions. Overnight gaps
mean accommodation is unplanned unless a Stay waypoint is in the main quest; never invent a hotel or
a return leg.

- Two browsers see the same waypoints, votes, questline, tasks, and check-offs within one polling
  interval; refreshing restores saved state.
- Importing the same chat twice creates no duplicate messages or waypoints. Mentioning the same
  Google place twice reuses one waypoint. Ambiguous or unresolved text creates no fictional
  waypoint.
- A questline contains only resolved waypoints, ordered travel legs, feasible times, sources,
  reasons, and estimates with stated coverage. Side quests always show detour minutes or
  "detour unknown".
- A waypoint with both *I'm in* and *Skip* votes is marked contested; *Resolve* returns only options
  whose operations validate against the current plan; applying one creates a new revision.
- Changing a budget preset creates a new plan, compares it with the previous successful plan, and
  leaves that previous plan visible if generation fails.
- Accepting locks a revision; an edit after acceptance returns the plan to draft. Check-offs survive
  rebuilds because they are keyed by waypoint, not by plan revision.
- iMessage: a message sent in the linked group reaches the trip once (redelivery is ignored by
  `external_id`), its places appear on the map within ~30 seconds, a ❤️/👍/👎 tapback on a
  single-place message sets that sender's vote, removing the tapback removes it, and the bot never
  replies to its own messages or posts without a command (except the one-time link notice).
- Before stretch work, the whole team runs this flow on the deployed app with two devices.

## 6. Data honesty rules

These are product rules, not nice-to-haves. The demo must never claim something we can't know.

- Never say "hidden gem." Prefer "Group pick" for places mentioned in chat. Use "Less touristy"
  only with a disclosed comparison; fewer reviews alone does not establish crowd levels.
- Prices are ranges marked *est.* Google price level is a coarse input to an app-defined range,
  not a quote. Missing price data stays unknown; a missing value is never free.
- Parking is "likely street / lot nearby / unknown," with a link out. Never claim availability.
- Side quests always show detour minutes ("+6 min") or "detour unknown"; never imply "on the way."
- Every waypoint shows where it came from: group mention (with quotes) vs. AI suggestion.
- Every displayed place is resolved through Google Places. Gemini selects candidate IDs and writes
  reasons; code supplies names, coordinates, routes, times, detours, estimates, and conflict labels.
- Votes are shown as counts and names. "The group agreed" appears only when every member voted
  *I'm in* or *Sure*. The AI never declares a conflict resolved; applying a resolution is a human
  action recorded as a revision.
- "Why" notes and resolution rationales describe actual votes and quotes, without inventing group
  agreement, preferences, or facts about the place.
- Unknown opening hours display "Hours unverified." A valid route is not a claim that an attraction
  is open, accessible, or that parking is available.
- Display required Google attribution on waypoint cards and the map. Store place IDs for
  deduplication; retain other Google-derived fields only where current terms permit, and refresh
  or remove them accordingly. See Google's Places policies and place ID guidance.
- Imported chat text is untrusted model input. It never grants permissions, triggers bookings or
  payments, or reaches another trip.
- The iMessage bot reads a group only after someone in it sends `@questline link`, and it then
  posts one visible notice saying it is reading the chat, that messages go to Google Gemini, and
  how to stop (`@questline unlink`). It never reads messages sent before the link unless someone
  explicitly asks (`@questline import last N`), and even then it can only see messages sent after
  the bot joined the group; older history needs the paste import. Tapback votes are attributed to the sender's
  handle, never guessed.

## 7. Tech stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Frontend | React + TypeScript + Vite (repo root) | `react-router` for `/t/:tripId`; `@vis.gl/react-google-maps` for the map (markers, polylines, fit bounds); polling hook against `GET /trips/{id}` |
| Backend | Python 3.12 + FastAPI (`backend/`) | SQLAlchemy 2 (async, psycopg), Pydantic, Alembic migrations, `httpx` for Google APIs, `google-genai` for Gemini (add and lock when the provider lands) |
| Database | PostgreSQL on Supabase (managed Postgres only) or Docker locally | Private `questline` schema; never exposed through PostgREST or an anon key. Frontend reads and writes only through FastAPI |
| Jobs | Procrastinate (Postgres-backed queue) | Extraction and plan generation run in the worker; job rows commit in the same transaction as the request |
| AI | Gemini via Google AI Studio | Structured JSON output validated with Pydantic. Check AI Studio for the current Flash-tier model name and record it in `GEMINI_MODEL` |
| Places & routes | Google Places API (New), Routes API, Maps JavaScript API | Text Search with location bias; `computeRoutes` with intermediates for the main quest; search-along-route for suggested side quests |
| iMessage relay | [`imsg`](https://github.com/openclaw/imsg) CLI (`brew install steipete/tap/imsg`) on a team MacBook + a Python relay (`backend/src/questline/integrations/imessage/`) | Reads `~/Library/Messages/chat.db`, sends via Messages.app AppleScript. No SIP changes. Talks to FastAPI with `API_TOKEN` like any bot (§11.1) |
| Hosting | Vercel Hobby (frontend); Render web service (API + worker) | If the hosting plan doesn't allow a separate worker process, start the worker inside the API process for the demo (§8). Free services sleep; warm the backend before judging and keep a local/video fallback |

## 8. Architecture

**Rule: the browser talks only to FastAPI.** The database is private; the queue is private. One
write path means a future Discord bot or a seed script uses exactly the same endpoints as the UI.

```text
iMessage group ──► team Mac: Messages.app + imsg watch ──► imessage relay
                                                              │  (API_TOKEN; same endpoints, §11.1)
Browser (React map)                                           │
  ├── GET /trips/{id}?revision=N  (poll every 3 s; unchanged → tiny response)
  └── POST/PATCH ─────────────► FastAPI /api/v1 ◄─────────────┘
                                      │
                                      └──────────────► PostgreSQL (questline schema)
                                      │                 ├── trips, members, messages, places, votes,
                                      │                 │   plan_generations, plans, tasks, checkins
                                      │                 └── procrastinate queue
                                      ▼
                              Procrastinate worker
                                ├── extract_places  ──► Gemini (extractor) ──► Google Places
                                └── generate_plan   ──► Gemini (planner)   ──► Google Routes / Places
```

### Identity and access

- Creating or joining a trip returns a `member` and a random `member_token`. The browser stores it
  per trip and sends `X-Member-Token` on every request. The backend resolves token → member → trip
  and rejects cross-trip references with 422.
- Trip IDs are random and unguessable, but **a link is not authorization**: anyone with the link can
  join, read, vote, and edit. Say so on Create/Join, use disposable demo data, and do not claim
  private trips. Private stretch features need a member-authorized design first.
- `Authorization: Bearer <API_TOKEN>` (the scaffold's shared service token) is for the seed script,
  tests, and future bots. It is never shipped in the frontend bundle.
- Restrict CORS to the frontend origin. Limit text lengths on every input. Rate limits are Harden.

### Live updates

`trips.revision` increments on every write that affects the trip (membership, messages, places,
votes, plans, tasks, check-ins, job status). The frontend polls `GET /trips/{trip_id}?revision=N`
every 3 seconds; when the revision is unchanged the server returns `{unchanged: true}`. Poll
immediately after any local write. Deduplicate rows by ID. Server-sent events are Harden (§19).

### Jobs

Two Procrastinate tasks, both locked per trip and both committed in the same transaction as the
request that created them (no in-process background tasks, so an API restart doesn't lose work):

- `questline.extract_places(import_id)` — reads the imported messages, asks the extractor for place
  mentions, resolves each on Google Places, upserts `places`, records unresolved mentions.
- `questline.generate_plan(generation_id)` — reads the saved snapshot (messages, places, votes,
  members, preset) and builds the questline (levels below).

Job status is visible in trip state (`jobs`). Provider errors become sanitized `failed` status.
Retry is a new request. A killed worker can leave a job `running`; stalled-job recovery is Harden.

For the demo deploy, if a separate worker process isn't available, start the worker from the
FastAPI lifespan (`app.run_worker_async`) in the same process; separate processes are Harden.

### Extraction

1. `POST /trips/{id}/import {text}` parses `Name: text` lines (continuation lines append to the
   previous message), assigns monotonic `sent_at` timestamps and content-hash `external_id`s, and
   stores them through the same batch path as `POST /trips/{id}/messages/batch`. Identical
   redelivery is ignored; the same `external_id` with different text returns 409 and rolls back.
2. The extractor (Gemini, structured output) returns `[{mention_text, search_query,
   category_guess, message_ids}]`. Validate that every `message_id` is in the import.
3. Code resolves each `search_query` with Places Text Search biased to the box around origin and
   destination. Accept the top result only if it is inside the bias region (or the trip state) and
   the name is a plausible match; otherwise add it to `trips.unresolved_mentions`.
4. Upsert `places` on `(trip_id, google_place_id)`, append `message_ids` to
   `places.source_message_ids`, set `source = group`, and set `mentioned_by` to the first author
   if they map to a member (author → member mapping is Harden; otherwise store the author name).
5. `POST /trips/{id}/places {query}` ("Add waypoint") runs steps 3–4 synchronously for one query and
   returns 201 with the waypoint (`source = added`, `mentioned_by` = the caller), or 404
   `place_not_found` with "Couldn't find that place — try adding the city."

### Questline generation levels

Build plan generation in levels. Each level is demoable on its own; stop wherever time runs out.
The plan JSON shape (§10) is the same at every level; fields a level doesn't compute are `null` or
empty.

- **Level 0 (Build, target Sat ~2 PM):** Gemini receives the candidates with vote scores and quotes
  and returns `{main: [place ids in order], side: [{place_id, anchor_place_id}], why: {place_id:
  text}}`. One Routes API `computeRoutes` call with the main stops as intermediates returns the
  legs and polylines; code computes arrive/depart from the day start plus drive and visit
  durations. Single preset (`comfortable`), `detour_min` null, `hours_status` unknown, conflicts
  limited to `split_vote`.
- **Level 1 (Build, target Sat ~midnight):** `detour_min` per side quest, suggested side quests
  from search-along-route (`source = suggested`), budget presets with the price-range table,
  per-person estimate, `over_budget` conflicts, `changed_from_previous`.
- **Level 2 (Harden):** opening-hours checks, daily-window feasibility with demote-and-retry,
  `does_not_fit` and `hours` conflicts, and the full validation in steps 5–7 below.

### Questline generation (full version)

1. Get the route origin → destination from the Routes API.
2. Candidates = the trip's `places` + at most a few search-along-route queries. Score votes as
   *in* +2, *ok* +1, *out* −1; deprioritize negative scores rather than silently treating one
   *Skip* as a group veto. Every waypoint stays in the Waypoints tab even when omitted from the
   questline.
3. Use the preset's food/activity targets and configured price ranges to prefer affordable main
   quests. Unknown prices remain explicitly unpriced. Persist selected suggestions in `places` so
   every node has a local place UUID.
4. Gemini picks main-quest IDs and order, side-quest IDs with anchors, visit durations, and grounded
   reasons. Code requests driving routes through the ordered main stops and calculates
   arrival/departure times, including each day's start and end legs. The map must follow the
   selected stops, not just the original route.
5. Check dates, travel times, visit durations, and available opening-hour data. Respect the daily
   window; demote the lowest-priority main quest to a side quest and retry once if infeasible. If
   still infeasible, mark the generation failed and explain why. Missing hours produce a warning,
   not a fabricated validation pass.
6. For a side quest S anchored to the leg A → B, `detour_min = max(0, drive(A, S, B) − drive(A, B))`
   using comparable route settings. Exclude visit time, round to whole minutes, and use `null` if
   unavailable. Detours are local to their leg and are not additive. Search-along-route results are
   candidates, not a substitute for this calculation.
7. Code computes the estimate, conflicts, warnings, and `changed_from_previous`, validates the
   final JSON, and atomically saves a `draft` plan plus the trip's `current_plan_id` and preset.
   Capture a snapshot of messages, places, votes, members, and the requested preset at request time,
   in the same transaction that enqueues the job; later activity does not silently modify that plan.

### Edits: operations and recompute

The UI never sends full plan content. It sends `POST /plans/{id}/operations {revision,
operations: [...]}`. Each operation uses an `op` discriminator, for example
`{"op": "set_quest", "node_id": "place-uuid", "quest": "main"}`. The server checks the revision
(409 on mismatch), applies the operations to the **decision** fields, recomputes every **derived** field, saves, bumps the revision, sets status back
to `draft`, and returns the full plan.

| Operation | Fields | Effect |
| --- | --- | --- |
| `set_quest` | `node_id`, `quest: main\|side` | Promote or demote. Promoting inserts after the anchor; demoting anchors to the leg that replaces it |
| `move` | `node_id`, `after: node_id \| "start"` | Reorder within the main quest |
| `set_anchor` | `node_id`, `anchor: node_id \| "start"` | Choose which main leg a side quest hangs off |
| `drop` | `node_id` | Remove from the questline; the waypoint stays in the Waypoints tab |
| `add` | `place_id`, `quest`, `after?` / `anchor?` | Put a candidate waypoint into the questline |
| `assign_owner` | `node_id`, `member_id \| null` | Follow-through owner |
| `set_note` | `node_id`, `notes` | Shared note on a stop (≤ 500 chars) |

Decision fields: node membership, `quest`, order, `anchor`, `owner_member_id`, `notes`.
Derived fields (code-owned, recomputed on every edit): edges, polylines, `drive_min`,
`distance_m`, `days`, `arrive`/`depart`, `detour_min`, estimates, `conflicts`, `warnings`,
`changed_from_previous`. If the Routes API fails during recompute, save the decision, keep the
previous derived values, set `derived_stale: true`, and add a warning; the next successful edit or
build clears it. `PATCH /plans/{id}` (full replacement, from the scaffold) remains for tooling only.

### Conflicts (code-detected)

| Kind | Rule | Level |
| --- | --- | --- |
| `split_vote` | at least one *in* and one *out* on the waypoint | 0 |
| `over_budget` | known price level above the preset's allowed levels | 1 |
| `does_not_fit` | the day's main quest exceeds the daily window | 2 |
| `hours` | returned hours are incompatible with the scheduled visit | 2 |

Conflicts are listed in `plan.content.conflicts` and badged on markers. Unpriced waypoints are a
warning, not a conflict.

### Resolve

`POST /plans/{id}/resolutions {node_id}` is synchronous (20 s timeout; 503 on provider failure).
Gemini receives the conflict, the node, votes with names, evidence quotes, the current questline,
nearby candidates from `places`, and the budget preset. It returns up to three options:
`{label, rationale, operations: [...]}`. Code validates every operation against the plan and
candidate list and discards invalid options. Choosing an option calls `/operations` with the
option's operations and the current revision. Rationales must cite the actual votes and quotes;
code rejects options whose rationale references members or places not in the input.

### Budget presets (starting values, tune during the build)

| Preset | Food per person / day | Activities per person / day | Allowed price levels |
| --- | --- | --- | --- |
| Shoestring | ≤ $30 | ≤ $20 | Free, $ |
| Comfortable | ≤ $70 | ≤ $60 | up to $$ |
| Treat ourselves | ≤ $150 | ≤ $150 | up to $$$$ |

These are planning targets, not spending guarantees. `per_person_estimate` is the sum of priced food
and activity **main quests** over the full itinerary, in USD per adult; label it "est. food +
activities / person". Side quests show their own range as "+$X–Y if you take it" and are excluded
from the subtotal. Exclude lodging, fuel, tolls, parking, taxes, and tips and show those exclusions
next to the amount. List unpriced stops and mark the subtotal partial; return `null` if nothing is
priced. Keep a deterministic category/price-level range table in backend configuration and disclose
it as an app estimate. The LLM cannot invent prices. Budget changes may result in no swaps; report
that honestly. An unknown-price stop must never be called cheaper.

## 9. Data model (PostgreSQL, `questline` schema)

The scaffold's `conversations` table becomes `trips` (rename in a migration); `messages`,
`plan_generations`, and `plans` are extended; the rest are new. Use foreign keys and enforce that
referenced members, places, and plans belong to the same trip (DB-level checks are Harden; the
backend validates on every write).

- **trips:** `id` (random, unguessable text), `name`, `origin`, `destination` (each
  `{label, google_place_id, lat, lng}`), `start_date`, `end_date`, `timezone` (IANA),
  `budget_preset` (`shoestring|comfortable|treat`, default `comfortable`), `current_plan_id`
  (nullable; only a successfully generated draft or accepted plan from this trip),
  `revision` (int, bumps on any write),
  `unresolved_mentions` (jsonb list of `{mention_text, message_ids}`), `discord_channel_id`
  (nullable), `imessage_chat_guid` (nullable, unique; the linked group, e.g.
  `iMessage;+;chat0000`), `created_at`.
- **members:** `id` (uuid), `trip_id`, `name` (1–60 chars), `token_hash` (nullable for members
  created by the iMessage relay), `discord_user_id` (nullable), `imessage_handle` (nullable; phone
  or email; unique on `(trip_id, imessage_handle)`), `created_at`. The raw token is returned once
  and stored only in the browser.
- **messages:** `id` (uuid), `trip_id`, `external_id` (for iMessage: the message `guid`),
  `author_id` (string; the name as written, or the iMessage handle), `member_id` (nullable; set
  when the author maps to a member), `sent_at` (tz-aware), `text` (≤ 10,000 chars), `source`
  (`import|web|discord|imessage`), `import_id` (nullable), `reply_to_guid` (nullable original
  parent GUID), `reply_to_id` (nullable parent message UUID, resolved only within the trip).
  Unique on `(trip_id, external_id)`. Order by `(sent_at, id)`. Bot commands (`@questline …`) are not stored or extracted.
- **imports:** `id` (uuid), `trip_id`, `member_id` (nullable for relay batches), `source`
  (`paste|imessage`), `status` (`queued|running|succeeded|failed`), `message_count`,
  `message_ids` (JSONB list of imported message UUIDs, including deduplicated redeliveries),
  `error` (nullable), `created_at`. Each relay flush (§11.1) is one import, so `extract_places` works the
  same for pasted and live messages.
- **places** (waypoints): `id` (uuid), `trip_id`, `google_place_id`, `name`, `category`
  (`eat|do|stay|along_the_way`), `address`, `lat`, `lng`, `google_maps_uri`, `price_level`
  (nullable int 0–4), `est_cost_low`, `est_cost_high`, `cost_basis` (nullable), `source`
  (`group|suggested|added`), `mentioned_by` (nullable member id), `mentioned_by_name` (nullable),
  `source_message_ids` (jsonb list), `created_at`. Unique on `(trip_id, google_place_id)`. Cost
  bounds are both null or nonnegative with low ≤ high. A later group mention changes a suggested
  waypoint's source to `group`. Google-derived display fields are subject to §6 retention rules.
- **votes:** `id` (uuid), `trip_id`, `place_id`, `member_id`, `kind` (`in|ok|out`), `created_at`.
  Unique on `(place_id, member_id)`. One vote per person per waypoint; choosing a different kind
  replaces it, choosing the current kind removes it. The backend derives `trip_id` from the place.
- **plan_generations:** `id` (uuid), `trip_id`, `requested_by` (member id, nullable for service
  calls), `idempotency_key`, `budget_preset`, `snapshot` (jsonb: messages, places, votes,
  members, taken at request time), `status` (`queued|running|succeeded|failed`), `error`
  (nullable, sanitized), `previous_plan_id` (nullable; the trip's current plan at request time),
  `created_at`. Unique on `(trip_id, idempotency_key)`. A partial unique index allows one
  queued/running generation per trip (Harden; Build returns the existing job).
- **plans:** `id` (uuid), `trip_id`, `generation_id` (unique), `budget_preset`, `revision` (int,
  starts at 1), `status` (`draft|accepted`), `accepted_at` (nullable), `content` (jsonb, §10),
  `created_at`, `updated_at`. Each generation creates a new plan; operations bump `revision` and set
  `draft`; accept bumps `revision` and sets `accepted`.
- **tasks:** `id` (uuid), `trip_id`, `place_id`, `text` (1–200 chars), `owner_member_id`
  (nullable), `done_at` (nullable), `created_by`, `created_at`.
- **checkins:** `id` (uuid), `trip_id`, `place_id`, `member_id`, `completed_at`. Unique on
  `(trip_id, place_id)`. Keyed by waypoint so completion survives rebuilds and revisions.

Derive vote tallies, waypoint counts, task counts, and progress from rows; never store totals.

## 10. API contract (backend)

All routes live under `/api/v1`. Member routes require `X-Member-Token`; the seed script and tests
may use `Authorization: Bearer <API_TOKEN>` instead. JSON fields are snake_case. Swagger `/docs` is
the source of truth for payload schemas.

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/trips` | `{name, origin, destination, start_date, end_date, timezone, organizer_name}` | 201 `{trip, member, member_token}` |
| POST | `/trips/{trip_id}/members` | `{name}` | 201 `{member, member_token}` |
| GET | `/trips/{trip_id}?revision=N` | — | 200 `{trip, members, places, votes, current_plan, tasks, checkins, jobs, revision}` or `{unchanged: true, revision}` |
| POST | `/trips/{trip_id}/import` | `{text}` | 202 `{import_id, message_count, status: "queued"}` |
| POST | `/trips/{trip_id}/messages/batch` | `{messages: [{external_id, author_id, sent_at, text}]}` | 200 `{inserted, revision}` (scaffold; used by bots and the seed script) |
| POST | `/trips/{trip_id}/places` | `{query}` | 201 `{place}`; 404 `place_not_found` |
| POST | `/places/{place_id}/votes` | `{kind}` | 200 `{vote}`; `{vote: null}` when removed |
| POST | `/trips/{trip_id}/plan-generations` | `{budget_preset}` + `Idempotency-Key` header | 202 `{generation}` |
| GET | `/plan-generations/{generation_id}` | — | 200 `{generation}` with `plan_id` when succeeded |
| GET | `/plans/{plan_id}` | — | 200 `{plan}` |
| POST | `/plans/{plan_id}/operations` | `{revision, operations: [...]}` | 200 `{plan}`; 409 on stale revision |
| POST | `/plans/{plan_id}/resolutions` | `{node_id}` | 200 `{options: [{label, rationale, operations}]}` |
| POST | `/plans/{plan_id}/accept` | `{revision}` | 200 `{plan}`; 409 on stale revision |
| PATCH | `/plans/{plan_id}` | `{revision, content}` | 200 `{plan}` (full replacement; tooling only) |
| POST | `/trips/{trip_id}/tasks` | `{place_id, text, owner_member_id?}` | 201 `{task}` |
| PATCH | `/tasks/{task_id}` | `{text?, owner_member_id?, done?}` | 200 `{task}` |
| POST | `/places/{place_id}/checkins` | — | 200 `{checkin}` |
| DELETE | `/places/{place_id}/checkins` | — | 204 |
| GET | `/health/live`, `/health/ready` | — | `{ok: true}` |
| POST | `/trips/{trip_id}/channels/imessage` | `{chat_guid}` (Bearer only) | 200 `{trip}`; 409 if the chat is linked to another trip |
| DELETE | `/trips/{trip_id}/channels/imessage` | — (Bearer only) | 204; stops ingestion, keeps existing data |
| GET | `/channels/imessage/{chat_guid}` | — (Bearer only) | 200 `{trip_id}`; 404 if unlinked (relay cache warm-up) |
| POST | `/trips/{trip_id}/imessage/batch` | `{messages: [{guid, handle, display_name?, sent_at, text, reply_to_guid?}]}` (Bearer only) | 202 `{import_id, inserted}`; upserts members by handle, inserts messages, enqueues `extract_places` |
| POST | `/trips/{trip_id}/imessage/reactions` | `{reactions: [{handle, target_guid, kind: love\|like\|dislike, added}]}` (Bearer only) | 200 `{applied, skipped}` |
| PATCH | `/trips/{trip_id}/imessage/members/{handle}` | `{name}` (Bearer only; see §11.1) | 200 `{member}`; 404 if no member has that handle yet |

Rules:

- Create-trip origin and destination are text; the backend resolves them to the §9 objects before
  returning. `timezone` is required, defaulted in the UI from the browser's IANA zone and shown for
  confirmation. Reject ambiguous endpoints with 422 (Harden; Build uses the top result and shows
  the resolved label). Trip creation, single-waypoint lookup, and resolution suggestions are
  synchronous and may wait for bounded Google/Gemini calls. Imports and builds enqueue jobs and
  return before provider calls.
- Names are trimmed, 1–60 characters; trip names 1–100; imported text ≤ 100,000 characters total
  per trip (413 on overflow, never silent truncation); messages 1–10,000 characters. Dates are ISO
  dates with `end_date ≥ start_date`, at most three inclusive days, and one valid time zone.
- Build requests: the UI generates a fresh `Idempotency-Key` per click. If a generation is already
  queued/running for the trip, a same-preset request returns 202 with that generation; a different
  preset returns 409 `plan_in_progress` with its ID. Reusing a key with different parameters
  returns 409. While a build runs, show the requested preset separately from the current plan's
  preset. Failed jobs leave `trips.current_plan_id` and `budget_preset` unchanged.
- The web API assigns `source = web` to anything a member creates; callers cannot create planner
  or system rows.
- `imessage/*` and `channels/imessage` routes accept only `Authorization: Bearer <API_TOKEN>`;
  the relay is the only caller. Reactions map `love → in`, `like → ok`, `dislike → out` and apply
  only when `target_guid` is a stored message whose `source_message_ids` link it to exactly one
  place; otherwise they are `skipped`. `added: false` removes that member's vote if it is the same
  kind. Other tapbacks (😂 ‼️ ❓) are ignored.
- Errors are `{error: {code, message}}`, optionally with `plan_id` or `generation_id`. Use 404 for
  missing resources, 409 for revision and job conflicts, 413 for oversize imports, 422 for
  validation and cross-trip references, 429 for rate limits (Harden), and 503 for unavailable
  upstream services during synchronous calls. Never send raw upstream errors or keys to the browser.

### Plan JSON (`plans.content`)

Extends the scaffold's `PlanContent` (`title`, `graph`, `assumptions`, `open_questions`,
`warnings`). Node `id` is the local `places.id` UUID for stops, and the literals `"start"` and
`"end"` for origin and destination, so votes, tasks, and check-ins join by ID. `place_id` is the
Google place ID. The following is a structural example, not verified travel data.

```json
{
  "title": "Big Sur weekend",
  "budget_preset": "comfortable",
  "currency": "USD",
  "timezone": "America/Los_Angeles",
  "derived_stale": false,
  "graph": {
    "nodes": [
      {"id": "start", "kind": "place", "role": "start", "quest": "main",
       "title": "Resolved origin", "place_id": "origin-id", "lat": 0, "lng": 0},
      {"id": "place-uuid", "kind": "place", "role": "stop", "quest": "main",
       "title": "Resolved place name", "place_id": "ChIJ...", "lat": 0, "lng": 0,
       "category": "do", "arrive": "2026-10-17T11:20:00-07:00",
       "depart": "2026-10-17T12:05:00-07:00", "duration_min": 45,
       "est_cost": [0, 10], "cost_basis": "App-configured activity range; per adult",
       "hours_status": "unknown", "source": "group",
       "why": "Three members voted I'm in; Maya: \"we HAVE to hit McWay Falls\".",
       "source_message_ids": ["message-uuid"], "owner_member_id": null, "notes": ""},
      {"id": "side-place-uuid", "kind": "place", "role": "stop", "quest": "side",
       "anchor": "place-uuid", "title": "Resolved bakery", "place_id": "ChIJ...",
       "lat": 0, "lng": 0, "category": "eat", "detour_min": 14, "est_cost": [10, 20],
       "cost_basis": "App-configured food range; per adult", "hours_status": "unknown",
       "source": "suggested", "why": "Near the leg after the falls; one member voted Sure.",
       "source_message_ids": [], "owner_member_id": null, "notes": ""},
      {"id": "end", "kind": "place", "role": "end", "quest": "main",
       "title": "Resolved destination", "place_id": "destination-id", "lat": 0, "lng": 0}
    ],
    "edges": [
      {"id": "e1", "source": "start", "target": "place-uuid", "kind": "travel",
       "drive_min": 140, "distance_m": 150000, "polyline": "encoded-leg-polyline"},
      {"id": "e2", "source": "place-uuid", "target": "end", "kind": "travel",
       "drive_min": 55, "distance_m": 60000, "polyline": "encoded-leg-polyline"},
      {"id": "e3", "source": "place-uuid", "target": "side-place-uuid", "kind": "detour",
       "detour_min": 14}
    ]
  },
  "days": [
    {"date": "2026-10-17", "start_at": "2026-10-17T09:00:00-07:00",
     "end_at": "2026-10-17T13:00:00-07:00", "node_ids": ["start", "place-uuid", "end"]}
  ],
  "per_person_estimate": [0, 10],
  "estimate_scope": "food_and_activities_main_quest",
  "estimate_is_partial": false,
  "unpriced_node_ids": [],
  "excluded_costs": ["lodging", "fuel", "tolls", "parking", "taxes", "tips", "side quests"],
  "conflicts": [
    {"node_id": "place-uuid", "kind": "split_vote",
     "detail": "2 I'm in, 1 Skip (Sam)."}
  ],
  "assumptions": ["One-way route", "Daily window 09:00–19:00", "Costs per adult"],
  "open_questions": [],
  "warnings": ["Opening hours are unverified for this stop"],
  "changed_from_previous": []
}
```

- Stop nodes always carry a real local place UUID; `source` is `group|suggested|added`; `why` is
  nonempty for nodes in the questline. `quest` is `main|side`; side nodes have an `anchor` that is a
  main node ID or `"start"`. `hours_status` is `verified|unknown` and means schedule compatibility
  with returned hours, not guaranteed access. `est_cost` is a per-adult range or `null`; Stay nodes
  use `null`. `detour_min` is a nonnegative integer or `null`.
- Edges: `travel` edges form a single path `start → … → end` through main nodes in order, each with
  its own polyline so the map follows the selected stops; `detour` edges connect a main node (or
  `start`) to a side node. Edge IDs are unique; edges reference existing nodes; no self-edges.
- All timestamps are ISO 8601 with offsets. Days appear in trip-date order; each day starts at the
  previous day's endpoint (the first at `start`), and the final day ends at `end`. Include every
  driving leg even when a day has no visits.
- `per_person_estimate` sums known main-quest food/activity ranges; `unpriced_node_ids` lists
  included food/activity nodes with unknown costs; `estimate_is_partial` is true when that list is
  nonempty. `changed_from_previous` is a code-generated list of factual added/removed/promoted/
  demoted-node and estimate changes versus `previous_plan_id`; the first plan has an empty list. If
  a rebuild changes nothing, say so. Never promise that every preset switch lowers the estimate.

## 11. Chat platform adapters

### 11.1 iMessage bot (Build)

The group keeps talking in their real iMessage group. A bot account in that group reads along and
feeds the trip; the web app is where the organized version lives. **The bot is silent**: it posts
only when someone sends a `@questline` command, plus the one-time link notice (§6). The goal is to
declutter, not to add another voice to the chat.

**How it runs.** A team MacBook stays awake on power with Messages.app signed into a dedicated bot
Apple ID (email-only is fine). The relay (`backend/src/questline/integrations/imessage/relay.py`,
run with `uv run python -m questline.integrations.imessage.relay`) keeps one long-lived
`imsg rpc` process (JSON-RPC over stdio) for both watching and sending. It implements the
scaffold's `ChatAdapter` protocol (`fetch_transcript` = `imsg history`, `post_plan_link` =
`imsg send`). It needs Full Disk Access and Automation → Messages for the terminal that runs it.
No SIP changes and no IMCore injection.

**Demo setup (decided 2026-10-10): self-account mode.** Apple wouldn't create a new bot Apple ID,
so the relay runs on Max's MacBook and personal Apple ID with `RELAY_SELF_HANDLE` set to his
handle. Rows "from me" are then either Max typing (from the Mac or his phone), which is forwarded
as his messages and votes, or echoes of the relay's own replies, which are dropped. Replies start
with "🧭 Questline:" so the group can tell them apart. A dedicated bot Apple ID (no
`RELAY_SELF_HANDLE`) remains the cleaner setup when one is available.

**Inbound.**

1. `watch.subscribe` streams new rows with `--reactions`. Drop echoes and rows from chats with no
   linked trip. With a dedicated bot ID every `is_from_me` row is an echo; in self-account mode
   only `is_from_me` rows matching a reply sent to that chat in the last 5 minutes are. Persist the last `rowid` locally and resume with
   `--since-rowid` after a restart.
2. Messages starting with `@questline` are commands (below) and are not forwarded for extraction.
3. Other text messages are buffered per chat and flushed to `POST /trips/{id}/imessage/batch`
   every ~15 seconds or 20 messages, whichever comes first. Each flush is one `imports` row, so
   extraction, dedupe by `external_id = guid`, and evidence quotes work exactly as for pasted chat.
4. Senders are upserted as members by `imessage_handle`; `name` is `sender_name` from the Mac's
   Contacts if available, otherwise the handle until they send `@questline I'm <name>`.
5. Tapback rows (`is_reaction`, `reaction_type`, `is_reaction_add`, `reacted_to_guid`) go to
   `POST /trips/{id}/imessage/reactions` and become votes (§10 rules).
6. Inline replies (`thread_originator_guid`) are stored like any message; when the parent mentions
   a place, the reply counts as evidence for that place. No separate thread UI.

**Relay/backend contracts:**

- `@questline I'm <name>` uses `PATCH /trips/{trip_id}/imessage/members/{handle}` (§10).
  The relay treats 404 as "no member yet" and sends the chosen name as `display_name` on later batches.
- `imessage/batch` accepts optional `reply_to_guid`, forwarded from `thread_originator_guid`.
  Persist it and resolve the parent only within the same trip, including out-of-order arrivals.
  A reply to a single-place message is evidence for that place; it never becomes an inferred vote.
- `@questline import last N` and the `ChatAdapter` (`fetch_transcript`/`post_plan_link`) wrapper
  are deferred with the §18 decision; the relay sends through `imsg rpc` directly.

**Commands** (main group only; any participant may send them):

| Command | Relay action | Bot reply |
| --- | --- | --- |
| `@questline link <trip_id or share link>` | `POST /trips/{id}/channels/imessage` (a pasted `…/t/<trip_id>` link is reduced to its ID; the live trip's *Link iMessage* button copies this command) | One-time notice: reading this chat for *<trip>*, messages go to Google Gemini, `@questline unlink` to stop, plus the trip link |
| `@questline build [shoestring\|comfortable\|treat]` | `POST /trips/{id}/plan-generations`, poll the generation | "Building…" then "Questline ready: N main quests, est. $X–Y/person (food + activities). <link>" or the sanitized failure; a 503 `provider_unavailable` gets "Plan building isn't available yet. Waypoints and votes are on the map: <link>" |
| `@questline add <place>` | `POST /trips/{id}/places {query}` | "Added <resolved name> · <link>" or "Couldn't find that place — try adding the city." |
| `@questline link` (no ID) | — | The trip link |
| `@questline I'm <name>` | Update the sender's member name | "Got it, <name>." |
| `@questline import last N` | `fetch_transcript` → `imessage/batch` (N ≤ 300) | "Imported N messages · <link>" |
| `@questline unlink` | `DELETE /trips/{id}/channels/imessage` | "Stopped reading this chat. The trip is still on the map: <link>" |
| anything else | — | Short usage help (Stretch: Q&A) |

Trips are created on the web (§3 step 1) so origin/destination validation stays in one place; the
group then links with the trip ID from the share link.

**What `imsg` can't do without SIP off (not used):** inline replies from the bot, edit/unsend,
typing indicators, text formatting, native polls, creating groups, adding members. A person adds
the bot to the group. `send` returns when AppleScript runs, not on delivery; confirm by seeing the
bot's own row come back through `watch`.

**Limits to state honestly in the demo:**

- Every participant must be on iMessage; an SMS/Android member turns the group into MMS, which the
  email-only bot account can't join.
- One Mac is a single point of failure: it must stay awake and online with Messages signed in.
- In self-account mode the bot's replies come from Max's account (prefixed "🧭 Questline:"), and
  the relay runs inside his personal Messages; it forwards only chats someone explicitly linked.
- The bot sees only messages sent after it joined, and only reads them after `link`.
- Names are phone numbers/emails unless the Mac's Contacts know them or members send `I'm <name>`.

### 11.2 Other platforms (later)

Because imports go through `messages/batch` and the tables already carry `source`, `external_id`,
`discord_channel_id`, and `discord_user_id`:

- **Input-only:** a bot in a Discord channel forwards messages to the backend; waypoints appear on
  the map and the bot posts the trip link.
- **Two-way:** the bot posts build results and conflict prompts back to the channel; must prevent
  echo loops and verify consent and permissions. Chat participation must be visible and opt-in;
  never silently collect chats or send them to Gemini without consent. Estimate after the
  hackathon.
- **WhatsApp:** the official Cloud API Groups feature requires an Official Business Account and
  caps groups at 8; an unofficial client (e.g. Baileys) works but risks a number ban. Fallback only.
- **Hosted iMessage providers** (Blooio, Linq, Sendblue): real phone numbers and SMS/RCS fallback
  for Android members, but paid, and group support varies by plan. Evaluate after the hackathon.

## 12. Team and roles

| Person | Role | Owns |
| --- | --- | --- |
| [Name] — React, CSS, Python | **Frontend / map lead** | Map rendering (markers, solid main-quest polylines, dotted side quests, badges, fit bounds), side panel tabs, waypoint card, vote UI, Import sheet, Create/Join with member tokens, polling hook and optimistic updates, operations UI (promote/demote/reorder/drop), quest log, Vercel deploy, demo video |
| [Name] — database | **Database / backend lead** | Migrations (rename `conversations` → `trips`, new tables in §9), member-token auth, `GET /trips/{id}` state endpoint and revision bumping, import parsing and `messages/batch`, votes, tasks, check-ins, accept, Procrastinate wiring and in-process worker fallback, backend deploy, seed script (§20), integration tests |
| [Name] — graphing | **Graph / planning lead** (`services/plan_generation.py`, `providers/maps.py`) | Candidate scoring, quest graph construction (nodes/edges/days), Routes API legs and polylines, timeline, detour calculation, suggested side quests, estimate, conflict detection, `/operations` apply-and-recompute, `changed_from_previous`, `FakeMaps`. Pure functions with the plan JSON as input/output; no HTTP or UI code |
| [Name] — AI behavior | **AI lead** (`providers/planner.py`, extractor, resolutions) | Gemini provider with structured output: place extraction from pasted chat, main/side selection and ordering with grounded "why" notes, resolution options for contested waypoints, prompt tuning against the seed chat, guardrails for untrusted transcript text, honesty rules in prompts and validators, `FakePlanner`/`FakeExtractor`; owns the demo chat content |

**iMessage relay owner: TBD (§18).** The relay is an API client with no UI and no model code;
the backend lead owns its five endpoints (§10), and whoever owns the relay Mac runs and babysits
it during the demo.

Shared: agree on §9 and §10 in the first hour and record changes here first. Until real providers
land, every track runs on the fake providers. The graph lead and AI lead agree on the planner output
contract (`{main, side, why}`) before writing prompts or graph code. Pitch and submission page are
split between the frontend and AI leads at feature freeze.

Why this split: the critical path (extraction, graph/route math, AI behavior, UI) is spread across
four people with clear input/output boundaries, so nobody blocks on anyone else's provider.

## 13. Timeline (vertical slice first)

The rule: get a crude version of the whole flow (import → waypoints → votes → questline → accept →
check off) working early, then improve each step. Something must be demoable from Saturday afternoon
onward.

| When | Goal |
| --- | --- |
| Sat 9–10 AM | Branch from `main`; §9/§10 confirmed; migration for new tables started; fake providers stubbed; map renders hard-coded waypoints; both apps deployed saying hello. **iMessage spike (1 h cap):** on the relay Mac, `imsg chats --json` lists the test group and `imsg send --chat-id …` posts into it. If the spike fails, drop item 7 to Stretch and keep pasted import |
| 10 AM–2 PM | **Walking skeleton.** Create/join with member tokens; add waypoint by search; trip-state polling; votes with tallies on markers; *Build* → Level 0 questline with a solid main-quest line; seed script posts the demo chat and votes (extraction may still be fake) |
| 2–8 PM | Real extraction from pasted chat with evidence quotes; side quests dotted with anchors; waypoint card; `split_vote` conflicts and badges; `/operations` with recompute (promote/demote/reorder/drop); *Accept*. **iMessage:** relay watches the test group, `link`, and live batches land as waypoints |
| 8 PM–12 AM | Level 1: detour minutes, suggested side quests, budget presets, estimate, change highlights; *Resolve* options via Gemini; quest log (owners, tasks, check-offs, next up); full deploy. **iMessage:** tapback votes, `build` / `add` replies |
| 12–6 AM | Sleep in shifts; bug fixes |
| Sun 6–10 AM | Acceptance checks (§5) on the deployed app with two devices; then Harden items (§19) in order; then Stretch |
| Sun 10 AM | Feature freeze. Deploy, record a backup demo video |
| 10 AM–2 PM | Polish, project submission write-up, pitch rehearsal |
| 3 PM | Submit |

## 14. Prep checklist before the build

- [ ] Read the actual hackathon rules and confirm what preparation is permitted before building.
- [ ] Google Cloud project with billing; enable Places API (New), Routes API, Maps JavaScript API.
      Create two keys: a browser key restricted to the site, and a server key for the backend.
- [ ] Google AI Studio API key (Gemini); verify a supported model and record it in `GEMINI_MODEL`.
- [ ] Supabase project (used as PostgreSQL only); connection URI in `backend/.env`; migrations run.
- [ ] Vercel and Render accounts; deploy the FastAPI service; test the wake-up delay; decide whether
      the worker runs as a separate service or in-process (§8).
- [ ] All four members added to the GitHub repo; everyone can run `npm run dev` from `frontend/` and the backend
      checks in the README.
- [ ] Pick a one-to-three-day demo route, check endpoint/place resolution and API access, and write
      a realistic demo chat (`demo/trip.json`) using disposable data.
- [ ] iMessage: choose the relay MacBook; create the bot Apple ID now (new IDs can sit on
      "waiting for activation"); sign it into Messages on that Mac (or a second macOS user that
      stays logged in); `brew install steipete/tap/imsg`; grant Full Disk Access and Automation →
      Messages to the terminal; make a test group of the iPhone teammates plus the bot.

## 15. Environment variables

Frontend (`frontend/.env.local`): `VITE_API_URL`, `VITE_GOOGLE_MAPS_BROWSER_KEY`.

Backend (`backend/.env`): `DATABASE_URL`, `APP_ENV`, `API_TOKEN`, `CORS_ORIGINS`,
`PLANNER_PROVIDER` (`fake|gemini`), `MAPS_PROVIDER` (`fake|google`), `GEMINI_API_KEY`,
`GEMINI_MODEL`, `GOOGLE_MAPS_API_KEY`, `MAX_TRANSCRIPT_CHARS`, `RUN_WORKER_IN_PROCESS` (`true` for
single-process demo hosting).

iMessage relay (env on the relay Mac only): `QUESTLINE_API_URL`, `API_TOKEN`, `WEB_BASE_URL`
(for links in replies), `IMSG_BIN` (default `imsg`), `RELAY_STATE_PATH` (stores the last
`rowid`, the chat → trip cache, and `I'm <name>` names), `RELAY_FLUSH_SECONDS` (default 15),
`RELAY_FLUSH_MAX` (default 20), `RELAY_SELF_HANDLE` (optional; the owner's phone or email in
self-account mode, §11.1). Put them in `backend/.env.relay` (template:
`backend/.env.relay.example`).

Never commit `.env` files. The frontend bundle contains only the browser Maps key and the API URL;
never `API_TOKEN` or the database URL.

Demo hosting note: free web services spin down after idle periods. Send a health-check request a
few minutes before judging, confirm `VITE_API_URL` points to the live backend, and keep the local
stack plus the recorded demo as fallbacks.

## 16. Demo script (~3 minutes)

1. **Problem (20 s):** show a staged chaotic group chat screenshot. "300 messages, no plan."
2. **Create + import (30 s):** create the trip, paste the chat. Waypoints land on the map with
   quotes: "Nobody organized anything, and here's every place, on a map, with who said it."
   **With the iMessage bot:** mirror a phone showing the real group. Send `@questline link …`,
   then two teammates text normally ("we HAVE to hit McWay Falls"); pins drop on the projected map
   within ~30 seconds (15 s relay flush + extraction). Someone ❤️s a message and the vote tally moves. End with `@questline build`
   in the chat and the questline appearing on the map. Pasting stays as the fallback beat.
3. **Vote (30 s):** two teammates vote on their phones. Tallies appear on markers. One waypoint
   turns contested (⚠).
4. **Build (40 s):** tap *Build*. Solid main quest routed through the committed stops with times;
   dotted side quests with "+N min"; grounded "why" notes; est. food + activities per person with
   exclusions.
5. **Resolve (30 s):** tap the contested waypoint → *Resolve* → three options → pick "make it a side
   quest". The map updates for everyone. Switch to Shoestring; show real swaps and estimate changes.
   Choose demo candidates that exercise a real affordable alternative; do not force a fake drop.
6. **Follow through (20 s):** *Accept*. Quest log: assign an owner, check off the first quest,
   "Next up: McWay Falls — leave by 11:20."
7. **Close (10 s):** future — Discord bot, live check-ins, split the bill.

## 17. Risks and fallbacks

| Risk | Fallback |
| --- | --- |
| Extraction misses or mislabels places | Skip ambiguous results and list them under "Couldn't place"; anyone can add a waypoint by search. Tune prompts against the seed chat early |
| Pasted chat formats vary | Build supports `Name: text` lines only; show the parsed preview before import; the seed file is the demo path |
| Live voting on stage goes wrong | Seed script casts the scripted votes into a fresh trip; it produces the same state every time |
| Plan generation is slow | Show a "building your questline…" state with the last plan still visible; pre-warm with one build before the demo |
| Routes API fails during an edit | Save the decision, keep previous derived values, mark `derived_stale`, warn; next edit or build recomputes |
| Google API costs or quota | Narrow field masks, per-trip place ID reuse, request limits and quota alerts |
| Hosting can't run a separate worker | `RUN_WORKER_IN_PROCESS=true` starts the worker inside the API process |
| Wi-Fi or deploy fails during the demo | Backup video recorded at feature freeze; local stack as a second fallback |
| Running out of time | Cut all stretch work first. Keep change highlights as a plain text list and the dotted detour as a straight dashed line; spend remaining time on import → vote → build → resolve → accept → check off |
| A provider times out or the server restarts | Mark the job failed, retain waypoints, votes, and the last successful plan, and allow a new request |
| Relay Mac sleeps, loses Wi-Fi, or Messages signs out | `caffeinate -dims`, power plugged in, lid open; relay resumes from the saved `rowid`; pasted import and the seed script are the stage fallback |
| New bot Apple ID is throttled or stuck activating | Create it before the build; fall back to a teammate's spare Apple ID, or pasted import |
| Demo group has an Android/SMS member | The demo group is iPhone-only (bot + iPhone teammates); the Android teammate drives the web map |
| Bot spams the chat | Silent by default; replies only to commands; one reply per command |
| Map rendering jank on mobile | Cap markers to the trip's waypoints; render polylines once per plan revision; bottom sheet instead of sidebar |

## 18. Open decisions

- Rename `conversations` → `trips` in a migration (assumed here) vs. keeping the table name and
  aliasing in code.
- Polling interval and whether to add server-sent events during the hackathon or leave it as Harden.
- Whether the demo backend runs API and worker as one process or two services.
- Demo trip destination and route; the demo chat content.
- Whether constraint extraction (Stretch 1) is promoted to Build if extraction lands early.
- Vote labels and icons (*I'm in / Sure / Skip* assumed here).
- iMessage bot priority: Must-have item 7 (assumed here) vs. Stretch, if it competes with
  *Resolve* or the quest log for time.
- ~~Who owns the iMessage relay, which MacBook runs it, and whose spare Apple ID is the fallback.~~
  Decided 2026-10-10: Max owns the relay; it runs on his MacBook and Apple ID in self-account
  mode (§11.1). A spare bot Apple ID is still welcome if a teammate has one.
- Bot command prefix (`@questline` assumed) and display name in the group.
- Whether the bot ever posts unprompted (assumed **no**, apart from the link notice). A quiet
  "Added 3 places · <link>" digest is possible later.
- Whether `@questline import last N` (reading pre-link history on explicit request) is in Build
  or Harden.

## 19. Harden if there's time

Everything not listed here is a Build requirement. These items are correct long-term behavior from
§8–§10, but each has a simpler Build version that's acceptable for the demo. Work through them in
this order after the acceptance checks pass.

| # | Harden rule (where specified) | Build version for the demo |
| --- | --- | --- |
| 1 | One active generation per trip via a partial unique index; same-preset duplicate returns the running job, different preset returns 409 (§9, §10) | Frontend disables *Build* and the preset switcher while a generation is queued/running; backend returns the existing running job if one exists |
| 2 | Level 2 generation: opening-hours checks, daily-window feasibility, demote-and-retry, `does_not_fit`/`hours` conflicts (§8) | Level 1 plan with `hours_status: "unknown"` and a warning |
| 3 | Stalled-job recovery; mark interrupted jobs failed on worker restart; per-job timeouts (§8) | Timeouts on Gemini/Google calls; a stuck job is retried by building again with a new key |
| 4 | Routed dotted detour polylines for side quests (§4) | Straight dashed line from the anchor waypoint to the side quest |
| 5 | Server-sent events for live updates (§8) | 3-second polling with the revision short-circuit |
| 6 | WhatsApp / iMessage export parsers (§8) | `Name: text` lines only, with a parsed preview |
| 7 | Database-level cross-trip constraints (§9) | Backend checks that `member_id` and `place_id` belong to the trip on each write |
| 8 | Rate limits and 429s (§10) | Pydantic length limits only |
| 9 | Reject ambiguous origin/destination with 422 (§10) | Use Google's top result and show the resolved label on the trip page |
| 10 | Map imported authors to members (§8 extraction step 4) | Show the author name as written; `mentioned_by` stays null |
| 11 | Google content retention refresh/removal (§6) | Store place IDs and display fields; still show required Google attribution |
| 12 | Separate API and worker processes (§8) | Worker started in the API process when `RUN_WORKER_IN_PROCESS=true` |
| 13 | Full error-code table including 429 (§10) | `{error: {code, message}}` with 404/409/413/422/503 |
| 14 | Link an iMessage member to their web member (claim a handle from the browser) so web votes and tapbacks merge (§11.1) | iMessage members and web members are separate rows; tapbacks vote as the handle member |
| 15 | Tapbacks on messages that mention several places (§10) | Skipped; vote on the web or on a single-place message |
| 16 | Relay health check and auto-restart (launchd) (§11.1) | Run the relay in a terminal; restart by hand; resume from the saved `rowid` |

## 20. Seed script

A script that drives the real API as if a group were using the app. Uses: testing extraction
repeatedly, tuning prompts, filling the app with realistic data, and a demo fallback if live
interaction goes wrong. Owner: database/backend lead (§12). Write the demo chat during the
hackathon, not before. The scaffold's `backend/scripts/smoke.py` remains the API-level smoke test.

Location: `backend/scripts/seed_demo.py` and `demo/trip.json`.

```json
{
  "trip": {
    "name": "Big Sur weekend",
    "origin": "San Jose, CA",
    "destination": "Big Sur, CA",
    "start_date": "2026-10-17",
    "end_date": "2026-10-18",
    "timezone": "America/Los_Angeles",
    "organizer_name": "Maya"
  },
  "members": ["Sam", "Jordan"],
  "chat": "Maya: ok we HAVE to hit McWay Falls\nSam: parking there is rough tho\nJordan: Big Sur Bakery for breakfast?\n",
  "votes": [
    {"member": "Maya", "place": "McWay Falls", "kind": "in"},
    {"member": "Sam", "place": "McWay Falls", "kind": "out"},
    {"member": "Jordan", "place": "Big Sur Bakery", "kind": "ok"}
  ],
  "build": {"budget_preset": "comfortable"}
}
```

- `members`: joined through `POST /trips/{id}/members`; the organizer is created with the trip.
- `chat`: posted through `POST /trips/{id}/import`; the script waits up to 60 seconds for the import
  job to finish and prints the "Couldn't place" list (each one is an extraction miss worth fixing).
- `add_places` (optional): `[{"query": "..."}]`, each added through `POST /trips/{id}/places`;
  a miss prints a warning.
- `votes`: `place` is matched by name against the trip's waypoints; unmatched votes print a warning.
  A vote that already exists is not re-sent (the vote endpoint toggles), so reruns are safe.
- `build`: requests a generation with a fresh `Idempotency-Key` and polls until it succeeds or
  fails. The script ends by printing each new member's `X-Member-Token` and the trip link.

Usage:

```sh
# from backend/; --api defaults to $BASE_URL or http://localhost:8000, Bearer token from $API_TOKEN
uv run python scripts/seed_demo.py ../demo/trip.json
# creates a new trip, prints its link
uv run python scripts/seed_demo.py ../demo/trip.json --api <url> --trip <trip id> --skip-build
# seeds into an existing trip without building
```

The script uses only the public API (§10). Aim for about 30 messages from 2–3 people that mention
8–10 places, include one deliberately split vote, one *Add waypoint* via search, and end with a
build.
