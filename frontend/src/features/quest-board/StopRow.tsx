import type { Stop } from '../../demo/types'
import { QuestBadge } from '../../components/QuestBadge'

export type StopRowProps = {
  stop: Stop
  number: number
  selected: boolean
  tab: string
  interested: number
  owner: string
  done: boolean
  accepted: boolean
  canMoveEarlier: boolean
  canMoveLater: boolean
  onSelect: (id: number) => void
  onMove: (id: number, offset: number) => void
  onDetails: (id: number) => void
  onToggleDone: (id: number) => void
}
export function StopRow({
  stop,
  number,
  selected,
  tab,
  interested,
  owner,
  done,
  accepted,
  canMoveEarlier,
  canMoveLater,
  onSelect,
  onMove,
  onDetails,
  onToggleDone,
}: StopRowProps) {
  return (
    <div className={`stop-row ${selected ? 'chosen' : ''}`}>
      <button className="stop-select" onClick={() => onSelect(stop.id)}>
        <span className={`stop-number ${stop.side ? 'side' : ''}`}>
          {stop.side ? '✧' : number}
        </span>
        <span className="stop-info">
          <strong>{stop.name}</strong>
          <small>
            {tab === 'Questline' ? stop.time : stop.category} <span>·</span>{' '}
            {stop.price ? `$${stop.price}` : 'Free'}
          </small>
          <QuestBadge kind={stop.side ? 'side' : 'main'} />
        </span>
        <span className="vote-count">↗ {interested}</span>
      </button>
      {tab === 'Questline' && (
        <div className="row-actions">
          <button
            disabled={!canMoveEarlier}
            aria-label={`Move ${stop.name} earlier`}
            onClick={() => onMove(stop.id, -1)}
          >
            ↑ Earlier
          </button>
          <button
            disabled={!canMoveLater}
            aria-label={`Move ${stop.name} later`}
            onClick={() => onMove(stop.id, 1)}
          >
            ↓ Later
          </button>
          <button onClick={() => onDetails(stop.id)}>Edit</button>
        </div>
      )}
      {tab === 'Quest log' && (
        <p className="owner-label">Owner: {owner || 'Anyone in the crew'}</p>
      )}
      {tab === 'Quest log' && (
        <label className="complete">
          <input
            type="checkbox"
            disabled={!accepted}
            checked={done}
            onChange={() => onToggleDone(stop.id)}
          />{' '}
          Quest complete
        </label>
      )}
    </div>
  )
}
