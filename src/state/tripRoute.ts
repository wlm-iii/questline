import { useSyncExternalStore } from 'react'
import type { Uuid } from '../api'

// Trip links look like /t/<trip UUID>. Hosting must serve index.html for /t/* (Vite dev and preview already do).
const tripPath = /^\/t\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/?$/i
const navigateEvent = 'questline-navigate'

/** The trip ID in a path, or null when the path isn't a well-formed trip link. */
export function tripIdFromPath(pathname: string): Uuid | null {
  return tripPath.exec(pathname)?.[1].toLowerCase() ?? null
}

export function tripUrl(tripId: Uuid, origin = window.location.origin): string {
  return `${origin}/t/${tripId}`
}

export function navigateToTrip(tripId: Uuid): void {
  navigate(`/t/${tripId}`)
}

export function navigateHome(): void {
  navigate('/')
}

/** The trip ID from the current URL. Re-renders on back/forward and on `navigateTo*`. */
export function useTripRoute(): Uuid | null {
  const pathname = useSyncExternalStore(subscribe, () => window.location.pathname)
  return tripIdFromPath(pathname)
}

function navigate(path: string): void {
  if (window.location.pathname === path) return
  window.history.pushState(null, '', path)
  window.dispatchEvent(new Event(navigateEvent))
}

function subscribe(listener: () => void): () => void {
  window.addEventListener('popstate', listener)
  window.addEventListener(navigateEvent, listener)
  return () => {
    window.removeEventListener('popstate', listener)
    window.removeEventListener(navigateEvent, listener)
  }
}
