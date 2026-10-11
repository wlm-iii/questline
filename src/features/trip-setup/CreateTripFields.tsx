import type { ComponentProps, ReactNode } from 'react'
import type { Constraints } from '../../demo/types'

export type CreateTripValues = {
  name: string
  origin: string
  destination: string
  startDate: string
  endDate: string
  organizerName: string
}
export type CreateTripErrors = Partial<Record<keyof CreateTripValues, string>>

export type CreateTripFieldsProps = {
  values: CreateTripValues
  errors: CreateTripErrors
  timezone: string
  travelMode: string
  constraints: Constraints
  busy: boolean
  /** A failure from the server, shown above the submit button. */
  submitError: string
  onValuesChange: (values: CreateTripValues) => void
  onTravelModeChange: (mode: string) => void
  onConstraintsChange: (constraints: Constraints) => void
}

const maxExtraDays = 2

export function CreateTripFields({
  values,
  errors,
  timezone,
  travelMode,
  constraints,
  busy,
  submitError,
  onValuesChange,
  onTravelModeChange,
  onConstraintsChange,
}: CreateTripFieldsProps) {
  function field(key: keyof CreateTripValues, label: string, input: ComponentProps<'input'> = {}): ReactNode {
    const error = errors[key]
    return (
      <label>
        {label}
        <input
          {...input}
          value={values[key]}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `create-trip-${key}-error` : undefined}
          onChange={(e) => onValuesChange({ ...values, [key]: e.target.value })}
        />
        {error && (
          <small id={`create-trip-${key}-error`} className="mt-1.5 block text-[11px] font-semibold text-cream">
            ⚠ {error}
          </small>
        )}
      </label>
    )
  }

  return (
    <>
      <article className="desk-card setup-details">
        <div className="section-title">
          <h3>Your adventure</h3>
          <span>Shared with your party</span>
        </div>
        {field('name', 'Trip name', { maxLength: 100, autoComplete: 'off' })}
        <div className="form-columns">
          {field('origin', 'Starting from', { maxLength: 200, placeholder: 'San Jose, CA' })}
          {field('destination', 'Destination', { maxLength: 200, placeholder: 'Big Sur, CA' })}
        </div>
        <div className="form-columns">
          {field('startDate', 'Start date', { type: 'date' })}
          {field('endDate', 'End date', {
            type: 'date',
            min: values.startDate || undefined,
            max: addDays(values.startDate, maxExtraDays),
          })}
        </div>
        <label>
          Time zone (from this browser)
          <input readOnly value={timezone} />
        </label>
        {field('organizerName', 'Your name', { maxLength: 60, autoComplete: 'name' })}
        <p className="desk-footnote">
          Trips last one to three days. Include the city or region in each place so we can find it.
        </p>
      </article>
      <article className="desk-card setup-details">
        <div className="section-title">
          <h3>Your preferences</h3>
          <span>Saved on this device only</span>
        </div>
        <p className="desk-copy">
          These stay in this browser and aren't shared with your party yet.
        </p>
        <label>
          How will you travel?
          <select value={travelMode} onChange={(e) => onTravelModeChange(e.target.value)}>
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
              onChange={(e) => onConstraintsChange({ ...constraints, returnBy: e.target.value })}
            />
          </label>
          <label>
            Max walking / leg (minutes)
            <input
              type="number"
              min="0"
              max="240"
              value={constraints.maxWalk}
              onChange={(e) => onConstraintsChange({ ...constraints, maxWalk: Number(e.target.value) })}
            />
          </label>
        </div>
        <label>
          Food & accessibility preferences
          <input
            value={constraints.dietary}
            onChange={(e) => onConstraintsChange({ ...constraints, dietary: e.target.value })}
          />
        </label>
        <label>
          Mobility notes
          <input
            value={constraints.mobility}
            onChange={(e) => onConstraintsChange({ ...constraints, mobility: e.target.value })}
          />
        </label>
        <p className="desk-footnote">
          Anyone with the trip link can see this trip and join it by name.
        </p>
        {submitError && (
          <p className="inline-warning mx-0 mt-4 mb-0" role="alert">
            {submitError}
          </p>
        )}
        <button className="primary setup-build" disabled={busy}>
          {busy ? 'Creating your trip…' : 'Create trip →'}
        </button>
      </article>
    </>
  )
}

function addDays(isoDate: string, days: number): string | undefined {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate)
  if (!match) return undefined
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + days))
  return date.toISOString().slice(0, 10)
}
