import { useState } from 'react'
import type { Uuid, VoteKind } from '../api'
import { useTrip } from '../state'
import { errorMessage } from './errors'

/** Casts the viewer's vote. The API toggles: sending the current kind again clears it. */
export function useVote(onError: (message: string) => void) {
  const { mutate } = useTrip()
  const [pending, setPending] = useState<Uuid[]>([])
  async function vote(placeId: Uuid, kind: VoteKind) {
    setPending(current => [...current, placeId])
    try {
      await mutate(api => api.vote(placeId, kind))
    } catch (failure) {
      onError(errorMessage(failure))
    } finally {
      setPending(current => current.filter(id => id !== placeId))
    }
  }
  return { vote, pending }
}
