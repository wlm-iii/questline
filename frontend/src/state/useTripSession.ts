import { useCallback, useEffect, useMemo, useSyncExternalStore } from 'react'
import {
  activeTripId,
  forgetSession,
  parseSessions,
  publicApi,
  rawSessions,
  saveSession,
  sessionFromJoin,
  setActiveTripId,
  subscribeToSessions,
  type MemberSession,
  type Trip,
  type Uuid,
} from '../api'
import { navigateToTrip, useTripRoute } from './tripRoute'
import { toTripCreate, type TripSetupErrors, type TripSetupForm } from './tripSetup'

export type TripSessionState =
  /** No trip link in the URL. `resumableTripId` is the last trip this browser joined, if any. */
  | { status: 'no-trip'; resumableTripId: Uuid | null }
  /** A trip link, but this browser hasn't joined that trip yet. */
  | { status: 'needs-join'; tripId: Uuid }
  | { status: 'ready'; session: MemberSession }

export type CreateTripResult = { ok: true; trip: Trip } | { ok: false; errors: TripSetupErrors }

const maxMemberName = 60

/** Which trip this browser is on, and as whom. Network and validation errors are thrown or returned to the caller. */
export function useTripSession() {
  const tripId = useTripRoute()
  const raw = useSyncExternalStore(subscribeToSessions, rawSessions)
  const lastTripId = useSyncExternalStore(subscribeToSessions, activeTripId)
  const sessions = useMemo(() => parseSessions(raw), [raw])
  const session = tripId ? sessions[tripId] ?? null : null

  useEffect(() => {
    if (session && activeTripId() !== session.tripId) setActiveTripId(session.tripId)
  }, [session])

  const state: TripSessionState = session
    ? { status: 'ready', session }
    : tripId
      ? { status: 'needs-join', tripId }
      : { status: 'no-trip', resumableTripId: lastTripId && sessions[lastTripId] ? lastTripId : null }

  /** Validates the form, creates the trip as its organizer, and opens its link. */
  const createTrip = useCallback(async (form: TripSetupForm, signal?: AbortSignal): Promise<CreateTripResult> => {
    const result = toTripCreate(form)
    if (!result.ok) return result
    const created = await publicApi.createTrip(result.request, { signal })
    saveSession(sessionFromJoin(created.trip.id, created))
    setActiveTripId(created.trip.id)
    navigateToTrip(created.trip.id)
    return { ok: true, trip: created.trip }
  }, [])

  /** Joins the trip in the URL under `name`. Throws ApiError `not_found` for an unknown trip. */
  const joinTrip = useCallback(async (name: string, signal?: AbortSignal): Promise<MemberSession> => {
    if (!tripId) throw new Error('Open a trip link before joining')
    const trimmed = name.trim()
    if (!trimmed || trimmed.length > maxMemberName) throw new Error(`Use a name of 1 to ${maxMemberName} characters`)
    const joined = sessionFromJoin(tripId, await publicApi.joinTrip(tripId, trimmed, { signal }))
    saveSession(joined)
    setActiveTripId(tripId)
    return joined
  }, [tripId])

  /** Forget this browser's membership of the current trip, for example after a 401. */
  const leaveTrip = useCallback(() => {
    if (tripId) forgetSession(tripId)
  }, [tripId])

  return { state, createTrip, joinTrip, leaveTrip }
}
