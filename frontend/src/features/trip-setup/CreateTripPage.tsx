import { useEffect, useRef, useState } from 'react'
import { isAbortError, isApiError, type Uuid } from '../../api'
import {
  browserTimezone,
  demoPath,
  followInAppLink,
  type CreateTripResult,
  type TripSetupForm,
} from '../../state'
import type { Constraints } from '../../demo/types'
import { useSaved } from '../../lib/useSaved'
import { SetupPage } from './SetupPage'
import { CreateTripFields, type CreateTripErrors, type CreateTripValues } from './CreateTripFields'

export type CreateTripPageProps = {
  createTrip: (form: TripSetupForm, signal?: AbortSignal) => Promise<CreateTripResult>
  resumableTripId: Uuid | null
}

const defaultConstraints: Constraints = { returnBy: '18:00', maxWalk: 30, dietary: '', mobility: '' }

export function CreateTripPage({ createTrip, resumableTripId }: CreateTripPageProps) {
  const [values, setValues] = useState<CreateTripValues>(() => {
    const today = localToday()
    return { name: '', origin: '', destination: '', startDate: today, endDate: today, organizerName: '' }
  })
  const [errors, setErrors] = useState<CreateTripErrors>({})
  const [submitError, setSubmitError] = useState('')
  const [busy, setBusy] = useState(false)
  const [travelMode, setTravelMode] = useSaved('questline-device-travel', 'Drive')
  const [constraints, setConstraints] = useSaved('questline-device-constraints', defaultConstraints)
  const [timezone] = useState(browserTimezone)
  const pending = useRef<AbortController | null>(null)

  useEffect(() => () => pending.current?.abort(), [])

  function changeValues(next: CreateTripValues) {
    const startMoved = next.startDate !== values.startDate
    const followStart = !values.endDate || values.endDate === values.startDate || values.endDate < next.startDate
    const updated = startMoved && followStart ? { ...next, endDate: next.startDate } : next
    setValues(updated)
    setErrors(Object.fromEntries(
      Object.entries(errors).filter(([key]) => updated[key as keyof CreateTripValues] === values[key as keyof CreateTripValues]),
    ))
  }

  async function submit() {
    if (busy) return
    setSubmitError('')
    setBusy(true)
    const controller = new AbortController()
    pending.current = controller
    try {
      const result = await createTrip(values, controller.signal)
      if (!result.ok) setErrors(result.errors)
    } catch (error) {
      if (isAbortError(error)) return
      setSubmitError(describeCreateError(error))
    } finally {
      if (pending.current === controller) pending.current = null
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen">
      <SetupPage
        onBuildPlan={submit}
        noValidate
        description="Start a shared trip, send the link to your party, and plan it together."
        actions={
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <ol className="m-0 w-full list-decimal pl-5 text-sm leading-6 text-bark">
              <li>Create the trip.</li>
              <li>Tap <strong>Link iMessage</strong> and send it in your group chat.</li>
              <li>Places your group mentions appear on the map.</li>
              <li>Vote or rank them, then <strong>Build</strong> the questline.</li>
            </ol>
            {resumableTripId && (
              <a className="quiet inline-block" href={`/t/${resumableTripId}`} onClick={followInAppLink}>
                Resume your trip
              </a>
            )}
            <a className="quiet inline-block" href={demoPath} onClick={followInAppLink}>
              Try the demo
            </a>
          </div>
        }
      >
        <CreateTripFields
          values={values}
          errors={errors}
          timezone={timezone}
          travelMode={travelMode}
          constraints={constraints}
          busy={busy}
          submitError={submitError}
          onValuesChange={changeValues}
          onTravelModeChange={setTravelMode}
          onConstraintsChange={setConstraints}
        />
      </SetupPage>
    </div>
  )
}

function describeCreateError(error: unknown): string {
  if (isApiError(error)) return error.code === 'network_error' ? "Can't reach the Questline server. Try again in a moment." : error.message
  return 'Something went wrong creating your trip. Try again.'
}

function localToday(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}
