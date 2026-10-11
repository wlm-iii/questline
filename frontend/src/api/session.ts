import type { JoinResult, Uuid } from './types'

/** Who this browser is on one trip. The token is a credential: never log it or put it in a URL. */
export type MemberSession = {
  tripId: Uuid
  memberId: Uuid
  memberName: string
  memberToken: string
}

const sessionsKey = 'questline-member-sessions'
const activeTripKey = 'questline-active-trip'
const changeEvent = 'questline-session-change'

export function sessionFromJoin(tripId: Uuid, result: JoinResult): MemberSession {
  return { tripId, memberId: result.member.id, memberName: result.member.name, memberToken: result.member_token }
}

export function loadSession(tripId: Uuid): MemberSession | null {
  return parseSessions(rawSessions())[tripId] ?? null
}

export function saveSession(session: MemberSession): void {
  writeSessions({ ...parseSessions(rawSessions()), [session.tripId]: session })
}

/** Drop a session, for example after the backend rejects its token with 401. */
export function forgetSession(tripId: Uuid): void {
  const sessions = parseSessions(rawSessions())
  delete sessions[tripId]
  writeSessions(sessions)
  if (activeTripId() === tripId) setActiveTripId(null)
}

export function activeTripId(): Uuid | null {
  try { return localStorage.getItem(activeTripKey) } catch { return null }
}

export function setActiveTripId(tripId: Uuid | null): void {
  try {
    if (tripId) localStorage.setItem(activeTripKey, tripId)
    else localStorage.removeItem(activeTripKey)
  } catch { /* Storage may be unavailable in private sessions. */ }
  notify()
}

/** The stored sessions as a string, so `useSyncExternalStore` can compare snapshots cheaply. */
export function rawSessions(): string | null {
  try { return localStorage.getItem(sessionsKey) } catch { return null }
}

export function parseSessions(raw: string | null): Record<Uuid, MemberSession> {
  try {
    const parsed: unknown = JSON.parse(raw ?? '{}')
    if (typeof parsed !== 'object' || parsed === null) return {}
    return Object.fromEntries(Object.entries(parsed).filter(([tripId, value]) => isSession(value) && value.tripId === tripId))
  } catch {
    return {}
  }
}

/** Calls `listener` when sessions change in this tab or another one. */
export function subscribeToSessions(listener: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === sessionsKey || event.key === activeTripKey) listener()
  }
  window.addEventListener(changeEvent, listener)
  window.addEventListener('storage', onStorage)
  return () => {
    window.removeEventListener(changeEvent, listener)
    window.removeEventListener('storage', onStorage)
  }
}

function writeSessions(sessions: Record<Uuid, MemberSession>): void {
  try { localStorage.setItem(sessionsKey, JSON.stringify(sessions)) } catch { /* Storage may be unavailable in private sessions. */ }
  notify()
}

function notify(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(changeEvent))
}

function isSession(value: unknown): value is MemberSession {
  if (typeof value !== 'object' || value === null) return false
  const session = value as Record<string, unknown>
  return ['tripId', 'memberId', 'memberName', 'memberToken'].every(key => typeof session[key] === 'string' && session[key] !== '')
}
