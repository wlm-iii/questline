export const googleMapsKey: string = import.meta.env.VITE_GOOGLE_MAPS_BROWSER_KEY ?? ''

// Advanced markers require a map ID; DEMO_MAP_ID works for development only.
export const googleMapId: string = import.meta.env.VITE_GOOGLE_MAP_ID || 'DEMO_MAP_ID'

export const googleMapsEnabled = googleMapsKey.length > 0
