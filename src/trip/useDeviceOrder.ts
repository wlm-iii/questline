import { useCallback, useState } from 'react'
import type { Uuid } from '../api'
import { isDeviceOrder, type DeviceOrder } from './adapters'

const storageKey = (tripId: Uuid) => `questline-device-order:${tripId}`

function read(tripId: Uuid): DeviceOrder | null {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(storageKey(tripId)) ?? 'null')
    return isDeviceOrder(parsed) ? parsed : null
  } catch {
    return null
  }
}

/** The device-only questline draft for one trip. Null until the member reorders or promotes something. */
export function useDeviceOrder(tripId: Uuid) {
  const [state, setState] = useState(() => ({ tripId, order: read(tripId) }))
  const order = state.tripId === tripId ? state.order : read(tripId)
  const save = useCallback((next: DeviceOrder | null) => {
    setState({ tripId, order: next })
    try {
      if (next) localStorage.setItem(storageKey(tripId), JSON.stringify(next))
      else localStorage.removeItem(storageKey(tripId))
    } catch { /* Storage may be unavailable in private sessions. */ }
  }, [tripId])
  return [order, save] as const
}
