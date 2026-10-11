import { isAbortError, isApiError, type MemberApi, type TripSnapshot, type Uuid } from '../api'

export const POLL_INTERVAL_MS = 3000

export type TripPollerEvents = {
  onSnapshot(snapshot: TripSnapshot): void
  /** Called with the latest failure, or null once a request succeeds again. Polling continues. */
  onError(error: Error | null): void
  /** The member token was rejected. Polling stops. */
  onUnauthorized(): void
}

export type TripPollerOptions = {
  intervalMs?: number
  isVisible?: () => boolean
}

export type TripPoller = {
  start(): void
  stop(): void
  /** Fetch now, superseding any request in flight. Resolves when this fetch settles. */
  refresh(): Promise<void>
}

/**
 * Polls `GET /trips/{id}?revision=N`. Sends the last revision it saw, so an unchanged trip costs a tiny
 * response; keeps the snapshot on `unchanged`; never replaces a snapshot with an older revision; and
 * skips ticks while the page is hidden.
 */
export function createTripPoller(tripId: Uuid, api: MemberApi, events: TripPollerEvents, options: TripPollerOptions = {}): TripPoller {
  const intervalMs = options.intervalMs ?? POLL_INTERVAL_MS
  const isVisible = options.isVisible ?? (() => typeof document === 'undefined' || document.visibilityState === 'visible')
  let revision: number | undefined
  let running = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let inFlight: AbortController | undefined

  function schedule() {
    clearTimeout(timer)
    timer = running ? setTimeout(() => { if (isVisible()) void fetchNow() }, intervalMs) : undefined
  }

  async function fetchNow(): Promise<void> {
    if (!running) return
    clearTimeout(timer)
    inFlight?.abort()
    const controller = new AbortController()
    inFlight = controller
    try {
      const result = await api.getTrip(tripId, revision, { signal: controller.signal })
      if (controller !== inFlight || !running) return
      if (!('unchanged' in result) && (revision === undefined || result.revision >= revision)) {
        revision = result.revision
        events.onSnapshot(result)
      }
      events.onError(null)
    } catch (error) {
      if (isAbortError(error) || controller !== inFlight || !running) return
      if (isApiError(error) && error.status === 401) {
        stop()
        events.onUnauthorized()
        return
      }
      events.onError(error instanceof Error ? error : new Error(String(error)))
    }
    inFlight = undefined
    schedule()
  }

  function stop() {
    running = false
    clearTimeout(timer)
    timer = undefined
    inFlight?.abort()
    inFlight = undefined
  }

  return {
    start() {
      if (running) return
      running = true
      void fetchNow()
    },
    stop,
    refresh: fetchNow,
  }
}
