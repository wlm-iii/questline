export type TravelCostsProps = {
  total: number
  travelMode: string
  gasPrice: number
  onTravelModeChange: (mode: string) => void
  onGasPriceChange: (price: number) => void
  /** Real route figures; without them the card shows the labelled sample scenario. */
  route?: { miles: number; minutes: number } | null
  /** Replaces `$total`, e.g. "$30–60". */
  totalLabel?: string
}
export function TravelCosts({
  total,
  travelMode,
  gasPrice,
  onTravelModeChange,
  onGasPriceChange,
  route,
  totalLabel,
}: TravelCostsProps) {
  const miles = route?.miles ?? 12
  return (
    <article className="desk-card">
      <div className="section-title">
        <h3>Travel & costs</h3>
        <span>Planning estimates</span>
      </div>
      <div className="mode-switch">
        {['Drive', 'Walk', 'Transit'].map((mode) => (
          <button
            className={travelMode === mode ? 'active' : ''}
            onClick={() => onTravelModeChange(mode)}
            key={mode}
          >
            {mode}
          </button>
        ))}
      </div>
      <div className="travel-metrics">
        <div>
          <span>Food + activities</span>
          <strong>
            {totalLabel ?? `$${total}`}
            <small> / person</small>
          </strong>
        </div>
        <div>
          <span>{route ? 'Route distance' : 'Sample route distance'}</span>
          <strong>
            {miles}
            <small> miles</small>
          </strong>
        </div>
        <div>
          <span>{route ? 'Drive time' : 'Sample travel time'}</span>
          <strong>
            {route
              ? route.minutes
              : travelMode === 'Drive'
              ? '45'
              : travelMode === 'Walk'
                ? '240'
                : '75'}
            <small> min</small>
          </strong>
        </div>
        {travelMode === 'Drive' && (
          <div>
            <span>Fuel estimate · 25 mpg</span>
            <strong>
              ${((miles / 25) * gasPrice).toFixed(2)}
              <small> / vehicle</small>
            </strong>
          </div>
        )}
      </div>
      {travelMode === 'Drive' && (
        <label>
          Gas price ($ / gallon)
          <input
            type="number"
            min="0"
            max="20"
            step="0.1"
            value={gasPrice}
            onChange={(e) => onGasPriceChange(Number(e.target.value))}
          />
        </label>
      )}
      <p className="desk-footnote">
        {route
          ? 'Distance and drive time come from the current questline. Fuel = route miles ÷ 25 mpg × gas price. Walking and transit are not routed. No fares or parking included.'
          : 'Distance and times use a fixed sample scenario, not live routing. Fuel = 12 miles ÷ 25 mpg × gas price. No fares or parking included.'}
      </p>
    </article>
  )
}
