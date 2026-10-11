import type { VoteKind } from '../../api'
import { QuestButton } from '../../components/QuestButton'
import type { StopView } from '../adapters'
import { StatusBadge } from './StatusBadge'
import { VoteButtons } from './VoteButtons'

export type TripPlaceCardProps = {
  stop: StopView
  voting: boolean
  onVote: (stop: StopView, kind: VoteKind) => void
  onView: () => void
}

export function TripPlaceCard({ stop, voting, onVote, onView }: TripPlaceCardProps) {
  const quote = stop.quotes[0]
  const number = stop.status === 'main' && stop.number ? String(stop.number).padStart(2, '0') : stop.status === 'side' ? '✧' : '—'
  return (
    <article className="quest-card place-card">
      <div className="quest-card-header">
        <StatusBadge status={stop.status} />
        <span className="quest-number" aria-label={`Quest ${number}`}>{number}</span>
      </div>
      <div className="quest-card-body">
        <h3>{stop.name}</h3>
        <p className="quest-description">
          {stop.categoryLabel} · {stop.address}
        </p>
        <p className="quest-description">
          {quote ? `“${quote.text}” — ${quote.author}` : stop.mentionedBy ? `Mentioned by ${stop.mentionedBy}` : stop.sourceLabel}
        </p>
        {stop.why && <p className="quest-description">Why: {stop.why}</p>}
      </div>
      <VoteButtons stop={stop} pending={voting} onVote={onVote} />
      <div className="quest-card-footer">
        <span>
          {stop.arrive && `Arrive ${stop.arrive} · `}
          {stop.cost}
          {stop.detour && ` · ${stop.detour}`}
          {stop.done && ' · ✓ Complete'}
        </span>
        <QuestButton onClick={onView}>View quest</QuestButton>
      </div>
    </article>
  )
}
