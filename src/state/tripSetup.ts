import type { TripCreate } from '../api'

/** What the setup form collects. `endDate` defaults to `startDate` (a one-day trip). */
export type TripSetupForm = {
  name: string
  origin: string
  destination: string
  startDate: string
  endDate?: string
  organizerName: string
}

export type TripSetupErrors = Partial<Record<keyof TripSetupForm, string>>

export type TripSetupResult =
  | { ok: true; request: TripCreate }
  | { ok: false; errors: TripSetupErrors }

// Mirrors the TripCreate limits in backend/src/questline/schemas.py. The backend answers invalid
// fields with a generic message, so the form has to explain problems itself.
const maxLength = { name: 100, origin: 200, destination: 200, organizerName: 60 } as const
const maxExtraDays = 2
const isoDate = /^\d{4}-\d{2}-\d{2}$/

export function browserTimezone(): string {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' } catch { return 'UTC' }
}

export function toTripCreate(form: TripSetupForm, timezone = browserTimezone()): TripSetupResult {
  const name = form.name.trim()
  const origin = form.origin.trim()
  const destination = form.destination.trim()
  const organizerName = form.organizerName.trim()
  const startDate = form.startDate
  const endDate = form.endDate || form.startDate
  const errors: TripSetupErrors = {}

  const required = { name, origin, destination, organizerName }
  for (const key of Object.keys(required) as (keyof typeof required)[]) {
    if (!required[key]) errors[key] = 'Required'
    else if (required[key].length > maxLength[key]) errors[key] = `Use ${maxLength[key]} characters or fewer`
  }

  const start = parseDate(startDate)
  const end = parseDate(endDate)
  if (start === null) errors.startDate = 'Choose a start date'
  if (end === null) errors.endDate = 'Choose an end date'
  if (start !== null && end !== null) {
    const extraDays = Math.round((end - start) / 86_400_000)
    if (extraDays < 0) errors.endDate = 'End date must be on or after the start date'
    else if (extraDays > maxExtraDays) errors.endDate = 'Trips can last one to three days'
  }

  if (Object.keys(errors).length > 0) return { ok: false, errors }
  return {
    ok: true,
    request: { name, origin, destination, start_date: startDate, end_date: endDate, timezone, organizer_name: organizerName },
  }
}

function parseDate(value: string): number | null {
  if (!isoDate.test(value)) return null
  const [year, month, day] = value.split('-').map(Number)
  const time = Date.UTC(year, month - 1, day)
  const date = new Date(time)
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day ? time : null
}
