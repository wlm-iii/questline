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
          budgetLabel={
            plan
              ? `${plan.presetLabel} preset${plan.estimate.note ? ` · ${plan.estimate.note}` : ''}`
              : 'Build the questline for an estimate'
          }
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
