# Questline

A shared map that turns a group's chat into a trip they will actually take. Every place anyone
mentioned becomes a waypoint; the group votes; Questline routes the committed stops into a main
quest, hangs the maybes off it as side quests, surfaces disagreements with grounded options, and
turns the accepted questline into a quest log the group checks off on the day.

The product and implementation spec is in [docs/SPEC.md](docs/SPEC.md).

## Stack and current scope

- **React + TypeScript + Vite** + TailwindCSS frontend scaffold at the repository root.
- **Python 3.12 + FastAPI**, Pydantic, SQLAlchemy, psycopg, and Alembic.
- **PostgreSQL**, hosted on Supabase for a shared environment or Docker locally.
- **Procrastinate** for durable PostgreSQL-backed background jobs; no Redis required.
- **uv** for dependencies, **pytest / Ruff / Pyright** for checks, GitHub Actions for CI.

The scaffold implements trip creation/joining → transcript ingestion → background generation →
editable draft → acceptance, with member-token access and revision-based trip polling.
Building a questline picks main and side quests from votes (or with Gemini, when enabled), then
code routes, times, prices and checks it; see [Building a questline](#building-a-questline).
Google Places (New) and Routes resolve places and drive times when explicitly enabled; fake
providers remain the default and make no paid calls.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before contributing, [docs/SPEC.md](docs/SPEC.md) for the
product requirements, data model, and target API contract, and [docs/architecture.md](docs/architecture.md)
for the scaffold's current boundaries, limitations, and suggested work streams.

## Frontend development

From the repository root, using Node.js and npm (also available in `nix develop`):

```sh
npm ci
npm run dev
```

Vite serves the frontend at <http://localhost:5173> by default. Run the backend separately using
one of the workflows below. `src/Root.tsx` picks the screen from the URL:

| Route | Screen |
| --- | --- |
| `/` | Create a trip (or resume the last trip this browser joined) |
| `/t/<tripId>` | Join by name, then the live trip, polled from the API |
| `/demo` | The offline San Francisco demo, on local data only |

Creating and joining need the backend. The live trip shows the waypoints with I'm in / Sure / Skip
votes, the map, the questline (build, reorder, promote/demote, drop, resolve, accept) and the quest
log (owners, tasks, check-offs), all shared through the API. Travel mode and constraints on the
create form are saved in this browser only; the backend doesn't store them.

### Talking to the API

The client calls same-origin `/api/v1/...`, and the Vite dev and preview servers proxy `/api` to
`http://127.0.0.1:8000`, so no CORS setup is needed locally. To change either side, set these in
`.env.local` and restart `npm run dev`:

```sh
# Dev/preview proxy target, for example when Compose uses API_PORT=58000. Never bundled.
QUESTLINE_API_PROXY_TARGET=http://127.0.0.1:58000
# Only when the frontend is served from a different origin than the API (no proxy).
# The backend's CORS_ORIGINS must then include the frontend's exact origin.
VITE_API_BASE_URL=https://api.example.com
```

Browsers authenticate with the member token returned by create/join, sent as `X-Member-Token`, and
stored per trip in local storage (`src/api/session.ts`). Never use `API_TOKEN` in the frontend.

Shared trip links have the form `/t/<tripId>`; anyone with the link can see the trip and join it
by name. Vite's dev and preview servers already serve `index.html` for every route; a static host
needs equivalent rewrites of `/t/*` and `/demo` to `index.html`.
`src/state/` holds the session hook (create, join, rejoin after a rejected token) and a trip
provider that polls `GET /trips/{id}?revision=N` every 3 seconds while the tab is visible.

### Frontend composition

`src/App.tsx` owns the demo's state, persistence, and actions. `src/trip/TripApp.tsx` is the live
trip's container: it reads `useTrip()` and passes plain props to the same panels, using adapters
such as `src/trip/tripHeadingAdapter.ts` so panels never see API types. Individual panels receive
typed props and action callbacks; the planning desk and overview compose panels through named slots.
See [UI composition](docs/ui-composition.md) for the component inventory, relocation examples,
and the styling boundaries to preserve when rearranging the page.

### Google map (optional)

The map view uses the Maps JavaScript API when a browser key is configured, and falls back to the
illustrated demo map when it isn't, so the frontend runs without a key. Create `.env.local` at the
repository root (gitignored) and restart `npm run dev`:

```sh
VITE_GOOGLE_MAPS_BROWSER_KEY=your-browser-key
# Optional: a cloud-styled map ID; defaults to Google's DEMO_MAP_ID
VITE_GOOGLE_MAP_ID=
```

`VITE_*` values are bundled into the browser, so use a key restricted by HTTP referrer to the
Maps JavaScript API. Never put the backend's server key, `API_TOKEN`, or `DATABASE_URL` in a
`VITE_*` variable. The map code lives in `src/features/map/`; `QuestMap` takes plain stop data
(`id`, `name`, `side`, `done`, `lat`, `lng`), so the rest of the UI can change without touching it.
Stops without coordinates are counted but not plotted. A live trip's map draws the plan's routed
legs (solid) and side-quest detours (dashed); the offline demo draws straight lines.

### Styling

New UI is styled with [Tailwind CSS](https://tailwindcss.com) v4. `src/styles/app.css` is the
single stylesheet entry: it defines the design tokens (`@theme` colors, fonts, and breakpoints)
and loads the older hand-written CSS (`src/App.css`, `src/styles/questline.css`) into a `legacy`
cascade layer beneath Tailwind's utilities, so a utility class always wins over a legacy rule.
To migrate a component, style it with utilities and delete its rules from `App.css`
(`src/components/AppHeader.tsx` is the first example). Tailwind's Preflight reset is not loaded
yet, so set things like button backgrounds explicitly.

Frontend checks and production preview:

```sh
npm run lint
npm run build
npm run preview
```

`npm run build` type-checks the frontend and writes the production build to `dist/`.
`npm run preview` serves that build locally; it is not a production deployment server.
Commit `package-lock.json` when dependencies change.

## Quick start: backend in Docker

Requires Docker with Compose v2. From the repository root:

```sh
docker compose up --build
```

This starts PostgreSQL, applies migrations, and runs the API and worker. Open:

- API documentation: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/health/live>
- Database connectivity: <http://localhost:8000/health/ready>

In Swagger's **Authorize** dialog, enter `local-development-only` as the bearer token.
The service token is for tooling/bots only. Create/join routes are public and return a member token;
use `X-Member-Token` for trip-scoped browser access. Never ship `API_TOKEN` in a frontend bundle.
Full plan replacement (`PATCH`) requires the service token; browsers edit plans through
`POST /plans/{id}/operations`.
In fake Maps mode, create trips using `San Jose, CA` and `Big Sur, CA` as endpoints—these are
explicit fixtures, not Google-verified results.
The Compose ports bind to localhost. Do not expose this development configuration publicly.

Compose intentionally uses its **local database**, not `backend/.env` or Supabase. No `.env` is
needed for this path. If ports are occupied, use, for example:

```sh
POSTGRES_PORT=55432 API_PORT=58000 docker compose up --build
```

`docker compose down` stops the services and keeps data. `docker compose down -v` also **deletes
local database data**. Rebuild after code changes, or use the native/reload workflow below.

## Nix development shell

With Nix installed and the `nix-command` and `flakes` experimental features enabled, run from the
repository root:

```sh
nix develop
cd backend
uv sync --locked
```

The shell provides Python 3.12, uv, PostgreSQL 17 tools (`psql`, `createdb`, etc.), Node.js for
Pyright, Git, OpenSSL, and Docker/Compose clients. It supports Linux on x86_64 and ARM64,
plus Apple Silicon macOS. `flake.lock` pins the tools; `backend/uv.lock` pins Python dependencies.

uv uses the Nix-provided Python rather than downloading an interpreter. On Linux, the shell also
provides the runtime library paths needed by binary Python wheels such as greenlet. Stay inside
`nix develop` when running the native backend, worker, or checks.

For automatic shell activation, optionally install direnv with nix-direnv integration, then run
`direnv allow` at the repository root. The committed `.envrc` uses this flake; generated `.direnv/`
cache files stay local and ignored.

Entering the shell does **not** install Python dependencies, load secrets, start Docker/Postgres,
or run migrations. You still need a running Docker daemon (or Docker Desktop on macOS) for the
Docker workflows. Configure `backend/.env` and follow either database setup below.

For a one-off check from the repository root:

```sh
nix develop --command bash -c 'cd backend && uv run pytest -q'
nix flake check
nix fmt flake.nix
```

Commit `flake.nix` and `flake.lock` together. When intentionally updating Nix tools, run
`nix flake update nixpkgs` and rerun the backend checks. Flakes in Git repositories only include
files known to Git; when testing newly added flake files before committing, stage them first.

## Development with uv and Supabase

Enter the Nix shell above, or install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
cd backend
cp .env.example .env
uv sync --locked
```

Edit `backend/.env`:

1. Set `DATABASE_URL` to your Supabase project's **Postgres connection URI**, not its HTTPS API URL.
2. Prefer a direct connection. If your network is IPv4-only, use the **session pooler on port 5432**.
   Do not use transaction pooling (port 6543) for this scaffold's worker/migrations.
3. Keep `?sslmode=require` on remote connections; URL-encode special characters in the password.
   For certificate verification, configure `sslmode=verify-full` with the appropriate CA.
4. Replace `API_TOKEN` with a shared, random demo secret, e.g. `openssl rand -hex 32`.
   Set `APP_ENV=production` for a deployed private demo; it rejects the default/short token.

The backend connects directly through SQLAlchemy; no Supabase SDK, anon key, or service-role API
key is needed. The database account must be able to create the `questline` schema and its tables,
functions, and triggers for initial setup. Run setup once per shared database:

```sh
# From backend/, with DATABASE_URL configured in .env
uv run alembic upgrade head
uv run python -m questline.jobs schema
uv run uvicorn questline.main:app --reload --host 127.0.0.1 --port 8000
```

For a single-process private demo, set `RUN_WORKER_IN_PROCESS=true` and do not launch a separate
worker. Work still uses the durable PostgreSQL queue. Otherwise, in a second terminal from `backend/`:

```sh
uv run python -m questline.jobs worker
```

Application and queue tables live in the private **`questline` schema**. Do **not** add it to
Supabase's exposed API schemas or grant browser/anonymous roles access. All clients use FastAPI.
Connections explicitly set the schema after connecting because session poolers may ignore startup
`search_path` options. If you installed the queue with older code, check that all
`procrastinate_*` tables and functions are in `questline`, not `public`; stop API/workers and
relocate existing queue objects before installing a second queue. Preserve queued jobs and data.
The service token grants access to all data. Member tokens are scoped to a single trip, but anyone
with a trip link can join by name. Use synthetic conversations; this is not private/account-based
identity, and retention/deletion controls are still pending.

Supabase hosts **only the database** in this setup. Deploy the API and worker separately as
long-running Python processes or containers. Inject secrets through your hosting provider; never
bake `.env` files into images. Configure explicit `CORS_ORIGINS` for your frontend.

See [Supabase connection guidance](https://supabase.com/docs/guides/database/connecting-to-postgres).
No remote Supabase project is created by this repository.

### Google Places development

Enable **Places API (New)** in a Google Cloud project with billing, set a quota/budget alert, and
restrict a server-side API key to that API. Set `MAPS_PROVIDER=google` and `GOOGLE_MAPS_API_KEY`
in `backend/.env`; never use a frontend `VITE_*` variable for this key. Restart the API afterward.

This enables create-trip endpoint resolution and manual waypoint search. Each search sends
one bounded Text Search request with an explicit field mask; creating a trip searches twice.
The Build implementation uses Google's top result and shows its resolved label—include city/region
in queries. Empty results stay unresolved; upstream failures return sanitized 503 responses.
Google's price level maps to the app's disclosed per-adult range table (`backend/src/questline/pricing.py`);
places without one stay unpriced, and opening hours remain unknown. Imported mentions use
trip-biased search and reject out-of-region or implausibly named matches. Mentions of the trip's own
origin or destination are skipped. Builds also call the **Routes API** (`computeRoutes`) for the
main-quest legs and each side-quest detour, so enable it for the same key.

Keep fake mode for normal development. Before publicly deploying real Places content, implement
Google attribution and the applicable retention/refresh/removal policy for display fields,
including copies in endpoint JSON and plan snapshots. Place IDs can be stored indefinitely;
other content cannot simply be retained forever. See [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies)
and [Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search).
Provider tests use mocked HTTP and never consume Google quota. Live calls require explicit setup.

### Gemini extraction development

To extract arbitrary named places, set `PLANNER_PROVIDER=gemini`, `GEMINI_API_KEY`, and
`GEMINI_MODEL` in the ignored `backend/.env`, using a currently supported structured-output
model from AI Studio. `gemini-3.1-flash-lite` has passed a small live extraction test with the
inline wire schema; older models such as `gemini-2.5-flash-lite` may reject new projects even when
listed by model discovery. Verify inference access, not just listing. Use `MAPS_PROVIDER=google`
plus its server-side key to resolve real places.
Restart both API and worker. Missing configuration returns 503 before saving/enqueuing imports.
The existing `PLANNER_PROVIDER` selector controls extraction and builds. Fake mode remains fully
supported for independent work.

Extraction sends imported message IDs and text to Gemini as untrusted data. Structured output
must cite supplied IDs and quote an exact place-name substring; no model votes are accepted.
The API uses a simple inline JSON schema; local Pydantic validation still enforces output limits,
allowed fields, categories, and evidence checks, rather than trusting schema conformance alone.
Google resolution uses a padded origin/destination box, rejects out-of-box and implausibly named
matches, and retains them as unresolved mentions. This conservative matcher can miss aliases;
manual search is the fallback. No provider call holds the trip write lock. Gemini has a 30-second
deadline and no automatic retries; extraction/resolution together have a 120-second deadline.
Failures preserve input and become sanitized failed import status; reimport to retry.

Configure quotas/budget alerts and use consented or synthetic chat only. No live provider calls
are part of the tests, including the real SDK transport test. See [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output).
Google attribution/content retention requirements above still block public real-data deployment.

### Native development with local Postgres instead

From the repository root:

```sh
docker compose up -d --wait db
```

Use the default database URL from `backend/.env.example`, then run the same migration, API, and
worker commands above. Each developer can use their own database; avoid running experimental
migrations against a teammate's shared database.

## Try the complete flow

With the API and worker running, from `backend/`:

```sh
uv run python scripts/smoke.py
```

For non-default endpoints or tokens, set `BASE_URL` and `API_TOKEN` in the command environment.
The script does not read `.env` automatically. It creates synthetic data, polls the generation,
edits the resulting draft, and confirms that a stale edit is rejected.

### Seed a demo trip

`scripts/seed_demo.py` fills the app with a realistic trip from `demo/trip.json`. It creates the
trip, joins members, imports the chat, adds places by search, casts votes and builds a plan, all
through the public API. From `backend/`, with the API and worker running:

```sh
uv run python scripts/seed_demo.py ../demo/trip.json
```

It prints the waypoints found, each mention it **couldn't place** (an extraction miss worth
fixing), each member's `X-Member-Token`, and the trip link. Other options:

```sh
# Seed into an existing trip without building (safe to rerun; existing votes are kept)
uv run python scripts/seed_demo.py ../demo/trip.json --trip <trip id> --skip-build
# Against another backend
BASE_URL=https://api.example.com API_TOKEN=... uv run python scripts/seed_demo.py ../demo/trip.json
```

`--web` (or `WEB_BASE_URL`) sets the host used in the printed link. To try a different chat, copy
`demo/trip.json` and edit it: `members` join the trip, `chat` uses `Name: text` lines, `votes`
match a waypoint by name (`in`, `ok` or `out`), and `build` is optional. On the fake providers
only McWay Falls and Big Sur Bakery resolve. If the planner is unavailable (for example, a missing
Gemini key), the script skips the build with a warning and still prints the member tokens and trip
link.

The same endpoints are available interactively at `/docs`; schemas use **snake_case** JSON fields.
Each new generation request requires an `Idempotency-Key` header; reuse it only to retry that request.
Same-preset requests return any active trip build; a different preset returns 409. Snapshots are
captured at request time, and successful generations create `draft` plans. Responses use
`{generation}` / `{plan}` envelopes and errors use `{error: {code, message}}`.

Existing databases need `uv run alembic upgrade head`: the alignment migration renames
`conversations` to `trips`, preserves messages/plans, and converts transcript snapshots. Legacy trips
can retain missing endpoints/dates; new creation requests require the spec fields. Drain old queued
jobs before upgrading because their task payload now expects the new snapshot schema.

Places, votes, imports, tasks, and check-ins are persisted and returned by trip polling.
Fake extraction recognizes `McWay Falls` / `Big Sur Bakery`; `Mystery Cafe` exercises unresolved
mentions. Import `Name: text` lines via `/trips/{id}/import`, or add either fixture via
`/trips/{id}/places`. Explicit votes, quest owners, notes and waypoint-keyed quest-log data
survive rebuilds.

## Building a questline

`POST /trips/{id}/plan-generations` snapshots the trip and queues a build (SPEC §8):

1. **Discover and pick.** Real routing can discover up to four optional cafes/attractions along
   the route through two bounded Places searches. Discoveries are persisted as waypoints, but never
   claim later group votes/evidence or become main quests in that build. Votes score *I'm in* +2,
   *Sure* +1, *Skip* −1. With no votes, existing waypoints are main quests; otherwise a score of 2+
   is main and the rest are side (a Skip never silently vetoes). With `PLANNER_PROVIDER=gemini`,
   Gemini picks membership and candidate-specific evidence IDs; code renders every "why" from
   actual votes/quotes, not free-form model claims. AI failures fall back to vote scores with a warning.
2. **Budget.** Main-quest picks above the preset's price level become side quests
   (Shoestring ≤ $, Comfortable ≤ $$, Treat any). The trip's endpoints are never stops.
3. **Route and time.** Code orders the main quest along origin → destination, gets legs and
   polylines from Google Routes (straight-line estimates in fake mode or if Routes fails, with a
   warning), and schedules visits (60 min meals, 75 min activities, 30 min stops along the way) in
   9 AM–7 PM windows, rolling into the next trip day when needed. A main Stay ends that day and
   resumes at 9 AM the next date; it is not a booking. Unplanned overnight gaps resume at the
   previous endpoint with a warning—lodging transfers are not modeled. A Stay on the last date is
   rejected; other schedule overflows remain visible conflicts pending Level 2 repair.
4. **Derive.** Side quests anchor to the leg with the smallest detour and get `detour_min`; the
   per-person estimate sums priced main-quest food and activities; conflicts flag split votes,
   over-budget picks and stops that run past the window; `changed_from_previous` compares with the
   plan that was current when the build was requested, including anchors, individual costs,
   price coverage and preset changes.

Builds support manually added waypoints without a transcript, one to three trip days, and at most
100 candidates. `PLANNER_DETOUR_LIMIT=5` caps optional detour lookups (0–20), with concurrency two
and a 60-second stage deadline. `PLANNER_SUGGESTION_QUERY_LIMIT=2` (0–2) and
`PLANNER_SUGGESTION_LIMIT=4` (0–4) bound discovery; zero disables it. New builds freeze these limits
alongside their inputs. Builds have a 180-second overall deadline; structural recomputation is
bounded to 125 seconds. No provider retries; identical discovery/main routes reuse results, including
failures. Offline builds never call Google or discover invented production places.

Refresh coarse prices before Build with `POST /api/v1/places/{local-place-id}/price-refresh` and a
member token. It makes one Place Details lookup, bumps trip revision, and preserves explicit cost
ranges; an unknown result clears old app-derived prices. Failure leaves state unchanged. Existing
plans and queued snapshots never change. Food/activity main quests alone contribute to the subtotal;
unknowns are not $0 and sides are optional extra costs. `priceLevel` triggers Enterprise pricing
for waypoint searches/details; endpoints omit it. Enable Places API (New) and Routes API, and set
hard quotas—budget alerts alone do not cap spending. See [Level 1 implementation](docs/level-one-planning.md)
for limits, billing, snapshot rules and remaining work.

`POST /plans/{id}/operations {revision, operations}` applies `set_quest`, `move`, `set_anchor`,
`drop`, `add`, `assign_owner` and `set_note`, recomputes every derived field, and returns the plan
(409 on a stale revision, 422 on an invalid edit). Structural edits return an accepted plan to
draft; owner and note edits keep it accepted. `POST /plans/{id}/resolutions {node_id}` returns up
to three options for a stop (promote or demote, swap for a nearby unskipped place of the same
kind, drop), each grounded in the actual votes and validated against the plan; apply one with
`/operations`. Resolution options are deterministic, not AI.

## iMessage relay

The silent iMessage bot (SPEC §11.1) is a relay process that runs on a team Mac and calls the API
with `API_TOKEN`. It reads the linked group through [`imsg`](https://github.com/openclaw/imsg)
(`imsg rpc`, JSON-RPC over stdio), batches messages to `/trips/{id}/imessage/batch`, posts tapback
votes to `/trips/{id}/imessage/reactions`, and replies only to `@questline` commands.

**Status:** the relay and all backend channel/batch/reaction/rename endpoints are implemented.
Tests exercise the real FastAPI endpoints and PostgreSQL with fake providers; a real-Mac test
against `imsg` is still required. Handles persist as separate trip members, replies retain parent
context as evidence (not guessed votes), and repeated tapbacks set rather than toggle votes.
Reactions targeting unresolved or multi-place messages are skipped; resend after extraction.

On the relay Mac (macOS 14+, Messages.app signed into either a dedicated bot Apple ID or, in
self-account mode, a team member's own Apple ID):

1. `brew install steipete/tap/imsg`, then `imsg --version`.
2. In System Settings → Privacy & Security, give the terminal that runs the relay **Full Disk
   Access** and **Automation → Messages**. Reopen the terminal.
3. `cp backend/.env.relay.example backend/.env.relay` and fill in the values.
4. From `backend/`: `uv run python -m questline.integrations.imessage.relay`

| Variable | Default | Purpose |
| --- | --- | --- |
| `QUESTLINE_API_URL` | required | API server root; the relay appends `/api/v1` |
| `API_TOKEN` | required | Bearer token for the relay-only routes |
| `WEB_BASE_URL` | required | Web app root for `/t/<trip_id>` links in replies |
| `IMSG_BIN` | `imsg` | Path to the `imsg` binary |
| `RELAY_STATE_PATH` | `~/.questline/imessage-relay.json` | Watch cursor, chat → trip links, `I'm <name>` names |
| `RELAY_FLUSH_SECONDS` | `15` | Max seconds a message waits before its batch is sent |
| `RELAY_FLUSH_MAX` | `20` | Messages per batch |
| `RELAY_SELF_HANDLE` | unset | Self-account mode: the owner's phone or email (see below) |

**Self-account mode.** With `RELAY_SELF_HANDLE` set, the relay runs on a member's own Apple ID:
their messages and tapbacks (from the Mac or their phone) count as theirs, echoes of the relay's
replies are ignored, and replies start with "🧭 Questline:". Keep "Start new conversations from"
on the same handle on the phone and the Mac. Without it, the relay assumes a dedicated bot ID and
ignores everything sent from its own account.

Delivery is at least once. The saved cursor never moves past an unsent row, and the backend
dedupes by message `guid`. Logs carry row IDs and counts, never message text.

**One person, two places.** Someone who joined on the web and then chats from iMessage should
send `@questline I'm <their web name>` in the group. If exactly one member with that name has no
handle yet, the handle joins that member, and anything the handle already did (messages, votes,
mentions, tasks) moves over; otherwise the handle's own member is renamed.

`@questline build` replies with the main and side quest counts, the estimate, up to two lines on
what changed since the last build, and any stops with split votes. `@questline add <place>` only
accepts results near the trip; include the city if it can't find one.

Manual check: `imsg chats --json` lists the test group;
`@questline link <trip_id>` in the group posts the notice; a normal message reaches the trip
within ~15 s; a ❤️ tapback on a message that names one place becomes an *I'm in* vote.

## Checks

From `backend/`:

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
```

Without `TEST_DATABASE_URL`, PostgreSQL integration tests are explicitly skipped. To run them,
create a **disposable** database (command below from the repository root):

```sh
docker compose exec db createdb -U questline questline_test
cd backend
TEST_DATABASE_URL=postgresql://questline:questline@localhost:5432/questline_test uv run pytest -q
```

**Integration tests drop and recreate the entire `questline` schema in the test database.** The
database name must end in `_test`. Never point tests at shared/demo data. CI runs all tests against
a disposable PostgreSQL service, checks migration upgrade/downgrade, and checks schema drift.

For a configured development database:

```sh
uv run alembic check
# After changing models, generate and REVIEW the migration:
uv run alembic revision --autogenerate -m "describe the schema change"
uv run ruff check --fix migrations
uv run ruff format migrations
uv run alembic upgrade head
```

Procrastinate's schema has a separate lifecycle: `python -m questline.jobs schema` is an idempotent
**initial installer**, not an upgrade tool. Its dependency is pinned. When upgrading it, apply its
[documented SQL migrations](https://procrastinate.readthedocs.io/en/stable/howto/production/migrations.html).

## Team workflow

Once this scaffold is reviewed and merged, create your own branch from the updated `main`:

```sh
git switch main
git pull --ff-only
git switch -c feat/your-feature
```

Keep credentials in your ignored `backend/.env`. Commit code, migrations, tests, and `uv.lock` changes,
not local database volumes or secrets. See [suggested work streams](docs/architecture.md#work-streams)
to divide implementation without duplicating responsibilities.

## Frontend visual theme

The starter screen is a responsive component preview with explicitly labeled demo data. It reuses
Paper UI `Card`, `Button`, and `Stamp`; the sample card's View quest action toggles local preview
text, not backend data. Shared styling lives in `src/styles/questline.css`, loaded after Paper UI.
The scoped adapter selectors for Paper UI's internal texture/label layers should be checked when
upgrading that package.

Kenney RPG expansion panels and buttons use sliced image borders with the original sprite fills
so edges retain their size as components grow. Quest cards pair a brown outer panel with a
notched parchment inset and raised grey buttons, matching the supplied pack reference. Parchment (`#ECE3CE`), leather (`#D3BF8F`), frame (`#B7916A`), ink (`#6D543A`),
and gold (`#CDA400`) come from the supplied pack. Forest, quest green, ocean blue, sage, and skipped
red retain their existing design values. A local, seamless SVG parchment texture (`public/ui/textures/parchment.svg`) adds warm mottling
and fine fibers to the page background, with CSS gradients for darker edges and a lighter reading
area. Component grain remains subtle. The frontend uses ordinary CSS; Tailwind is not configured
as a project dependency or Vite plugin. Stamp rings use
content-sized CSS ovals with padding to keep the strokes clear of text, including wrapped labels.

Black Chancery is self-hosted for headings, stamps, and buttons; body copy uses system sans-serif.
Assets and original notices are in `public/ui/kenney/` (Kenney, CC0) and `public/fonts/` (the supplied
Black Chancery font and its accompanying notes). No remote font service or new dependency is needed.
Paper UI's distributed stylesheet references an unused `Luminari-Regular.woff`; Vite may report that
unresolved reference during builds. This theme uses the supplied Black Chancery font instead.

## Live UI preview

Run `npm run dev -- --host 127.0.0.1 --port 5175` from this repository and open
http://localhost:5175. This serves the connected development checkout with hot reload.
The UI starts with trip setup and includes route review, tier rankings, member voting, and
a packing checklist. Changes save locally; shared backend synchronization is not connected.
Google Maps uses the existing Vite configuration when a browser key is configured.
