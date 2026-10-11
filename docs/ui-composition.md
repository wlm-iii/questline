# UI composition

The app split preserves the current demo's appearance, copy, local-storage keys, and behavior.
It starts from `73709e7`; backend integration is separate. No store, context, or new dependency
is introduced.

## Where to make changes

- `frontend/src/App.tsx` owns shared state, `useSaved` calls, derived trip data, and actions. Route ordering,
  votes, acceptance, import matching, waypoint identity, and persistence stay here.
- `frontend/src/demo/types.ts` holds the current demo types, including `Stop`, `Trip`, `Constraints`,
  `PartyVotes`, and form input `WaypointInput`. These are demo contracts, not API models.
- `frontend/src/demo/data.ts` holds sample stops and coordinate fallbacks.
- `frontend/src/lib/useSaved.ts` contains the existing persistence hook, including storage failure handling.
- Layout components place panels. Content components render their props and report user actions.
  Components do not import `App`, a global store, API/session code, or sample data.

The existing `TierList`, `TripEssentials`, `QuestCard`, `AppHeader`, and `QuestMap` remain intact.
`TripEssentials` still owns its existing local packing/conditions persistence; this extraction
has not redesigned that component's state.

## Component inventory and props

Each extracted component exports its `NameProps` type beside its implementation. Callback props
accept ordinary values, not React setters or state updater functions.

| Area | Components | Data and actions |
| --- | --- | --- |
| Setup layout | `SetupPage` | `children`, `onBuildPlan`; owns the setup form and intro |
| Setup panels | `TripSetupFields`, `StartingPlaces` | Trip, constraints, travel mode, stops/count/cost; change fields or toggle inclusion |
| Planning layout | `PlanningDesk` | Named React-node slots: `conversation`, `route`, `priorities`, `constraints`, `travel`, `location` |
| Planning panels | `ConversationReader`, `RouteGraph` | Conversation/draft/stops or stops/completion; read text, select a place, review route, open details |
| Planning panels | `ConstraintsCard`, `TravelCosts`, `LocationCard` | Constraints or cost/mode/gas price with change callbacks; location card has no props |
| Overview layout | `Overview` | Named React-node slots: `hero`, `stats`, `party`, `preparation` |
| Overview panels | `OverviewHero`, `TripStats`, `PartyCard`, `PreparationCard` | Stop count/explore action; counts/cost/budget/progress; static crew; travel mode/settings/review/export actions |
| Map layout | `MapPanel` | Stops, mapped stops, selected ID, completion, zoom, provider flag, select/zoom/reset actions; `children` for independently positioned content |
| Map content | `IllustratedMap`, `PlaceCard`, `EmptyMap` | Map state/actions; selected stop/number/voter/vote and vote/view/side callbacks plus optional `className`; add action |
| Board | `QuestBoard` | Stops, main/displayed stops, selection/tab/filter/search, votes/owners/completion, accepted/budget state, and board actions |
| Board pieces | `StopRow`, `BudgetSummary` | One stop plus number/status/count/owner/reorder availability and callbacks; total/budget |
| Shell | `NavigationRail`, `TripHeading`, `ViewNavigation`, `AppFooter`, `Notice` | View/navigation actions; trip/settings/import actions; view/acceptance; static footer; message/dismiss action |
| Dialog container | `DialogHost` | `open`, `onClose`, `children`; owns the single native dialog, modal lifecycle, Escape/backdrop/close dismissal |
| Dialog content | `ImportChatDialog` | Transcript/matched stops, change/import actions |
| Dialog content | `TripSettingsDialog`, `WaypointDialog` | Trip or edited stop; save a trip or parsed waypoint form values |
| Dialog content | `PlaceDetailsDialog` | Stop, interested count, owner/note, owner/note/edit/side/remove actions |
| Dialog content | `RemoveWaypointDialog` | Stop, keep/remove actions |

## Moving panels

Move a panel's JSX and its props at the composition site. Keep the existing state and actions in
`App`; changing placement does not require moving persistence or rewiring the panel's internals.
A planning panel can also appear in a different view:

```tsx
<Overview
  hero={<OverviewHero stopCount={stops.length} onExplore={() => setView('Map')} />}
  stats={<TripStats mainCount={main.length} total={total} budget={trip.budget} completed={completed} />}
  party={<PartyCard />}
  preparation={
    <TravelCosts
      total={total}
      travelMode={travelMode}
      gasPrice={gasPrice}
      onTravelModeChange={setTravelMode}
      onGasPriceChange={setGasPrice}
    />
  }
/>
```

For a new layout, import these same panels directly and arrange them in your own grid or drawer.
There is no need to use the current `PlanningDesk` or `Overview` wrapper. Named slots describe
placement, not state ownership. Render a shared panel once unless duplicate controls are intended.

`PlaceCard` defaults to an ordinary `QuestCard` with no map positioning class. The current
composition explicitly passes `className="place-card"` to place it over the map. Omit that class
when placing it in normal document flow. `StopRow` receives its number and reorder availability
from its caller; it does not look up siblings or depend on where it is rendered.

Dialog content is separate from `DialogHost`; move the host in the tree or reuse a content component
inside another suitable container. `TripSettingsDialog` and `WaypointDialog` own their forms and
parse input before calling their save callbacks. `StartingPlaces` includes a submit button and
belongs inside `SetupPage`'s form, or another form connected to the build action.

## Styling boundaries

This pass changes no CSS or class names and adds no DOM wrappers between extracted pieces.
Legacy styles still include contextual rules such as `.place-card .vote-row`, `.desk-right`, and
`.overview-grid`. Repositioning is independent of state, but layout classes, inherited colors,
and form semantics still need consideration during the future visual redesign. Keep placement
styles in the composition/layout and content styles with the panel; do not add sibling selectors,
DOM queries, or parent navigation logic to content components.

Shared draft/input state stays in `App` so switching views or dismissing a dialog retains the same
values as before. Avoid moving that state into a panel without deciding whether unmounting should
reset it. The import preview receives matched stops from its caller, and the map receives prepared
coordinate data; neither chooses demo fixtures on its own.

## Validation of this extraction

- `npm run lint` and `npm run build` pass; `git diff --check` passes.
- Commands used Node 24.18.1 from the existing nvm installation because the system Homebrew Node
  could not load its `llhttp` library. Dependencies were installed with `npm ci` in the isolated
  worktree; package manifests and lockfiles are unchanged.
- Compared DOM structure, text, computed fonts/colors/display, and bounding boxes with a clean
  `73709e7` baseline for setup, map/board, planning desk, and overview at 390, 760, and 1440 pixels.
  All 12 comparisons matched within a 0.5-pixel tolerance; the footer has a subpixel text-width
  difference from JSX formatting.
- Browser checks covered setup/build, marker selection, voting/toggle-off/member switching,
  promotion/demotion, tier ordering via the selector, route reordering, search, acceptance,
  main-stop-only progress, refresh persistence, acceptance invalidation, sample chat matching,
  conversation reading, notes/owners, trip settings, waypoint add/edit/remove, travel mode,
  illustrated zoom/reset, and visible keyboard focus.
- All five dialog contents dismiss using the close button, Escape, and backdrop click.
- The illustrated map was exercised. The Google-map branch is preserved and type-checked, but
  live Google Maps was not enabled in the isolated worktree. Native tier drag/drop and storage
  failure simulation were not exercised. No automated frontend test runner is configured.
- The baseline's illustrated map also renders black triangles in this browser; this pre-existing
  rendering issue is preserved rather than folded into a behavior-preserving extraction.
