# Live trip uses the demo layout

Date: 2026-10-11 · Status: approved in chat, pending spec review

## Goal

A trip created on the web (`/t/<id>`) should look and work like the offline demo (`/demo`):
same shell, the same Map / Overview / Planning desk views and the same panels, filled with the
trip's real shared data wherever the backend has it. Panels with no backend support stay
device-local and say so. The demo itself is unchanged, and there are no backend changes.

Decisions made with the user:

- Same layout with live data, not full shared parity (no new tables or endpoints).
- The create page takes the demo's setup look but keeps only the fields the backend stores.
- The tier list sets the viewer's real vote.

## 1. Shell (`src/trip/TripApp.tsx`)

- Layout: `NavigationRail` on the left, then `PlannerHeader` (status, New trip, Link iMessage,
  Share trip), `TripHeading` (name, dates, avatars, **Import chat**), and `ViewNavigation` with
  **Map / Overview / Planning desk**.
- No Edit trip button, because there is no trip update endpoint. `TripHeading`'s `onSettings` is
  optional and is omitted here.
- The selected view is kept in `localStorage` per trip (key `questline-view:<tripId>`), with
  try/catch, and defaults to Map.
- **Map** renders today's `TripWorkspace`. It stays mounted on the other views (hidden with the
  `hidden` class, as the demo does), so the Google map does not reload on every tab switch. Its
  board tab becomes controllable (`tab`/`onTabChange` props), so the rail's quest-log button can
  open Map › Quest log.
- The Import chat dialog moves up to `TripApp`. `TripWorkspace` gets an `onImport` prop, and the
  heading opens the same single dialog.
- Overview and Planning desk cast votes through a new `src/trip/useVote.ts`
  (`mutate(api => api.vote(...))`, a pending list and an error notice). The Map view keeps its
  existing vote code.

## 2. Overview view (`src/trip/ui/TripOverview.tsx`)

Composed with the existing `Overview` layout and panels:

| Panel | Data |
| --- | --- |
| `OverviewHero` | Waypoint count. "Explore the map" switches to the Map view |
| `TripStats` | Main-quest count from the current plan. The estimate is the plan's per-person range (e.g. "$30–60") shown with the preset ("Comfortable preset"). Progress is checked-off main quests out of the total |
| `PartyCard` | Real members ("You, on this device" for the viewer) |
| Preparation | `TripEssentials`, saved per trip on this device |

- `TripStats` gains optional `totalLabel` / `budgetLabel` string props. The demo keeps its
  numeric props.
- `TripEssentials` takes an optional `storageKey`. It defaults to the current global keys so
  the demo is unchanged, and the live trip passes `…:<tripId>`. The panel is labelled
  "On this device".

## 3. Planning desk view (`src/trip/ui/TripPlanningDesk.tsx`)

Composed with the existing `PlanningDesk` slots:

- **conversation:** a live panel using the demo's classes. It shows the trip's messages (author
  and text, newest last, scrollable), and its button opens Import chat. It is read-only and
  there is no local draft.
- **route:** `RouteGraph` fed from the plan, using the existing `planStops` and `StopView`
  adapters. Main stops show arrival times. Side quests branch with "+N min" or "detour unknown".
  Without a plan it shows "Build the questline to see your route" with a Build shortcut that
  switches to Map › Questline. `RouteGraph`'s stop id is widened to `string | number`.
- **priorities:** `TierList`, with ids widened to `string | number`. The "Voting as" select
  renders only when `onVoter` is given, so the live trip omits it.
  - **Rank to vote:** S/A → `in`, B/C → `ok`, D/E/F → `out`. Places with no vote from the viewer
    go in an **Unranked** row.
  - **Displayed tier:** the tier last chosen on this device (`questline-tiers:<tripId>`) when it
    agrees with the viewer's current server vote. Otherwise it is the vote's default tier (`in`
    → A, `ok` → C, `out` → E). A tapback or a vote elsewhere therefore moves the place.
  - **Party votes:** the section under the tier list shows real tallies and casts real votes.
- **constraints:** `ConstraintsCard`, saved on this device under the create page's existing key
  `questline-device-constraints`, so preferences entered at creation show up here.
- **travel:** `TravelCosts` with optional real figures: total route distance (sum of travel
  edges' `distance_m`), total drive minutes, and the plan's per-person estimate. The demo's fixed
  sample numbers remain the defaults. Travel mode uses the create page's
  `questline-device-travel` key, and gas price uses `questline-device-gas`.
- **location:** `LocationCard` unchanged.

Pure logic goes in `src/trip/adapters.ts` or a new `src/trip/deskAdapters.ts`: tier↔vote
mapping, displayed-tier resolution, route totals and the stat labels.

## 4. Create page (`src/features/trip-setup/CreateTripPage.tsx`)

- The page already uses `SetupPage`, with a "Your adventure" card and a "Your preferences" card
  (travel mode and restrictions, saved on the device). Both cards stay.
- Add a **"What happens next"** list under the intro. Steps: create the trip → tap **Link
  iMessage** and send it in your group → places appear as you chat → vote or rank → **Build**.
- "Resume your trip" and "Try the demo" stay.

## Error handling

- Vote failures use the existing notices and the existing rollback behaviour of
  `mutate`/polling.
- Every `localStorage` read and write is wrapped in try/catch. A view renders correctly when
  storage is unavailable.
- Views without a plan show explicit empty states, never invented numbers.

## Testing

- The frontend has no test runner, and none is added (that would be a new dependency).
- Verification:
  - `npm run lint` and `npm run build`.
  - Backend suite unchanged.
  - A browser walkthrough on a live trip at desktop width and 375px:
    - Each view renders with real data.
    - A tier drag changes the vote in a second session.
    - A vote cast elsewhere moves the tier.
    - Device-local panels survive a reload.
    - `/demo` is unchanged.
    - The console shows no errors.

## Out of scope

Edit trip, shared constraints, budget or checklist, live location, and changes to `/demo`.
