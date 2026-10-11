import type { VoteKind } from '../../api'
import { voteKinds, voteLabels, type StopView } from '../adapters'

export type VoteButtonsProps = {
  stop: StopView
  /** True while this member's vote on the stop is being saved. */
  pending: boolean
  onVote: (stop: StopView, kind: VoteKind) => void
  className?: string
}

/** I'm in / Sure / Skip with tallies. Tapping your current vote again clears it. */
export function VoteButtons({ stop, pending, onVote, className = 'vote-row' }: VoteButtonsProps) {
  const voters = voteKinds.flatMap(kind => stop.votes[kind].map(name => `${name}: ${voteLabels[kind]}`))
  return (
    <div className={className} role="group" aria-label={`Vote on ${stop.name}`}>
      <span title={voters.join(', ') || 'No votes yet'}>{stop.contested ? '⚠ Contested' : voters.length ? `${voters.length} voted` : 'Vote'}</span>
      {voteKinds.map(kind => (
        <button
          key={kind}
          className={stop.myVote === kind ? 'voted' : ''}
          aria-pressed={stop.myVote === kind}
          disabled={pending}
          onClick={event => {
            event.stopPropagation()
            onVote(stop, kind)
          }}
        >
          {voteLabels[kind]} {stop.votes[kind].length > 0 && <b>{stop.votes[kind].length}</b>}
        </button>
      ))}
    </div>
  )
}
