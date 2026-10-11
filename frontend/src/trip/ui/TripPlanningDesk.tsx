import { useState } from 'react'
import type { Plan, TripSnapshot, VoteKind } from '../../api'
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
  afterVote,
  conversationLines,
  displayedTiers,
  graphStops,
  kindForChoice,
  partyVotes,
  routeTotals,
  voteChoices,
  voteForRank,
  withPendingVotes,
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
  // Votes sent but not yet in the snapshot. The API toggles, so a repeat of an action before the
  // refresh lands would clear the vote: actions on a place wait until its vote settles.
  const [inFlight, setInFlight] = useState<Partial<Record<string, VoteKind | null>>>({})
  const plan: Plan | null = snapshot.current_plan
  const stops = withPendingVotes(view.stops, inFlight)
  const ranks = displayedTiers(stops, savedTiers)
  const done = stops.filter(stop => stop.done).map(stop => stop.id)

  function send(id: string, kind: VoteKind) {
    const stop = stops.find(s => s.id === id)
    if (!stop || id in inFlight) return
    setInFlight(current => ({ ...current, [id]: afterVote(stop.myVote, kind) }))
    void vote(id, kind).finally(() =>
      setInFlight(current => {
        const rest = { ...current }
        delete rest[id]
        return rest
      }),
    )
  }

  function rank(id: string, tier: Tier) {
    if (id in inFlight) return
    setSavedTiers(current => ({ ...current, [id]: tier }))
    const stop = stops.find(s => s.id === id)
    const next = stop ? voteForRank(stop.myVote, tier) : null
    if (next) send(id, next)
  }

  function voteFor(id: string, choice: string) {
    const kind = kindForChoice(choice)
    if (kind) send(id, kind)
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
          votesHint="Everyone’s votes, live. Tap your selection again to clear it."
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
