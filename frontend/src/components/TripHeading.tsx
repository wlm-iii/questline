import type { Trip } from '../demo/types'

export type TripHeadingMember = {
  id: string
  name: string
  initials: string
}

export type TripHeadingProps = {
  trip: Pick<Trip, 'name' | 'destination'> & { date?: string }
  /** Replaces the label formatted from `trip.date`, for example a date range. */
  dateLabel?: string
  /** The party; without it the heading shows the demo crew. */
  members?: TripHeadingMember[]
  /** "Edit trip" is hidden when absent. */
  onSettings?: () => void
  /** "Import chat" is hidden when absent. */
  onImport?: () => void
}

const shownAvatars = 3

export function TripHeading({ trip, dateLabel, members, onSettings, onImport }: TripHeadingProps) {
  return (
    <section className="trip-heading">
      <div>
        <div className="eyebrow">A LITTLE ADVENTURE, TOGETHER</div>
        <h1>{trip.name} </h1>
        <p>
          {dateLabel ??
            new Date(trip.date + 'T12:00:00').toLocaleDateString('en-US', {
              weekday: 'long',
              month: 'long',
              day: 'numeric',
            })}{' '}
          <span>·</span> {trip.destination} <span>·</span>{' '}
          {members ? `${members.length} ${members.length === 1 ? 'adventurer' : 'adventurers'}` : '4 adventurers'}
        </p>
      </div>
      <div className="trip-actions">
        {onSettings && (
          <button className="quiet" onClick={onSettings}>
            Edit trip
          </button>
        )}
        {members ? (
          <div className="avatars">
            {members.slice(0, shownAvatars).map((member) => (
              <span key={member.id} title={member.name}>
                {member.initials}
              </span>
            ))}
            {members.length > shownAvatars && (
              <span title={members.slice(shownAvatars).map((member) => member.name).join(', ')}>
                +{members.length - shownAvatars}
              </span>
            )}
          </div>
        ) : (
          <div className="avatars">
            <span>JS</span>
            <span>AL</span>
            <span>MK</span>
            <span>+1</span>
          </div>
        )}
        {onImport && (
          <button className="primary" onClick={onImport}>
            ＋ Import chat
          </button>
        )}
      </div>
    </section>
  )
}
