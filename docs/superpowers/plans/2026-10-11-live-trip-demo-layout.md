# Live Trip Demo Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give live trips (`/t/<id>`) the demo's shell and its Map / Overview / Planning desk views, filled with real shared data.

**Architecture:** Reuse the demo's presentation panels (they take plain props). Widen the few that are tied to demo types (numeric IDs, hard-coded crew) with optional, backwards-compatible props. Pure snapshot→view logic goes in `src/trip/deskAdapters.ts`. `TripApp` composes the shell, and keeps `TripWorkspace` (the existing map and board) mounted while hidden on the other views.

**Tech Stack:** React 19 + TypeScript + Vite, legacy CSS classes from `src/App.css`, the existing `useTrip()` context and `MemberApi`.

**Spec:** `docs/superpowers/specs/2026-10-11-live-trip-demo-layout-design.md`

## Global Constraints

- No backend changes. No new npm dependencies (that includes test runners).
- `/demo` must look and behave exactly as before. Every widened prop is optional and defaults to today's demo behaviour.
- Device-local storage keys:
  - `questline-view:<tripId>` for the selected view.
  - `questline-tiers:<tripId>` for chosen tiers.
  - `questline-conditions:<tripId>` and `questline-packed:<tripId>` for the checklist.
  - `questline-device-travel` and `questline-device-constraints` (shared with the create page).
  - `questline-device-gas`.
- Wrap every `localStorage` access in try/catch (`useSaved` already does).
- Tier → vote: S/A → `in`, B/C → `ok`, D/E/F → `out`. Vote → default tier: `in` → A, `ok` → C, `out` → E.
- The vote API **toggles**: sending the viewer's current vote kind again clears it. The tier list must never send the current kind.
- Checks for every task: `npm run lint` and `npm run build` must pass. The final task also runs the backend suite (unchanged) and a browser walkthrough.

## Review Focus

1. **Moving a place between two tiers that mean the same vote** (S→A). Expected: no API call, and the vote stays. Owned by Task 2 (`voteForRank`) and Task 5 (call site).
2. **A vote changed elsewhere** (a tapback, or the Map view) while the device has a saved tier. Expected: the place moves to the new vote's default tier. Owned by Task 2 (`displayedTiers`).
3. **A trip with no plan yet.** Expected: Overview and Planning desk show explicit empty states (no `$0`, no `NaN`), and Travel & costs falls back to the labelled sample. Owned by Tasks 4 and 5.
4. **Storage unavailable** (private mode). Expected: every view renders, and choices just don't persist. Owned by Task 6 (`readView`/`writeView` try/catch). `useSaved` is already safe.
5. **Switching views.** Expected: the Google map is not torn down (it stays mounted with `hidden`), so returning to Map does not reload tiles. Owned by Task 6.

---

### Task 1: Widen shared panels (backwards-compatible)

**Files:**
- Modify: `src/components/TierList.tsx` (generic IDs, optional voter picker, configurable crew/choices/copy, Unranked row)
- Modify: `src/features/planning/RouteGraph.tsx` (generic IDs, anchored branches, empty text, footnote)
- Modify: `src/features/overview/TripStats.tsx` (optional labels)
- Modify: `src/features/overview/OverviewHero.tsx` (optional party size)
- Modify: `src/features/planning/TravelCosts.tsx` (optional real route figures)
- Modify: `src/components/TripEssentials.tsx` (optional per-trip storage key)
- Modify: `src/components/ViewNavigation.tsx`, `src/components/NavigationRail.tsx`, `src/features/planning/PlanningDesk.tsx` (optional status text, initials, badge)

**Interfaces:**
- Produces:
  - `TierList<I extends string | number>(props: TierListProps<I>)`.
  - `RouteGraph<I extends string | number>(props: RouteGraphProps<I>)` and `RouteGraphStop<I>`.
  - `TripStats` gains `totalLabel?`/`budgetLabel?`.
  - `OverviewHero` gains `partySize?`.
  - `TravelCosts` gains `route?: { miles: number; minutes: number } | null` and `totalLabel?`.
  - `TripEssentials` gains `storageKey?`.
  - `ViewNavigation` gains `status?`, `NavigationRail` gains `initials?`, `PlanningDesk` gains `badge?`.

- [ ] **Step 1: Replace `src/components/TierList.tsx`**

```tsx
import { useState } from 'react'
import { tiers, type Tier } from './tiers'

const demoCrew = ['Jerry', 'Alex', 'Morgan', 'Sam']
const demoChoices = ['I’m in', 'Maybe', 'Skip']

export type TierListProps<I extends string | number> = {
  options: { id: I; name: string }[]
  ranks: Partial<Record<I, Tier>>
  onRank: (id: I, tier: Tier) => void
  /** The member whose votes are highlighted. */
  voter: string
  /** Shows the "Voting as" picker (the demo's local member switcher). */
  onVoter?: (name: string) => void
  votes: Partial<Record<I, Record<string, string>>>
  onVote: (id: I, choice: string) => void
  /** Names listed under each place's votes. Defaults to the demo crew. */
  crew?: string[]
  /** Vote button labels. Defaults to the demo's I’m in / Maybe / Skip. */
  choices?: string[]
  /** Shows places without a tier in an Unranked row. */
  showUnranked?: boolean
  intro?: string
  hint?: string
}

export function TierList<I extends string | number>({
  options, ranks, onRank, voter, onVoter, votes, onVote,
  crew = demoCrew,
  choices = demoChoices,
  showUnranked = false,
  intro = 'Drag a place into a tier. Higher tiers come first in your questline. S–B are main quests; C–F stay as side quests.',
  hint = 'Use each place’s tier selector for keyboard or touch. Places in the same tier keep their current order. Changes save on this device.',
}: TierListProps<I>) {
  const [dragged, setDragged] = useState<I | null>(null)
  const [over, setOver] = useState<Tier | null>(null)
  const unranked = options.filter(option => ranks[option.id] === undefined)
  const optionRow = (option: { id: I; name: string }, tier: Tier | null) => (
    <div className={`tier-option ${dragged === option.id ? 'dragging' : ''}`} key={option.id} draggable onDragStart={e => { setDragged(option.id); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(option.id)) }} onDragEnd={() => { setDragged(null); setOver(null) }}>
      <span className="drag-handle" aria-hidden="true">⠿</span>
      <strong>{option.name}</strong>
      <select aria-label={`Tier for ${option.name}`} value={tier ?? ''} onChange={e => { if (e.target.value) onRank(option.id, e.target.value as Tier) }}>
        {tier === null && <option value="">–</option>}
        {tiers.map(t => <option key={t} value={t}>{t}</option>)}
      </select>
    </div>
  )
  return <article className="desk-card tier-card">
    <div className="section-title"><h3>Party tier list</h3><span>Rank each stop</span></div>
    <p className="desk-copy">{intro}</p>
    {onVoter && <div className="party-voter"><label>Voting as<select value={voter} onChange={e => onVoter(e.target.value)}>{crew.map(name => <option key={name}>{name}</option>)}</select></label><span>Local demo · switch members to try individual votes</span></div>}
    <div className="tier-board">
      {tiers.map(tier => <section key={tier} className={`tier-row tier-${tier.toLowerCase()} ${over === tier ? 'drop-active' : ''}`} aria-label={`${tier} tier`} onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; setOver(tier) }} onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setOver(null) }} onDrop={e => { e.preventDefault(); const raw = e.dataTransfer.getData('text/plain'); const option = options.find(o => String(o.id) === raw); if (option) onRank(option.id, tier); setDragged(null); setOver(null) }}>
        <div className="tier-label">{tier}<small>TIER</small></div>
        <div className="tier-items">
          {options.filter(option => ranks[option.id] === tier).map(option => optionRow(option, tier))}
          {!options.some(option => ranks[option.id] === tier) && <span className="tier-empty">Drop a place here</span>}
        </div>
      </section>)}
      {showUnranked && unranked.length > 0 && <section className="tier-row tier-unranked" aria-label="Unranked">
        <div className="tier-label">–<small>UNRANKED</small></div>
        <div className="tier-items">{unranked.map(option => optionRow(option, null))}</div>
      </section>}
    </div>
    <p className="tier-hint">{hint}</p>
    <section className="individual-votes">
      <h4>Party votes</h4>
      <p className="tier-hint">Vote on every place independently of its tier. Tap your selection again to clear it.</p>
      {options.map(option => {
        const cast = votes[option.id] ?? {}
        const values = Object.values(cast)
        return <div className="option-voting" key={option.id}>
          <strong>{option.name}</strong>
          <div className="party-vote-actions">{choices.map(choice => <button key={choice} aria-pressed={cast[voter] === choice} className={cast[voter] === choice ? 'selected-vote' : ''} onClick={() => onVote(option.id, choice)}>{choice} <span>{values.filter(v => v === choice).length}</span></button>)}</div>
          <details><summary>{values.filter(Boolean).length} of {crew.length} voted{values.includes(choices[0]) && values.includes(choices[2]) ? ' · Split vote' : ''}</summary>
            <div className="member-votes">{crew.map(name => <span key={name}><b>{name}</b>{cast[name] || 'Not voted'}</span>)}</div>
          </details>
        </div>
      })}
    </section>
  </article>
}
```

Note: the demo's split-vote check compared against `'I’m in'` and `'Skip'` literally; `choices[0]`/`choices[2]` is identical for the demo defaults.

- [ ] **Step 2: Replace `src/features/planning/RouteGraph.tsx`**

```tsx
export type RouteGraphStop<I extends string | number> = {
  id: I
  name: string
  side: boolean
  time: string
  /** Side quests: the main stop they branch from. Missing → under the first stop (demo). */
  anchorId?: I | null
  /** Side quests: e.g. "+6 min". Defaults to "Optional branch". */
  branchNote?: string
}

export type RouteGraphProps<I extends string | number> = {
  stops: RouteGraphStop<I>[]
  done: I[]
  onReviewRoute: () => void
  onDetails: (id: I) => void
  emptyText?: string
  footnote?: string
}

export function RouteGraph<I extends string | number>({
  stops,
  done,
  onReviewRoute,
  onDetails,
  emptyText = 'Promote a waypoint to start your main path.',
  footnote = 'Illustrative sequence',
}: RouteGraphProps<I>) {
  const main = stops.filter((stop) => !stop.side)
  const sides = stops.filter((stop) => stop.side)
  const branchesOf = (stop: RouteGraphStop<I>, index: number) =>
    sides.filter((side) =>
      side.anchorId === stop.id || (index === 0 && !main.some((m) => m.id === side.anchorId)),
    )
  return (
    <article className="desk-card route-graph">
      <div className="section-title">
        <h3>Your questline</h3>
        <button className="text-button" onClick={onReviewRoute}>
          Edit on map →
        </button>
      </div>
      <p className="desk-copy">
        Solid connections are the main path. Blue branches are optional side
        quests.
      </p>
      <div className="graph-flow">
        {main.map((stop, index) => {
          const branches = branchesOf(stop, index)
          return (
            <div className="graph-stage" key={stop.id}>
              <button onClick={() => onDetails(stop.id)}>
                <span>{done.includes(stop.id) ? '✓' : index + 1}</span>
                <strong>{stop.name}</strong>
                <small>{stop.time}</small>
              </button>
              {branches.length > 0 && (
                <div className="graph-branches">
                  {branches.map((side) => (
                    <button key={side.id} onClick={() => onDetails(side.id)}>
                      ↳ <span>✧ {side.name}</span>
                      <small>{side.branchNote ?? 'Optional branch'}</small>
                    </button>
                  ))}
                </div>
              )}
              {index < main.length - 1 && <div className="graph-connector">↓</div>}
            </div>
          )
        })}
      </div>
      {main.length === 0 && <div className="desk-empty">{emptyText}</div>}
      <div className="graph-footer">
        <span>● Main path</span>
        <span className="blue">○ Side quest</span>
        <span>{footnote}</span>
      </div>
    </article>
  )
}
```

Note: the demo rendered branches *after* the first stage's connector only when `index === 0`. Branches now render before the connector, which matches the demo screenshot (Sutro Baths sits between stops 1 and 2).

- [ ] **Step 3: `TripStats` optional labels.** In `src/features/overview/TripStats.tsx`, change the props and the middle card:

```tsx
export type TripStatsProps = {
  mainCount: number
  total?: number
  budget?: number
  completed: number
  /** Replaces `$total`, e.g. "$30–60". */
  totalLabel?: string
  /** Replaces "Of your $budget daily budget". */
  budgetLabel?: string
}
export function TripStats({ mainCount, total = 0, budget = 0, completed, totalLabel, budgetLabel }: TripStatsProps) {
```

```tsx
      <article>
        <span>ESTIMATE / PERSON</span>
        <strong>{totalLabel ?? `$${total}`}</strong>
        <p>{budgetLabel ?? `Of your $${budget} daily budget`}</p>
      </article>
```

- [ ] **Step 4: `OverviewHero` party size.** In `src/features/overview/OverviewHero.tsx`, add `partySize?: number` to the props and replace the paragraph:

```tsx
      <p>
        {stopCount} places to explore.{' '}
        {partySize === undefined ? 'Four people' : `${partySize} ${partySize === 1 ? 'person' : 'people'}`} to make memories with.
      </p>
```

- [ ] **Step 5: `TravelCosts` real figures.** In `src/features/planning/TravelCosts.tsx`:
  - Add `route?: { miles: number; minutes: number } | null` and `totalLabel?: string` to the props and destructuring.
  - Add `const miles = route?.miles ?? 12` at the top of the function.
  - Replace the metrics and footnote as follows:

```tsx
        <div>
          <span>Food + activities</span>
          <strong>
            {totalLabel ?? `$${total}`}
            <small> / person</small>
          </strong>
        </div>
        <div>
          <span>{route ? 'Route distance' : 'Sample route distance'}</span>
          <strong>
            {miles}<small> miles</small>
          </strong>
        </div>
        <div>
          <span>{route ? 'Drive time' : 'Sample travel time'}</span>
          <strong>
            {route ? route.minutes : travelMode === 'Drive' ? '45' : travelMode === 'Walk' ? '240' : '75'}
            <small> min</small>
          </strong>
        </div>
        {travelMode === 'Drive' && (
          <div>
            <span>Fuel estimate · 25 mpg</span>
            <strong>
              ${((miles / 25) * gasPrice).toFixed(2)}
              <small> / vehicle</small>
            </strong>
          </div>
        )}
```

```tsx
      <p className="desk-footnote">
        {route
          ? 'Distance and drive time come from the current questline. Fuel = route miles ÷ 25 mpg × gas price. Walking and transit are not routed. No fares or parking included.'
          : 'Distance and times use a fixed sample scenario, not live routing. Fuel = 12 miles ÷ 25 mpg × gas price. No fares or parking included.'}
      </p>
```

- [ ] **Step 6: `TripEssentials` storage key.** In `src/components/TripEssentials.tsx`:
  - Change the signature to `export function TripEssentials({ travelMode, storageKey }: { travelMode: string; storageKey?: string }) {`.
  - Add `const suffix = storageKey ? \`:${storageKey}\` : ''` as its first line.
  - Replace the four literal keys: `'questline-conditions'` → `` `questline-conditions${suffix}` `` (two places) and `'questline-packed'` → `` `questline-packed${suffix}` `` (two places).

- [ ] **Step 7: Shell text props.**
  - `ViewNavigation`: add `status?: string` and render `{status ?? <>{accepted ? '✓ Questline accepted' : '◌ Draft questline'} · Changes saved locally</>}` inside the `<span>`.
  - `NavigationRail`: add `initials?: string` (default `'JS'`) and render it in `<span className="avatar">`.
  - `PlanningDesk`: add `badge?: string` (default `'Local planning workspace'`) and render it in `.local-badge`.

- [ ] **Step 8: Verify the demo is unchanged**

Run: `npm run lint && npm run build`
Expected: both pass. Then open `http://localhost:5173/demo` (Build my questline → Planning desk and Overview) and compare against the screenshots in `.playwright-mcp/demo-*.png`. The tier list, route graph (Sutro Baths branch under stop 1), stats `$43 / Of your $65 daily budget`, and "Voting as" picker should be unchanged.

- [ ] **Step 9: Commit**

```bash
git add src/components/TierList.tsx src/features/planning/RouteGraph.tsx src/features/overview/TripStats.tsx src/features/overview/OverviewHero.tsx src/features/planning/TravelCosts.tsx src/components/TripEssentials.tsx src/components/ViewNavigation.tsx src/components/NavigationRail.tsx src/features/planning/PlanningDesk.tsx
git commit -m "refactor(ui): let demo panels take live data without changing the demo"
```

---

### Task 2: Desk adapters (pure logic)

**Files:**
- Create: `src/trip/deskAdapters.ts`

**Interfaces:**
- Consumes: `StopView`, `voteLabels`, `voteKinds`, `planStops` from `src/trip/adapters.ts`; `Tier` from `src/components/tiers.ts`.
- Produces:
  - `tierVote: Record<Tier, VoteKind>` and `voteTier: Record<VoteKind, Tier>`.
  - `displayedTiers(stops: StopView[], saved: Partial<Record<string, Tier>>): Partial<Record<string, Tier>>`.
  - `voteForRank(current: VoteKind | null, tier: Tier): VoteKind | null`.
  - `voteChoices: string[]` and `kindForChoice(choice: string): VoteKind | null`.
  - `partyVotes(stops: StopView[]): Record<string, Record<string, string>>`.
  - `routeTotals(plan: Plan | null): { miles: number; minutes: number } | null`.
  - `graphStops(plan: Plan | null, stops: StopView[]): RouteGraphStop<string>[]`.
  - `conversationLines(snapshot: TripSnapshot): ConversationLine[]` and the `ConversationLine` type.

- [ ] **Step 1: Create `src/trip/deskAdapters.ts`**

```ts
// Pure snapshot → view-model logic for the live Overview and Planning desk. No React, no fetch.
import type { Plan, TripSnapshot, VoteKind } from '../api'
import type { Tier } from '../components/tiers'
import type { RouteGraphStop } from '../features/planning/RouteGraph'
import { planStops, voteKinds, voteLabels, type StopView } from './adapters'

/** A tier is a vote: S/A I'm in, B/C Sure, D–F Skip. */
export const tierVote: Record<Tier, VoteKind> = { S: 'in', A: 'in', B: 'ok', C: 'ok', D: 'out', E: 'out', F: 'out' }
/** Where a vote shows when this device has no matching tier. */
export const voteTier: Record<VoteKind, Tier> = { in: 'A', ok: 'C', out: 'E' }

/** The viewer's tiers: their saved tier when it still matches their vote, else the vote's default. Unvoted places are unranked. */
export function displayedTiers(stops: StopView[], saved: Partial<Record<string, Tier>>): Partial<Record<string, Tier>> {
  const ranks: Partial<Record<string, Tier>> = {}
  for (const stop of stops) {
    if (!stop.myVote) continue
    const local = saved[stop.id]
    ranks[stop.id] = local && tierVote[local] === stop.myVote ? local : voteTier[stop.myVote]
  }
  return ranks
}

/** The vote to send for a new tier, or null when it already is the viewer's vote (the API toggles). */
export function voteForRank(current: VoteKind | null, tier: Tier): VoteKind | null {
  const next = tierVote[tier]
  return next === current ? null : next
}

export const voteChoices: string[] = voteKinds.map(kind => voteLabels[kind])

export function kindForChoice(choice: string): VoteKind | null {
  return voteKinds.find(kind => voteLabels[kind] === choice) ?? null
}

/** place id → member name → vote label, for the tier list's Party votes section. */
export function partyVotes(stops: StopView[]): Record<string, Record<string, string>> {
  return Object.fromEntries(
    stops.map(stop => [
      stop.id,
      Object.fromEntries(voteKinds.flatMap(kind => stop.votes[kind].map(name => [name, voteLabels[kind]]))),
    ]),
  )
}

/** Total main-route distance and drive time, or null before a plan exists. */
export function routeTotals(plan: Plan | null): { miles: number; minutes: number } | null {
  const legs = plan?.content?.graph?.edges.filter(edge => edge.kind === 'travel') ?? []
  if (legs.length === 0) return null
  const meters = legs.reduce((sum, leg) => sum + (leg.distance_m ?? 0), 0)
  const minutes = legs.reduce((sum, leg) => sum + (leg.drive_min ?? 0), 0)
  return { miles: Math.round(meters / 1609.344), minutes: Math.round(minutes) }
}

/** The plan's quests in travel order for RouteGraph; side quests keep their anchor. */
export function graphStops(plan: Plan | null, stops: StopView[]): RouteGraphStop<string>[] {
  const nodes = planStops(plan)
  if (!nodes) return []
  const byId = new Map(stops.map(stop => [stop.id, stop]))
  const main = nodes.main.flatMap(node => {
    const stop = byId.get(node.id)
    return stop ? [{ id: stop.id, name: stop.name, side: false, time: stop.arrive ?? '' }] : []
  })
  const side = nodes.side.flatMap(node => {
    const stop = byId.get(node.id)
    return stop
      ? [{ id: stop.id, name: stop.name, side: true, time: '', anchorId: node.anchor, branchNote: stop.detour ?? 'detour unknown' }]
      : []
  })
  return [...main, ...side]
}

export type ConversationLine = { id: string; author: string; initial: string; text: string }

/** Messages oldest first, attributed to member names when known. */
export function conversationLines(snapshot: TripSnapshot): ConversationLine[] {
  const names = new Map(snapshot.members.map(member => [member.id, member.name]))
  return [...snapshot.messages]
    .sort((a, b) => a.sent_at.localeCompare(b.sent_at))
    .map(message => {
      const author = (message.member_id && names.get(message.member_id)) || message.author_id
      return { id: message.id, author, initial: author.slice(0, 1).toUpperCase(), text: message.text }
    })
}
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc -b`
Expected: no errors. If `PlanNode.anchor` is not typed `string | null`, check `src/api/types.ts:183` and adjust `anchorId: node.anchor ?? null`.

- [ ] **Step 3: Commit**

```bash
git add src/trip/deskAdapters.ts
git commit -m "feat(trip): add pure adapters for the live overview and planning desk"
```

---

### Task 3: `useVote` hook and controllable workspace

**Files:**
- Create: `src/trip/useVote.ts`
- Modify: `src/trip/TripWorkspace.tsx` (props `tab?`, `onTabChange?`, `onImport`; remove its own Import chat dialog)

**Interfaces:**
- Consumes: `useTrip()` from `../state`, and `errorMessage` from `./errors`.
- Produces:
  - `useVote(onError: (message: string) => void): { vote: (placeId: Uuid, kind: VoteKind) => Promise<void>; pending: Uuid[] }`.
  - `TripWorkspace(props: TripWorkspaceProps)` with `TripWorkspaceProps = { tab?: BoardTab; onTabChange?: (tab: BoardTab) => void; onImport: () => void }`.

- [ ] **Step 1: Create `src/trip/useVote.ts`**

```ts
import { useState } from 'react'
import type { Uuid, VoteKind } from '../api'
import { useTrip } from '../state'
import { errorMessage } from './errors'

/** Casts the viewer's vote. The API toggles: sending the current kind again clears it. */
export function useVote(onError: (message: string) => void) {
  const { mutate } = useTrip()
  const [pending, setPending] = useState<Uuid[]>([])
  async function vote(placeId: Uuid, kind: VoteKind) {
    setPending(current => [...current, placeId])
    try {
      await mutate(api => api.vote(placeId, kind))
    } catch (failure) {
      onError(errorMessage(failure))
    } finally {
      setPending(current => current.filter(id => id !== placeId))
    }
  }
  return { vote, pending }
}
```

- [ ] **Step 2: Make `TripWorkspace` controllable**

In `src/trip/TripWorkspace.tsx`:

```tsx
export type TripWorkspaceProps = {
  /** Controlled board tab; uncontrolled when absent. */
  tab?: BoardTab
  onTabChange?: (tab: BoardTab) => void
  /** Opens the trip's single Import chat dialog, owned by TripApp. */
  onImport: () => void
}

/** The live map and quest board for the trip in the surrounding TripProvider. */
export function TripWorkspace({ tab: controlledTab, onTabChange, onImport }: TripWorkspaceProps) {
```

- Replace `const [tab, setTab] = useState<BoardTab>('Waypoints')` with:

```tsx
  const [ownTab, setOwnTab] = useState<BoardTab>('Waypoints')
  const tab = controlledTab ?? ownTab
  const setTab = onTabChange ?? setOwnTab
```

- Delete `const [importOpen, setImportOpen] = useState(false)`.
- Replace both `onImport={() => setImportOpen(true)}` with `onImport={onImport}`.
- Delete `<ImportChat open={importOpen} onClose={() => setImportOpen(false)} />` and its `import { ImportChat } from './ImportChat'`.

- [ ] **Step 3: Typecheck**

Run: `npx tsc -b`
Expected: an error only in `src/trip/TripApp.tsx` (`onImport` missing on `<TripWorkspace />`). Task 6 fixes this. Temporarily pass `onImport={() => {}}` there so the build stays green for this commit.

- [ ] **Step 4: Commit**

```bash
git add src/trip/useVote.ts src/trip/TripWorkspace.tsx src/trip/TripApp.tsx
git commit -m "refactor(trip): share voting and let the shell own the board tab and import dialog"
```

---

### Task 4: Live Overview view

**Files:**
- Create: `src/trip/ui/TripOverview.tsx`

**Interfaces:**
- Consumes: `WorkspaceView` (from `workspaceView()` in `adapters.ts`); `PartyMember` from `features/overview/PartyCard`; `Overview`, `OverviewHero`, `TripStats`, `PartyCard`, `TripEssentials`.
- Produces: `TripOverview(props: { tripId: string; view: WorkspaceView; party: PartyMember[]; travelMode: string; onExplore: () => void; onReviewRoute: () => void })`.

- [ ] **Step 1: Create `src/trip/ui/TripOverview.tsx`**

```tsx
import { TripEssentials } from '../../components/TripEssentials'
import { Overview } from '../../features/overview/Overview'
import { OverviewHero } from '../../features/overview/OverviewHero'
import { PartyCard, type PartyMember } from '../../features/overview/PartyCard'
import { TripStats } from '../../features/overview/TripStats'
import type { WorkspaceView } from '../adapters'

export type TripOverviewProps = {
  tripId: string
  view: WorkspaceView
  party: PartyMember[]
  travelMode: string
  onExplore: () => void
  onReviewRoute: () => void
}

export function TripOverview({ tripId, view, party, travelMode, onExplore, onReviewRoute }: TripOverviewProps) {
  const plan = view.build.plan
  const progress = view.questLog.progress
  return (
    <Overview
      hero={<OverviewHero stopCount={view.stops.length} partySize={party.length} onExplore={onExplore} />}
      stats={
        <TripStats
          mainCount={plan?.mainCount ?? 0}
          completed={progress?.done ?? 0}
          totalLabel={plan ? plan.estimate.amount : '—'}
          budgetLabel={plan ? `${plan.presetLabel} preset${plan.estimate.note ? ` · ${plan.estimate.note}` : ''}` : 'Build the questline for an estimate'}
        />
      }
      party={<PartyCard members={party} />}
      preparation={
        <article className="overview-card">
          <div className="section-title">
            <h3>Before you head out</h3>
            <span>On this device</span>
          </div>
          <TripEssentials travelMode={travelMode} storageKey={tripId} />
          <button className="overview-action" onClick={onReviewRoute}>
            ◇ Review the questline <span>→</span>
          </button>
        </article>
      }
    />
  )
}
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc -b`
Expected: passes. If `PlanView.estimate.amount` is named differently, check `Estimate` in `src/trip/adapters.ts:400`. It is `{ amount: string; note: string | null }`.

- [ ] **Step 3: Commit**

```bash
git add src/trip/ui/TripOverview.tsx
git commit -m "feat(trip): add the live overview view"
```

---

### Task 5: Live Planning desk view

**Files:**
- Create: `src/trip/ui/TripConversation.tsx`
- Create: `src/trip/ui/TripPlanningDesk.tsx`

**Interfaces:**
- Consumes: everything from Task 2; `useVote` (Task 3); the widened `TierList`, `RouteGraph`, `TravelCosts` and `PlanningDesk` (Task 1); `ConstraintsCard`, `LocationCard`; `useSaved`.
- Produces:
  - `TripConversation(props: { lines: ConversationLine[]; onImport: () => void; onSelectPlace: (id: string) => void; stops: { id: string; name: string }[] })`.
  - `TripPlanningDesk(props: TripPlanningDeskProps)` (below).

- [ ] **Step 1: Create `src/trip/ui/TripConversation.tsx`**

```tsx
import type { ConversationLine } from '../deskAdapters'

export type TripConversationProps = {
  lines: ConversationLine[]
  stops: { id: string; name: string }[]
  onImport: () => void
  onSelectPlace: (id: string) => void
}

/** The trip's real messages in the demo's conversation panel. Read-only. */
export function TripConversation({ lines, stops, onImport, onSelectPlace }: TripConversationProps) {
  return (
    <article className="desk-card chat-reader">
      <div className="section-title">
        <h3>Party conversation</h3>
        <span>From your group chat</span>
      </div>
      <p className="desk-copy">
        Messages from your linked iMessage group and pasted chats. Places they mention land on the map.
      </p>
      <button className="primary" onClick={onImport}>
        ＋ Import chat
      </button>
      <div className="conversation-stream">
        {lines.length === 0 ? (
          <div className="desk-empty">
            Your group’s ideas will appear here.
            <br />
            Link iMessage or import a chat to get started.
          </div>
        ) : (
          lines.map(line => (
            <div className="message" key={line.id}>
              <span className="message-avatar">{line.initial}</span>
              <div>
                <strong>{line.author}</strong>
                <p>{line.text}</p>
                {stops
                  .filter(stop => line.text.toLowerCase().includes(stop.name.toLowerCase()))
                  .map(stop => (
                    <button key={stop.id} onClick={() => onSelectPlace(stop.id)}>
                      ⌖ {stop.name} ↗
                    </button>
                  ))}
              </div>
            </div>
          ))
        )}
      </div>
    </article>
  )
}
```

- [ ] **Step 2: Create `src/trip/ui/TripPlanningDesk.tsx`**

```tsx
import type { Plan, TripSnapshot } from '../../api'
import type { Tier } from '../../components/tiers'
import { TierList } from '../../components/TierList'
import type { Constraints } from '../../demo/types'
import { ConstraintsCard } from '../../features/planning/ConstraintsCard'
import { LocationCard } from '../../features/planning/LocationCard'
import { PlanningDesk } from '../../features/planning/PlanningDesk'
import { RouteGraph } from '../../features/planning/RouteGraph'
import { TravelCosts } from '../../features/planning/TravelCosts'
import { useSaved } from '../../lib/useSaved'
import type { WorkspaceView } from '../adapters'
import {
  conversationLines,
  displayedTiers,
  graphStops,
  kindForChoice,
  partyVotes,
  routeTotals,
  voteChoices,
  voteForRank,
} from '../deskAdapters'
import { useVote } from '../useVote'
import { TripConversation } from './TripConversation'

const defaultConstraints: Constraints = { returnBy: '18:00', maxWalk: 30, dietary: '', mobility: '' }

export type TripPlanningDeskProps = {
  tripId: string
  snapshot: TripSnapshot
  view: WorkspaceView
  myName: string
  travelMode: string
  onTravelModeChange: (mode: string) => void
  onImport: () => void
  /** Show a place on the Map view. */
  onShowPlace: (id: string) => void
  /** Map view › Questline tab. */
  onReviewRoute: () => void
  onError: (message: string) => void
}

export function TripPlanningDesk({
  tripId, snapshot, view, myName, travelMode, onTravelModeChange, onImport, onShowPlace, onReviewRoute, onError,
}: TripPlanningDeskProps) {
  const [constraints, setConstraints] = useSaved('questline-device-constraints', defaultConstraints)
  const [gasPrice, setGasPrice] = useSaved('questline-device-gas', 4.5)
  const [savedTiers, setSavedTiers] = useSaved<Partial<Record<string, Tier>>>(`questline-tiers:${tripId}`, {})
  const { vote } = useVote(onError)
  const plan: Plan | null = snapshot.current_plan
  const stops = view.stops
  const ranks = displayedTiers(stops, savedTiers)
  const done = stops.filter(stop => stop.done).map(stop => stop.id)

  function rank(id: string, tier: Tier) {
    setSavedTiers({ ...savedTiers, [id]: tier })
    const stop = stops.find(s => s.id === id)
    const next = stop ? voteForRank(stop.myVote, tier) : null
    if (next) void vote(id, next)
  }

  function voteFor(id: string, choice: string) {
    const kind = kindForChoice(choice)
    if (kind) void vote(id, kind)
  }

  return (
    <PlanningDesk
      badge="Shared trip · some panels on this device"
      conversation={
        <TripConversation
          lines={conversationLines(snapshot)}
          stops={stops}
          onImport={onImport}
          onSelectPlace={onShowPlace}
        />
      }
      route={
        <RouteGraph
          stops={graphStops(plan, stops)}
          done={done}
          onReviewRoute={onReviewRoute}
          onDetails={onShowPlace}
          emptyText="Build the questline on the map to see your route here."
          footnote="From the current questline"
        />
      }
      priorities={
        <TierList
          options={stops.map(stop => ({ id: stop.id, name: stop.name }))}
          ranks={ranks}
          onRank={rank}
          voter={myName}
          votes={partyVotes(stops)}
          onVote={voteFor}
          crew={view.members.map(member => member.name)}
          choices={voteChoices}
          showUnranked
          intro="Drag a place into a tier to vote. S–A is I’m in, B–C is Sure, D–F is Skip. Build puts I’m-in picks on the main quest."
          hint="Your tier is your vote, shared with the party. The exact tier is remembered on this device."
        />
      }
      constraints={<ConstraintsCard constraints={constraints} onConstraintsChange={setConstraints} />}
      travel={
        <TravelCosts
          total={0}
          totalLabel={view.build.plan ? view.build.plan.estimate.amount : '—'}
          route={routeTotals(plan)}
          travelMode={travelMode}
          gasPrice={gasPrice}
          onTravelModeChange={onTravelModeChange}
          onGasPriceChange={setGasPrice}
        />
      }
      location={<LocationCard />}
    />
  )
}
```

`StopView.votes` lists member names. `myName` is the viewer's member name, so the tier list's `cast[voter]` highlights the viewer's own vote.

- [ ] **Step 3: Typecheck**

Run: `npx tsc -b`
Expected: passes.

- [ ] **Step 4: Commit**

```bash
git add src/trip/ui/TripConversation.tsx src/trip/ui/TripPlanningDesk.tsx
git commit -m "feat(trip): add the live planning desk with tier-list voting"
```

---

### Task 6: Shell in `TripApp`

**Files:**
- Modify: `src/trip/TripApp.tsx`

**Interfaces:**
- Consumes: Tasks 3–5 (`TripWorkspace` props, `TripOverview`, `TripPlanningDesk`); `NavigationRail`, `ViewNavigation`, `ImportChat`, `workspaceView`, `useSaved`; `BoardTab` from `./ui/TripBoard`.
- Produces: the live shell. No new exports.

- [ ] **Step 1: Rewrite `src/trip/TripApp.tsx`**

```tsx
import { useMemo, useState } from 'react'
import { navigateHome, tripUrl, useTrip } from '../state'
import { PlannerHeader } from '../components/AppHeader'
import { NavigationRail } from '../components/NavigationRail'
import { TripHeading } from '../components/TripHeading'
import { ViewNavigation } from '../components/ViewNavigation'
import { AppFooter } from '../components/AppFooter'
import { Notice } from '../components/Notice'
import { copyText } from '../lib/copyText'
import { useSaved } from '../lib/useSaved'
import { PartyCard } from '../features/overview/PartyCard'
import { workspaceView } from './adapters'
import { ImportChat } from './ImportChat'
import { tripHeadingFromSnapshot } from './tripHeadingAdapter'
import { TripWorkspace } from './TripWorkspace'
import type { BoardTab } from './ui/TripBoard'
import { TripOverview } from './ui/TripOverview'
import { TripPlanningDesk } from './ui/TripPlanningDesk'

type View = 'Map' | 'Overview' | 'Planning desk'
const views: View[] = ['Map', 'Overview', 'Planning desk']

function readView(tripId: string): View {
  try {
    const saved = localStorage.getItem(`questline-view:${tripId}`)
    return views.includes(saved as View) ? (saved as View) : 'Map'
  } catch {
    return 'Map'
  }
}

function writeView(tripId: string, view: View) {
  try {
    localStorage.setItem(`questline-view:${tripId}`, view)
  } catch {
    /* Storage may be unavailable in private sessions. */
  }
}

/** The live trip shell. Must render inside `<TripProvider>`. */
export function TripApp() {
  const { session, snapshot, error } = useTrip()
  const [notice, setNotice] = useState('')
  const [view, setViewState] = useState<View>(() => readView(session.tripId))
  const [tab, setTab] = useState<BoardTab>('Waypoints')
  const [importOpen, setImportOpen] = useState(false)
  const [travelMode, setTravelMode] = useSaved('questline-device-travel', 'Drive')
  const heading = useMemo(
    () => (snapshot ? tripHeadingFromSnapshot(snapshot, session.memberId) : null),
    [snapshot, session.memberId],
  )
  const live = useMemo(
    () => (snapshot ? workspaceView(snapshot, null, null, session.memberId) : null),
    [snapshot, session.memberId],
  )
  const status = snapshot ? (error ? 'Reconnecting…' : 'Live') : error ? 'Connecting…' : 'Loading…'
  const me = heading?.members.find(member => member.isMe)
  const party = (heading?.members ?? []).map(member => ({
    id: member.id,
    initials: member.initials,
    name: member.name,
    role: member.isMe ? 'You, on this device' : 'Party member',
  }))

  function setView(next: string) {
    if (!views.includes(next as View)) return
    setViewState(next as View)
    writeView(session.tripId, next as View)
  }

  function openOnMap(nextTab: BoardTab) {
    setTab(nextTab)
    setView('Map')
  }

  function shareTrip() {
    const link = tripUrl(session.tripId)
    void copyText(link).then((copied) =>
      setNotice(
        copied
          ? 'Trip link copied. Anyone with the link can see this trip and join it.'
          : `Share this link with your party: ${link}`,
      ),
    )
  }

  /**
   * Copies the link command with the bare trip ID. Messages splits a pasted text that ends in a URL
   * into two messages, so `@questline link <share link>` would reach the relay without its link.
   */
  function linkChat() {
    const command = `@questline link ${session.tripId}`
    void copyText(command).then((copied) =>
      setNotice(
        copied
          ? 'Copied. Paste it into your iMessage group and send it to link the chat to this trip.'
          : `Send this in your iMessage group: ${command}`,
      ),
    )
  }

  return (
    <div className="app">
      <NavigationRail view={view} initials={me?.initials} onViewChange={setView} onQuestLog={() => openOnMap('Quest log')} />
      <div className="workspace">
        <PlannerHeader status={status} planSetupLabel="New trip" onPlanSetup={navigateHome} onShare={shareTrip} onLinkChat={linkChat} />
        {heading && live && snapshot ? (
          <>
            <TripHeading
              trip={{ name: heading.name, destination: heading.destination }}
              dateLabel={heading.dateLabel}
              members={heading.members}
              onImport={() => setImportOpen(true)}
            />
            <ViewNavigation
              view={view}
              accepted={live.build.plan?.accepted ?? false}
              status={`${live.build.plan?.accepted ? '✓ Questline accepted' : '◌ Draft questline'} · Shared with your party`}
              onViewChange={setView}
            />
            {view === 'Overview' && (
              <TripOverview
                tripId={session.tripId}
                view={live}
                party={party}
                travelMode={travelMode}
                onExplore={() => setView('Map')}
                onReviewRoute={() => openOnMap('Questline')}
              />
            )}
            {view === 'Planning desk' && (
              <TripPlanningDesk
                tripId={session.tripId}
                snapshot={snapshot}
                view={live}
                myName={me?.name ?? ''}
                travelMode={travelMode}
                onTravelModeChange={setTravelMode}
                onImport={() => setImportOpen(true)}
                onShowPlace={() => openOnMap('Waypoints')}
                onReviewRoute={() => openOnMap('Questline')}
                onError={setNotice}
              />
            )}
            <div className={view === 'Map' ? '' : 'hidden'}>
              <TripWorkspace tab={tab} onTabChange={setTab} onImport={() => setImportOpen(true)} />
            </div>
            {view === 'Map' && (
              <section className="overview">
                <div className="overview-grid">
                  <PartyCard members={party} />
                </div>
              </section>
            )}
          </>
        ) : (
          <section className="overview">
            <article className="overview-card" aria-busy={!error}>
              <p className="overview-copy mb-0">
                {error ? "Can't reach the Questline server. Still trying…" : 'Opening your trip…'}
              </p>
            </article>
          </section>
        )}
        <AppFooter />
        <ImportChat open={importOpen} onClose={() => setImportOpen(false)} />
        {notice && <Notice message={notice} onDismiss={() => setNotice('')} />}
      </div>
    </div>
  )
}
```

`shareTrip` and `linkChat` are today's bodies, unchanged. `onShowPlace` switches to Map › Waypoints; it does not select the place, because selection stays inside `TripWorkspace` (out of scope).

- [ ] **Step 2: Lint, build and check in the browser**

Run: `npm run lint && npm run build`
Expected: pass. Then open a live trip at `http://<LAN IP>:5173/t/<id>`:
- the rail and the three tabs appear;
- switching to Overview and back to Map does not reload the map tiles (no blank map);
- the rail's ☷ opens Map › Quest log;
- Import chat from the heading opens one dialog;
- reloading keeps the selected view.

- [ ] **Step 3: Commit**

```bash
git add src/trip/TripApp.tsx
git commit -m "feat(trip): give live trips the demo shell with map, overview and planning desk"
```

---

### Task 7: Create page "What happens next"

**Files:**
- Modify: `src/features/trip-setup/CreateTripPage.tsx` (the `actions` prop of `SetupPage`)

**Interfaces:**
- Consumes: nothing new.
- Produces: a UI change only.

- [ ] **Step 1: Add the steps list** inside the existing `actions` `<div>`, before the links:

```tsx
            <ol className="desk-copy m-0 w-full list-decimal pl-5">
              <li>Create the trip.</li>
              <li>Tap <strong>Link iMessage</strong> and send it in your group chat.</li>
              <li>Places your group mentions appear on the map.</li>
              <li>Vote or rank them, then <strong>Build</strong> the questline.</li>
            </ol>
```

- [ ] **Step 2: Verify**

Run: `npm run lint && npm run build`
Expected: pass. At `/`, the list shows under the intro, at desktop width and at 375px with no horizontal scroll.

- [ ] **Step 3: Commit**

```bash
git add src/features/trip-setup/CreateTripPage.tsx
git commit -m "feat(setup): show what happens after creating a trip"
```

---

### Task 8: Docs and full verification

**Files:**
- Modify: `README.md` (route table: the live trip now has Map / Overview / Planning desk)
- Modify: `docs/ui-composition.md` (live composition and the widened props)

- [ ] **Step 1: README.** In "Frontend development", replace the paragraph starting "Creating and joining need the backend. The live trip shows…" with:

```markdown
Creating and joining need the backend. A live trip uses the demo's shell: **Map** (waypoints with
I'm in / Sure / Skip votes, the map, the questline and the quest log), **Overview** (real stats,
party and progress, plus a packing checklist kept on this device), and **Planning desk** (the
group's messages, the questline graph, a tier list whose tiers are your vote, and restrictions /
travel panels kept on this device). Shared data comes from the API; travel mode, restrictions,
gas price, tier placement and the checklist are saved in this browser only.
```

- [ ] **Step 2: `docs/ui-composition.md`.** Append a section:

```markdown
## Live trip composition

`src/trip/TripApp.tsx` composes the same panels for live trips. Pure logic lives in
`src/trip/deskAdapters.ts`; `TripOverview` and `TripPlanningDesk` (in `src/trip/ui/`) wire panels
to `workspaceView()` data. Widened, optional props keep the demo unchanged: `TierList` and
`RouteGraph` accept string or number IDs; `TierList` hides "Voting as" without `onVoter` and can
show an Unranked row; `TripStats`, `TravelCosts`, `OverviewHero`, `TripEssentials`,
`ViewNavigation`, `NavigationRail` and `PlanningDesk` take optional labels or keys.
`TripWorkspace` stays mounted (hidden) on other views so the Google map does not reload.
```

- [ ] **Step 3: Full checks**

```bash
npm run lint && npm run build
cd backend && uv run ruff check . && uv run pyright && TEST_DATABASE_URL=postgresql://questline:questline@localhost:5433/questline_test uv run pytest -q
```

Expected: everything passes. The backend is untouched, so the pytest count is unchanged (290).

- [ ] **Step 4: Browser walkthrough** (two sessions on one live trip, A and B), at desktop width and at 375px:
1. Overview: the stats match the Map › Questline (main count, estimate, progress). The party is the real members.
2. Planning desk: the messages match the trip. The route graph shows the plan order with side branches under their anchors.
3. In A, drag a place from Unranked to S. B sees A's "I'm in" within about 3 seconds.
4. In A, drag that place S → A. No vote request is sent (check the Network panel). The vote stays.
5. In B (or by tapback), change A's vote to Skip. A's tier list moves the place to E.
6. Travel & costs shows the real miles and drive time after a build, and the labelled sample before.
7. Reload: the view, tiers, restrictions and checklist persist.
8. `/demo` is unchanged.
9. The console shows no errors.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/ui-composition.md
git commit -m "docs: describe the live trip's demo layout"
```
