import { createContext, useContext } from 'react'
import type { Member, MemberApi, MemberSession, TripSnapshot } from '../api'

export type TripContextValue = {
  session: MemberSession
  api: MemberApi
  /** Null until the first successful load. Kept as-is while later polls fail. */
  snapshot: TripSnapshot | null
  /** This browser's member, once the snapshot includes it. */
  me: Member | null
  /** The latest polling failure, or null. */
  error: Error | null
  refresh(): Promise<void>
  /** Runs a write, then refreshes the snapshot whether it succeeded or failed (for example a 409). */
  mutate<T>(action: (api: MemberApi) => Promise<T>): Promise<T>
}

export const TripContext = createContext<TripContextValue | null>(null)

export function useTrip(): TripContextValue {
  const value = useContext(TripContext)
  if (!value) throw new Error('useTrip must be used inside <TripProvider>')
  return value
}
