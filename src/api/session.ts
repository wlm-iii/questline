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

export function sessionFromJoin(tripId: Uuid, result: JoinResult): MemberSession {
  return { tripId, memberId: result.member.id, memberName: result.member.name, memberToken: result.member_token }
}

export function loadSession(tripId: Uuid): MemberSession | null {
  return readSessions()[tripId] ?? null
}

export function saveSession(session: MemberSession): void {
  writeSessions({ ...readSessions(), [session.tripId]: session })
}

/** Drop a session, for example after the backend rejects its token with 401. */
export function forgetSession(tripId: Uuid): void {
  const sessions = readSessions()
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
}

function readSessions(): Record<Uuid, MemberSession> {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(sessionsKey) ?? '{}')
    if (typeof parsed !== 'object' || parsed === null) return {}
    return Object.fromEntries(Object.entries(parsed).filter(([tripId, value]) => isSession(value) && value.tripId === tripId))
  } catch {
    return {}
  }
}

function writeSessions(sessions: Record<Uuid, MemberSession>): void {
  try { localStorage.setItem(sessionsKey, JSON.stringify(sessions)) } catch { /* Storage may be unavailable in private sessions. */ }
}

function isSession(value: unknown): value is MemberSession {
  if (typeof value !== 'object' || value === null) return false
  const session = value as Record<string, unknown>
  return ['tripId', 'memberId', 'memberName', 'memberToken'].every(key => typeof session[key] === 'string' && session[key] !== '')
}
