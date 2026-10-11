import type { Stop } from '../../demo/types'
import { QuestCard } from '../../components/QuestCard'

export type PlaceCardProps = {
  current: Stop
  number: string
  voter: string
  vote: string | undefined
  className?: string
  onVoterChange: (name: string) => void
  onVote: (choice: string) => void
  onView: () => void
  onToggleSide: () => void
}
export function PlaceCard({
  current,
  number,
  voter,
  vote,
  className = '',
  onVoterChange,
  onVote,
  onView,
  onToggleSide,
}: PlaceCardProps) {
  return (
    <QuestCard
      className={className}
      title={current.name}
      description={current.description}
      kind={current.side ? 'side' : 'main'}
      number={number}
      status={
        current.price
          ? `$${current.price} / person · ${current.time}`
          : `Free · ${current.time}`
      }
      onView={onView}
    >
      <label className="voter-inline">
        Voting as{' '}
        <select
          aria-label="Active voting member"
          value={voter}
          onChange={(e) => onVoterChange(e.target.value)}
        >
          {['Jerry', 'Alex', 'Morgan', 'Sam'].map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
      </label>
      <div className="vote-row">
        <span>Your vote</span>
        {['I’m in', 'Maybe', 'Skip'].map((v, i) => (
          <button
            key={v}
            className={vote === v ? 'voted' : ''}
            onClick={() => onVote(v)}
          >
            {['↗', '〜', '−'][i]} {v}
          </button>
        ))}
      </div>
      <button className="text-button" onClick={onToggleSide}>
        Make {current.side ? 'main' : 'side'} quest ↗
      </button>
    </QuestCard>
  )
}
