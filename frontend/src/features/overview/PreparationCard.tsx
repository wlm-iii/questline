import { TripEssentials } from '../../components/TripEssentials'

export type PreparationCardProps = {
  travelMode: string
  onSettings: () => void
  onReviewRoute: () => void
  onExport: () => void
}
export function PreparationCard({
  travelMode,
  onSettings,
  onReviewRoute,
  onExport,
}: PreparationCardProps) {
  return (
    <article className="overview-card">
      <div className="section-title">
        <h3>Before you head out</h3>
        <span>Trip essentials</span>
      </div>
      <TripEssentials travelMode={travelMode} />
      <button className="overview-action" onClick={onSettings}>
        ◷ Trip date & daily budget <span>→</span>
      </button>
      <button className="overview-action" onClick={onReviewRoute}>
        ◇ Review the questline <span>→</span>
      </button>
      <button className="overview-action" onClick={onExport}>
        ↓ Download your trip <span>→</span>
      </button>
    </article>
  )
}
