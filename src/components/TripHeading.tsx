import type { Trip } from '../demo/types'

export type TripHeadingProps = {
  trip: Trip
  onSettings: () => void
  onImport: () => void
}
export function TripHeading({ trip, onSettings, onImport }: TripHeadingProps) {
  return (
    <section className="trip-heading">
      <div>
        <div className="eyebrow">A LITTLE ADVENTURE, TOGETHER</div>
        <h1>{trip.name} </h1>
        <p>
          {new Date(trip.date + 'T12:00:00').toLocaleDateString('en-US', {
            weekday: 'long',
            month: 'long',
            day: 'numeric',
          })}{' '}
          <span>·</span> {trip.destination} <span>·</span> 4 adventurers
        </p>
      </div>
      <div className="trip-actions">
        <button className="quiet" onClick={onSettings}>
          Edit trip
        </button>
        <div className="avatars">
          <span>JS</span>
          <span>AL</span>
          <span>MK</span>
          <span>+1</span>
        </div>
        <button className="primary" onClick={onImport}>
          ＋ Import chat
        </button>
      </div>
    </section>
  )
}
