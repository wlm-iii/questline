import { useSyncExternalStore, type MouseEvent } from 'react'
import type { Uuid } from '../api'

// Trip links look like /t/<trip UUID>. Hosting must serve index.html for /t/* (Vite dev and preview already do).
const tripPath = /^\/t\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/?$/i
const navigateEvent = 'questline-navigate'

export const demoPath = '/demo'

/** The trip ID in a path, or null when the path isn't a well-formed trip link. */
export function tripIdFromPath(pathname: string): Uuid | null {
  return tripPath.exec(pathname)?.[1].toLowerCase() ?? null
}

export function isDemoPath(pathname: string): boolean {
  return pathname.replace(/\/+$/, '') === demoPath
}

export function tripUrl(tripId: Uuid, origin = window.location.origin): string {
  return `${origin}/t/${tripId}`
}

export function navigateToTrip(tripId: Uuid): void {
  navigateTo(`/t/${tripId}`)
}

export function navigateHome(): void {
  navigateTo('/')
}

/** Pushes an in-app path; everything using `usePathname` or `useTripRoute` re-renders. */
export function navigateTo(path: string): void {
  if (window.location.pathname === path) return
  window.history.pushState(null, '', path)
  window.dispatchEvent(new Event(navigateEvent))
}

/** `onClick` for an in-app `<a href>`: navigates without a reload, but lets modified clicks open a new tab. */
export function followInAppLink(event: MouseEvent<HTMLAnchorElement>): void {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  navigateTo(event.currentTarget.pathname)
}

/** The current path. Re-renders on back/forward and on `navigateTo*`. */
export function usePathname(): string {
  return useSyncExternalStore(subscribe, () => window.location.pathname)
}

/** The trip ID from the current URL. Re-renders on back/forward and on `navigateTo*`. */
export function useTripRoute(): Uuid | null {
  return tripIdFromPath(usePathname())
}

function subscribe(listener: () => void): () => void {
  window.addEventListener('popstate', listener)
  window.addEventListener(navigateEvent, listener)
  return () => {
    window.removeEventListener('popstate', listener)
    window.removeEventListener(navigateEvent, listener)
  }
}
