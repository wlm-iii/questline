export type OverviewHeroProps = {
  stopCount: number
  onExplore: () => void
}
export function OverviewHero({ stopCount, onExplore }: OverviewHeroProps) {
  return (
    <div className="overview-hero">
      <span className="eyebrow">THE PLAN IS COMING TOGETHER</span>
      <h2>
        Your next good day
        <br />
        starts right here.
      </h2>
      <p>{stopCount} places to explore. Four people to make memories with.</p>
      <button className="primary" onClick={onExplore}>
        Explore the map →
      </button>
    </div>
  )
}
