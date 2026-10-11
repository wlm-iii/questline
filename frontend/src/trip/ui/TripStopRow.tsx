import type { ReactNode } from 'react'
import type { StopView } from '../adapters'

export type TripStopRowProps = {
  stop: StopView
  /** Number for a main quest, ✧ for a side quest, · for a candidate. */
  marker: string
  hollow: boolean
  selected: boolean
  details: string[]
  badge?: ReactNode
  onSelect: (id: string) => void
  children?: ReactNode
}

export function TripStopRow({ stop, marker, hollow, selected, details, badge, onSelect, children }: TripStopRowProps) {
  return (
    <div className={`stop-row ${selected ? 'chosen' : ''}`}>
      <button className="stop-select" aria-pressed={selected} onClick={() => onSelect(stop.id)}>
        <span className={`stop-number ${hollow ? 'side' : ''}`}>{marker}</span>
        <span className="stop-info">
          <strong>{stop.name}</strong>
          {details.map(detail => (
            <small key={detail}>{detail}</small>
          ))}
          {badge}
        </span>
        {stop.done && <span className="vote-count" aria-label="Quest complete">✓</span>}
      </button>
      {children}
    </div>
  )
}
