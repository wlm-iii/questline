import type { Stop } from '../../demo/types'

export type PlaceDetailsDialogProps = {
  current: Stop
  interested: number
  owner: string
  note: string
  onOwnerChange: (name: string) => void
  onNoteChange: (text: string) => void
  onEdit: () => void
  onToggleSide: () => void
  onRemove: () => void
}
export function PlaceDetailsDialog({
  current,
  interested,
  owner,
  note,
  onOwnerChange,
  onNoteChange,
  onEdit,
  onToggleSide,
  onRemove,
}: PlaceDetailsDialogProps) {
  return (
    <>
      <span className="eyebrow">
        {current.category.toUpperCase()} ·{' '}
        {current.side ? 'SIDE QUEST' : 'MAIN QUEST'}
      </span>
      <h2>{current.name}</h2>
      <p>{current.description}</p>
      <div className="detail-stats">
        <span>
          {current.price ? `$${current.price} / person` : 'Free to explore'}
        </span>
        <span>{current.time}</span>
        <span>↗ {interested} interested</span>
      </div>
      <label>
        Who’s taking the lead?
        <select value={owner} onChange={(e) => onOwnerChange(e.target.value)}>
          <option value="">Anyone in the crew</option>
          {['Jerry', 'Alex', 'Morgan', 'Sam'].map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
      </label>
      <label>
        Notes & things to remember
        <textarea
          placeholder="Bring a picnic blanket, check opening hours…"
          value={note}
          onChange={(e) => onNoteChange(e.target.value)}
        />
      </label>
      <p className="saved-hint">
        Notes and owner changes save automatically on this device.
      </p>
      <div className="detail-actions">
        <button className="quiet" onClick={onEdit}>
          Edit waypoint
        </button>
        <button className="quiet" onClick={onToggleSide}>
          Make {current.side ? 'main' : 'side'} quest
        </button>
        <button className="danger" onClick={onRemove}>
          Remove
        </button>
      </div>
    </>
  )
}
