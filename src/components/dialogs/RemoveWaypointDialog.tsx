import type { Stop } from '../../demo/types'

export type RemoveWaypointDialogProps = { current: Stop; onKeep: () => void; onRemove: () => void }
export function RemoveWaypointDialog({ current, onKeep, onRemove }: RemoveWaypointDialogProps) {
 return <><span className="eyebrow">EDIT YOUR ADVENTURE</span><h2>Remove {current.name}?</h2><p>This removes the waypoint from your board and illustrated route.</p><div className="detail-actions"><button className="quiet" onClick={onKeep}>Keep waypoint</button><button className="danger" onClick={onRemove}>Remove waypoint</button></div></>
}
