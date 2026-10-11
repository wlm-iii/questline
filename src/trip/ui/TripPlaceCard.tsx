import { QuestButton } from '../../components/QuestButton'
import type { StopView } from '../adapters'
import { StatusBadge } from './StatusBadge'

export type TripPlaceCardProps = { stop: StopView; onView: () => void }

export function TripPlaceCard({ stop, onView }: TripPlaceCardProps) {
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
      </div>
      <div className="quest-card-footer">
        <span>
          {stop.cost}
          {stop.detour && ` · ${stop.detour}`}
          {stop.done && ' · ✓ Complete'}
        </span>
        <QuestButton onClick={onView}>View quest</QuestButton>
      </div>
    </article>
  )
}
