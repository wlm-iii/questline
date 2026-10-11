export type EmptyMapProps = { onAddWaypoint: () => void }

export function EmptyMap({ onAddWaypoint }: EmptyMapProps) {
  return (
    <div className="empty-map">
      <h2>A fresh start.</h2>
      <p>Add your first waypoint to start an adventure.</p>
      <button className="primary" onClick={onAddWaypoint}>
        ＋ Add waypoint
      </button>
    </div>
  )
}
