import { useCallback, useState } from 'react'
import type { Place } from '../api'
import { useTrip } from '../state'
import { errorMessage, PLACE_NOT_FOUND } from './errors'

export type AddPlaceState = {
  /** The query being searched, or null. */
  pending: string | null
  error: string | null
}

/** Adds a place by text search. Resolves to the new place, or null after showing why it failed. */
export function useAddPlace() {
  const { session, mutate } = useTrip()
  const [state, setState] = useState<AddPlaceState>({ pending: null, error: null })

  const addPlace = useCallback(async (query: string): Promise<Place | null> => {
    const text = query.trim()
    if (!text) return null
    setState({ pending: text, error: null })
    try {
      const { place } = await mutate(api => api.addPlace(session.tripId, text))
      setState({ pending: null, error: null })
      return place
    } catch (error) {
      setState({
        pending: null,
        error: errorMessage(error, {
          place_not_found: PLACE_NOT_FOUND,
          provider_unavailable: "Place search isn't available right now. Try again later.",
        }),
      })
      return null
    }
  }, [mutate, session.tripId])

  const clearError = useCallback(() => setState(current => ({ ...current, error: null })), [])

  return { ...state, addPlace, clearError }
}
