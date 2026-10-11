export type RouteGraphStop<I extends string | number> = {
  id: I
  name: string
  side: boolean
  time: string
  /** Side quests: the main stop they branch from. Missing → under the first stop (demo). */
  anchorId?: I | null
  /** Side quests: e.g. "+6 min". Defaults to "Optional branch". */
  branchNote?: string
}

export type RouteGraphProps<I extends string | number> = {
  stops: RouteGraphStop<I>[]
  done: I[]
  onReviewRoute: () => void
  onDetails: (id: I) => void
  emptyText?: string
  footnote?: string
}

export function RouteGraph<I extends string | number>({
  stops,
  done,
  onReviewRoute,
  onDetails,
  emptyText = 'Promote a waypoint to start your main path.',
  footnote = 'Illustrative sequence',
}: RouteGraphProps<I>) {
  const main = stops.filter((stop) => !stop.side)
  const sides = stops.filter((stop) => stop.side)
  const branchesOf = (stop: RouteGraphStop<I>, index: number) =>
    sides.filter(
      (side) =>
        side.anchorId === stop.id ||
        (index === 0 && !main.some((m) => m.id === side.anchorId)),
    )
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
        {main.map((stop, index) => {
          const branches = branchesOf(stop, index)
          return (
            <div className="graph-stage" key={stop.id}>
              <button onClick={() => onDetails(stop.id)}>
                <span>{done.includes(stop.id) ? '✓' : index + 1}</span>
                <strong>{stop.name}</strong>
                <small>{stop.time}</small>
              </button>
              {index < main.length - 1 && (
                <div className="graph-connector">↓</div>
              )}
              {branches.length > 0 && (
                <div className="graph-branches">
                  {branches.map((side) => (
                    <button key={side.id} onClick={() => onDetails(side.id)}>
                      ↳ <span>✧ {side.name}</span>
                      <small>{side.branchNote ?? 'Optional branch'}</small>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
      {main.length === 0 && <div className="desk-empty">{emptyText}</div>}
      <div className="graph-footer">
        <span>● Main path</span>
        <span className="blue">○ Side quest</span>
        <span>{footnote}</span>
      </div>
    </article>
  )
}
