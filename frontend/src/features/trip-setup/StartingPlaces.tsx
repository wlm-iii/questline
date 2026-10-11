import type { Stop } from '../../demo/types'

export type StartingPlacesProps = {
  stops: Stop[]
  mainCount: number
  total: number
  onToggleSide: (id: number) => void
}
export function StartingPlaces({
  stops,
  mainCount,
  total,
  onToggleSide,
}: StartingPlacesProps) {
  return (
    <article className="desk-card setup-options">
      <div className="section-title">
        <h3>The possibilities</h3>
        <span>{stops.length} places</span>
      </div>
      <p className="desk-copy">
        Choose the stops to start with. You can add places, vote, and change
        priorities after building the plan.
      </p>
      <div className="setup-stop-list">
        {stops.map((stop) => (
          <label key={stop.id} className="setup-stop">
            <input
              type="checkbox"
              checked={!stop.side}
              onChange={() => onToggleSide(stop.id)}
            />
            <span>
              <strong>{stop.name}</strong>
              <small>
                {stop.category} ·{' '}
                {stop.price ? `$${stop.price} per person` : 'Free'}
              </small>
            </span>
            <span className="setup-status">
              {stop.side ? 'Side quest' : 'Main quest'}
            </span>
          </label>
        ))}
      </div>
      <div className="setup-summary">
        <span>
          {mainCount} main stops · {stops.length - mainCount} optional
        </span>
        <strong>${total} / person</strong>
      </div>
      <p className="desk-footnote">
        This demo uses an illustrated San Francisco map. The route follows tier
        priority and nearby layout positions, not road routing. Preferences are
        saved for review; live weather and route validation are not connected.
      </p>
      <button className="primary setup-build" disabled={!mainCount}>
        Build my questline →
      </button>
    </article>
  )
}
