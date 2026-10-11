# Level 1 completion on the merged planner

This extends the planner merged in #19, not the retired Level 0/1 engine. `QuestlinePlanner` still
selects membership; code orders the main quest geographically and uses category visit durations.
`Decisions`, `compose()`, server operations, Resolve options, owner/note preservation and the live
UI remain the existing design. No migration or dependency change is required. Restart API and worker.

## Reference-work checklist

The former `feat/level-zero-planning` / `feat/level-one-planning` branches were used as references:

| Capability | Current implementation |
| --- | --- |
| Core selection, routes, estimates, presets, operations and live UI | Retained from main |
| Bounded route suggestions and local-ID persistence | `services/suggestions.py`, worker registration sink |
| Request-time vote/evidence/price isolation | Private discovery overlay, unchanged stored snapshot |
| Price refresh, explicit-range preservation, endpoint billing masks | Places adapter, pricing helper, waypoint endpoint |
| Manual-waypoint-only builds and candidate/date guards | Generation endpoint and shared context validation |
| Detour caps, concurrency, deadlines and unrounded comparison | Shared `compose()` and route adapters |
| Grounded reasons | Gemini supplies validated candidate-specific message IDs; code renders text |
| Anchors, stop costs, coverage and preset change summaries | Extended existing `changes()` |
| Stay/overnight continuity and DST elapsed time | Shared build/edit scheduling; no invented transfers |
| Late/expired build preservation | Final save rechecks terminal generation status under the trip lock |

Not copied: the old engine classes, level switch, Gemini-controlled order/anchors/visit durations,
legacy empty mock generator, or blanket fail-on-AI/routing-outage policy. Main's disclosed vote and
straight-line fallbacks remain. Schedule overflow conflicts remain editable; no automatic demotion
or AI/routing retry is introduced. A main Stay requires a following trip date and arrival before
that morning; invalid Stay schedules fail with an actionable error (422 for structural edits).

## Optional calls and deadlines

Fake maps/routing remain the default and make no paid calls. Discovery needs real routing, a maps
provider and a registration sink. Direct planner use without a sink does not discover places.

| Environment variable | Default | Range |
| --- | --- | --- |
| `PLANNER_DETOUR_LIMIT` | 5 | 0–20 |
| `PLANNER_SUGGESTION_QUERY_LIMIT` | 2 | 0–2 |
| `PLANNER_SUGGESTION_LIMIT` | 4 | 0–4 |

Zero disables the corresponding feature. Limits are frozen in new generation snapshots; older queued
snapshots without limits use worker settings. Builds accept at most 100 candidates and one to three
inclusive dates. Real discovery uses one origin→destination route, then at most two Places queries
(cafes and tourist attractions), two results per query. Main routing retains chunking at 25
intermediates: at most four main Routes requests for 100 stops, plus at most five default detours
and one discovery baseline. An identical baseline/main route reuses success **or failure** rather
than charging for a retry. Disabled discovery, full candidate capacity, offline routing, or missing
sink never triggers the baseline lookup.

Google Routes requests have a 15-second deadline; main routing has 60 seconds overall. Discovery
baseline/query stages have 20/15-second outer bounds. Optional detours have a 60-second stage deadline
and concurrency two; uncomputed or failed detours remain `null`. `detour_min` is the ceiling of the
nonnegative difference of unrounded drive durations for A→S→B versus A→B. Main edge minutes are
rounded up independently. Detours exclude visit time, are local alternatives, and are not additive.
Builds have 180 seconds overall and structural recomputation 125 seconds. Provider calls happen
outside trip write locks. Timeouts/failures cannot overwrite a previously successful plan; a build
expired by the API cannot save a late result. External cancellation still propagates.

## Discovery facts and immutable group inputs

Results must be food/activity places inside the padded trip region, not endpoints or duplicate
Google IDs. Registration upserts real trip-local UUIDs in a short locked transaction. The overlay
uses the discovered provider facts, zero votes and empty evidence—not the mutable row returned by
an upsert. This remains true if someone added/voted on the same place after Build was clicked.
New discoveries are side quests in this build. A future build considers their then-current snapshot
votes normally. Omitted or failed-build discoveries can remain in Waypoints; discovery does not
roll back an earlier completed registration. Existing group/added sources are not overwritten in
storage merely because a discovery collides with them.

Gemini receives bounded quotes with IDs, actual named votes, coarse prices and budget targets. It
returns IDs only, not explanation prose or derived facts. Evidence must come from that candidate's
supplied quotes; malformed/foreign references trigger the disclosed vote-selection fallback. Code
renders actual votes and exact quote excerpts. Untrusted quote text is never treated as instructions.

## Prices and billing

`pricing.py` owns the existing tunable USD per-adult food/activity range table. Known Free is $0;
unknown/unspecified price levels stay unknown. Explicit supplied ranges survive coarse refreshes;
app-derived ranges are recomputed and cleared when a refreshed level is unavailable. Stay and
Along-the-way are not converted or included in the food/activity subtotal. Side quests have their
own optional food/activity range but never contribute to the main subtotal. Unpriced main
food/activity stops make the subtotal partial; no known costs yields `null`, not zero. Lodging,
fuel, tolls, parking, taxes and tips remain excluded. Presets are preferences, not daily spending
guarantees; unknown prices are never described as cheaper.

`POST /api/v1/places/{local-place-uuid}/price-refresh` takes the existing member/service auth. It
rejects cross-trip access before lookup, makes one Place Details request with `id,priceLevel`, updates
the waypoint and bumps revision. Only food/activity places qualify. Provider failure is sanitized
503 with no mutation. Refresh before Build: queued snapshots and existing plans are never rewritten.
Readding/reimporting a waypoint also refreshes its coarse pricing without overwriting explicit costs.
Build does not automatically refresh all unknown prices.

Requesting `priceLevel` invokes Enterprise pricing for waypoint Text Search/Place Details, even
when Google has no usable price. Endpoint resolution keeps the smaller mask without `priceLevel`.
Enable Places API (New) and Routes API and use a restricted server key. Set quotas; budget alerts
alone do not cap spending. These are broad app estimates, not menu/admission verification.

References: [search along route](https://developers.google.com/maps/documentation/places/web-service/search-along-route),
[Place Details fields](https://developers.google.com/maps/documentation/places/web-service/place-details),
[Text Search fields](https://developers.google.com/maps/documentation/places/web-service/text-search).

## Validation and remaining work

Tests cover discovery caps/deduplication, unsafe results, local IDs and post-request collisions,
provider calls outside trip locks, free/unknown/explicit prices, refresh authorization, immutable
plans/snapshots, candidate evidence, detour rounding/caps/deadlines, Stay/DST continuity and expired
builds. Run the README checks and full PostgreSQL suite against a disposable `_test` database.
Mocks/fake providers consume no Gemini/Google quota. Live discovery/selection/pricing/routing still
need an approved smoke test; the price-refresh endpoint currently has no dedicated UI control.

Level 2: opening hours, strict daily feasibility with bounded demote-and-retry. Gemini Resolve
and preserve-previous-derived-values/`derived_stale` on edit routing failure
remain separate work. Public real-provider deployment still requires Google attribution and
content retention/refresh/removal across waypoints, endpoints, snapshots and route content.
