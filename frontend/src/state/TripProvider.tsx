import { useCallback, useEffect, useEffectEvent, useMemo, useRef, useState, type ReactNode } from 'react'
import { createMemberApi, type MemberApi, type MemberSession, type TripSnapshot } from '../api'
import { TripContext, type TripContextValue } from './tripContext'
import { createTripPoller, type TripPoller } from './tripPoller'

type TripProviderProps = {
  session: MemberSession
  /** The backend rejected this member's token; the caller should forget the session and ask to rejoin. */
  onUnauthorized: () => void
  children: ReactNode
}

/** Shares one polled trip snapshot with everything below it. State resets when the trip or member changes. */
export function TripProvider(props: TripProviderProps) {
  return <TripState key={`${props.session.tripId}:${props.session.memberId}`} {...props} />
}

function TripState({ session, onUnauthorized, children }: TripProviderProps) {
  const api = useMemo(() => createMemberApi(session.memberToken), [session.memberToken])
  const [snapshot, setSnapshot] = useState<TripSnapshot | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const pollerRef = useRef<TripPoller | null>(null)
  const handleUnauthorized = useEffectEvent(() => onUnauthorized())

  useEffect(() => {
    const poller = createTripPoller(session.tripId, api, {
      onSnapshot: setSnapshot,
      onError: setError,
      onUnauthorized: () => handleUnauthorized(),
    })
    pollerRef.current = poller
    poller.start()
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') void poller.refresh()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange)
      poller.stop()
      pollerRef.current = null
    }
  }, [session.tripId, api])

  const refresh = useCallback(() => pollerRef.current?.refresh() ?? Promise.resolve(), [])

  const mutate = useCallback(async <T,>(action: (api: MemberApi) => Promise<T>): Promise<T> => {
    try {
      return await action(api)
    } finally {
      await refresh()
    }
  }, [api, refresh])

  const value = useMemo<TripContextValue>(() => ({
    session,
    api,
    snapshot,
    me: snapshot?.members.find(member => member.id === session.memberId) ?? null,
    error,
    refresh,
    mutate,
  }), [session, api, snapshot, error, refresh, mutate])

  return <TripContext.Provider value={value}>{children}</TripContext.Provider>
}
