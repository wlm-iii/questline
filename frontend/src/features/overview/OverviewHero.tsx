export type OverviewHeroProps = {
  stopCount: number
  /** Without it the hero speaks of the demo's four people. */
  partySize?: number
  onExplore: () => void
}
export function OverviewHero({ stopCount, partySize, onExplore }: OverviewHeroProps) {
  return (
    <div className="overview-hero">
      <span className="eyebrow">THE PLAN IS COMING TOGETHER</span>
      <h2>
        Your next good day
        <br />
        starts right here.
      </h2>
      <p>
        {stopCount} places to explore.{' '}
        {partySize === undefined
          ? 'Four people'
          : `${partySize} ${partySize === 1 ? 'person' : 'people'}`}{' '}
        to make memories with.
      </p>
      <button className="primary" onClick={onExplore}>
        Explore the map →
      </button>
    </div>
  )
}
