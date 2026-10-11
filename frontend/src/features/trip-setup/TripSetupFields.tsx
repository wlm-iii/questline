import type { Trip, Constraints } from '../../demo/types'

export type TripSetupFieldsProps = {
  trip: Trip
  constraints: Constraints
  travelMode: string
  onTripChange: (trip: Trip) => void
  onConstraintsChange: (constraints: Constraints) => void
  onTravelModeChange: (mode: string) => void
}
export function TripSetupFields({
  trip,
  constraints,
  travelMode,
  onTripChange,
  onConstraintsChange,
  onTravelModeChange,
}: TripSetupFieldsProps) {
  return (
    <article className="desk-card setup-details">
      <div className="section-title">
        <h3>Your adventure</h3>
        <span>Start with the basics</span>
      </div>
      <label>
        Trip name
        <input
          required
          maxLength={70}
          value={trip.name}
          onChange={(e) => onTripChange({ ...trip, name: e.target.value })}
        />
      </label>
      <div className="form-columns">
        <label>
          Date
          <input
            required
            type="date"
            value={trip.date}
            onChange={(e) => onTripChange({ ...trip, date: e.target.value })}
          />
        </label>
        <label>
          Daily budget / person ($)
          <input
            required
            type="number"
            min="1"
            max="10000"
            value={trip.budget}
            onChange={(e) =>
              onTripChange({ ...trip, budget: Number(e.target.value) })
            }
          />
        </label>
      </div>
      <label>
        Destination
        <input
          required
          value={trip.destination}
          onChange={(e) =>
            onTripChange({ ...trip, destination: e.target.value })
          }
        />
      </label>
      <label>
        How will you travel?
        <select
          value={travelMode}
          onChange={(e) => onTravelModeChange(e.target.value)}
        >
          {['Drive', 'Walk', 'Transit'].map((mode) => (
            <option key={mode}>{mode}</option>
          ))}
        </select>
      </label>
      <div className="form-columns">
        <label>
          Back by
          <input
            type="time"
            value={constraints.returnBy}
            onChange={(e) =>
              onConstraintsChange({ ...constraints, returnBy: e.target.value })
            }
          />
        </label>
        <label>
          Max walking / leg (minutes)
          <input
            type="number"
            min="0"
            max="240"
            value={constraints.maxWalk}
            onChange={(e) =>
              onConstraintsChange({
                ...constraints,
                maxWalk: Number(e.target.value),
              })
            }
          />
        </label>
      </div>
      <label>
        Food & accessibility preferences
        <input
          value={constraints.dietary}
          onChange={(e) =>
            onConstraintsChange({ ...constraints, dietary: e.target.value })
          }
        />
      </label>
      <label>
        Mobility notes
        <input
          value={constraints.mobility}
          onChange={(e) =>
            onConstraintsChange({ ...constraints, mobility: e.target.value })
          }
        />
      </label>
    </article>
  )
}
