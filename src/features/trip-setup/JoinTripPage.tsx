import { useEffect, useRef, useState } from 'react'
import { isAbortError, isApiError, type MemberSession } from '../../api'
import { followInAppLink } from '../../state'
import { SetupPage } from './SetupPage'

export type JoinTripPageProps = {
  joinTrip: (name: string, signal?: AbortSignal) => Promise<MemberSession>
  /** This browser was a member, but the server stopped accepting its token. */
  rejoin: boolean
}

const maxName = 60

export function JoinTripPage({ joinTrip, rejoin }: JoinTripPageProps) {
  const [name, setName] = useState('')
  const [nameError, setNameError] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [busy, setBusy] = useState(false)
  const pending = useRef<AbortController | null>(null)

  useEffect(() => () => pending.current?.abort(), [])

  async function submit() {
    if (busy) return
    const trimmed = name.trim()
    if (!trimmed) return setNameError('Required')
    if (trimmed.length > maxName) return setNameError(`Use ${maxName} characters or fewer`)
    setNameError('')
    setSubmitError('')
    setBusy(true)
    const controller = new AbortController()
    pending.current = controller
    try {
      await joinTrip(trimmed, controller.signal)
    } catch (error) {
      if (isAbortError(error)) return
      setSubmitError(describeJoinError(error))
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
        eyebrow="YOU'RE INVITED ON A LITTLE ADVENTURE"
        title="Join the quest"
        description="Your party is planning a trip together. Choose the name they'll see next to your votes."
        actions={
          rejoin && (
            <p className="inline-warning mx-0 mt-5 mb-0 max-w-[700px]" role="status">
              Please join again. This browser's membership of the trip is no longer accepted.
            </p>
          )
        }
      >
        <article className="desk-card setup-details">
          <div className="section-title">
            <h3>Join this trip</h3>
            <span>No account needed</span>
          </div>
          <label>
            Your name
            <input
              value={name}
              maxLength={maxName}
              autoComplete="name"
              aria-invalid={nameError ? true : undefined}
              aria-describedby={nameError ? 'join-trip-name-error' : undefined}
              onChange={(e) => {
                setName(e.target.value)
                setNameError('')
              }}
            />
            {nameError && (
              <small id="join-trip-name-error" className="mt-1.5 block text-[11px] font-semibold text-cream">
                ⚠ {nameError}
              </small>
            )}
          </label>
          {submitError && (
            <p className="inline-warning mx-0 mt-4 mb-0" role="alert">
              {submitError}
            </p>
          )}
          <button className="primary setup-build" disabled={busy}>
            {busy ? 'Joining…' : 'Join trip →'}
          </button>
        </article>
        <article className="desk-card setup-details">
          <div className="section-title">
            <h3>About trip links</h3>
            <span>Share with care</span>
          </div>
          <p className="desk-copy">
            Anyone with this link can see the trip and join it by name. This browser remembers you after
            you join.
          </p>
          <p className="desk-copy mt-4">
            Planning something else?{' '}
            <a className="underline" href="/" onClick={followInAppLink}>
              Start a new trip
            </a>
          </p>
        </article>
      </SetupPage>
    </div>
  )
}

function describeJoinError(error: unknown): string {
  if (!isApiError(error)) return error instanceof Error ? error.message : 'Something went wrong joining this trip. Try again.'
  if (error.status === 404) return "This trip link doesn't exist. Check the link with whoever sent it."
  if (error.code === 'network_error') return "Can't reach the Questline server. Try again in a moment."
  return error.message
}
