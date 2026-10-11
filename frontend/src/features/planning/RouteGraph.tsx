import type { Stop } from '../../demo/types'

export type RouteGraphProps = {
  stops: Stop[]
  done: number[]
  onReviewRoute: () => void
  onDetails: (id: number) => void
}
export function RouteGraph({
  stops,
  done,
  onReviewRoute,
  onDetails,
}: RouteGraphProps) {
  const main = stops.filter((stop) => !stop.side)
  return (
    <article className="desk-card route-graph">
      <div className="section-title">
        <h3>Your questline</h3>
        <button className="text-button" onClick={onReviewRoute}>
          Edit on map →
        </button>
      </div>
      <p className="desk-copy">
        Solid connections are the main path. Blue branches are optional side
        quests.
      </p>
      <div className="graph-flow">
        {main.map((stop, index) => (
          <div className="graph-stage" key={stop.id}>
            <button onClick={() => onDetails(stop.id)}>
              <span>{done.includes(stop.id) ? '✓' : index + 1}</span>
              <strong>{stop.name}</strong>
              <small>{stop.time}</small>
            </button>
            {index < main.length - 1 && (
              <div className="graph-connector">↓</div>
            )}
            {index === 0 && stops.some((s) => s.side) && (
              <div className="graph-branches">
                {stops
                  .filter((s) => s.side)
                  .map((side) => (
                    <button key={side.id} onClick={() => onDetails(side.id)}>
                      ↳ <span>✧ {side.name}</span>
                      <small>Optional branch</small>
                    </button>
                  ))}
              </div>
            )}
          </div>
        ))}
      </div>
      {main.length === 0 && (
        <div className="desk-empty">
          Promote a waypoint to start your main path.
        </div>
      )}
      <div className="graph-footer">
        <span>● Main path</span>
        <span className="blue">○ Side quest</span>
        <span>Illustrative sequence</span>
      </div>
    </article>
  )
}
