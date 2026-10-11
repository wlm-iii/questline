import { useEffect, useMemo } from 'react'
import {
  APIProvider,
  AdvancedMarker,
  AdvancedMarkerAnchorPoint,
  Map,
  Polyline,
  useMap,
} from '@vis.gl/react-google-maps'
import { googleMapId, googleMapsKey } from './config'
import './QuestMap.css'

/** `start` and `end` are trip endpoints; `candidate` is a place not in the questline. */
export type MapStopKind = 'stop' | 'candidate' | 'start' | 'end'

export type MapStop<Id extends string | number = number> = {
  id: Id
  name: string
  side: boolean
  done: boolean
  lat?: number
  lng?: number
  /** Defaults to `stop`. Only stops are numbered or joined by lines. */
  kind?: MapStopKind
  /** `false` keeps a stop off the route and detour lines. Defaults to `true`. */
  route?: boolean
}

type PlottedStop<Id extends string | number> = MapStop<Id> & { lat: number; lng: number }
type GoogleMap = NonNullable<ReturnType<typeof useMap>>
type LatLng = { lat: number; lng: number }

type QuestMapProps<Id extends string | number> = {
  stops: MapStop<Id>[]
  selectedId: Id | null
  onSelect: (id: Id) => void
}

const FIT_PADDING = 80
const SAN_FRANCISCO = { lat: 37.7749, lng: -122.4194 }
const ENDPOINT_LABEL: Partial<Record<MapStopKind, string>> = { start: 'A', end: 'B' }

function isPlotted<Id extends string | number>(stop: MapStop<Id>): stop is PlottedStop<Id> {
  return typeof stop.lat === 'number' && typeof stop.lng === 'number'
}

function boundsOf(stops: LatLng[]) {
  return {
    north: Math.max(...stops.map(s => s.lat)),
    south: Math.min(...stops.map(s => s.lat)),
    east: Math.max(...stops.map(s => s.lng)),
    west: Math.min(...stops.map(s => s.lng)),
  }
}

function fit(map: GoogleMap, stops: LatLng[]) {
  if (stops.length === 0) return
  if (stops.length === 1) {
    map.setCenter(stops[0])
    map.setZoom(15)
    return
  }
  map.fitBounds(boundsOf(stops), FIT_PADDING)
}

function nearest<T extends LatLng>(target: LatLng, candidates: T[]) {
  return candidates.reduce((best, c) =>
    Math.hypot(c.lat - target.lat, c.lng - target.lng) < Math.hypot(best.lat - target.lat, best.lng - target.lng) ? c : best,
  )
}

function FitToStops<Id extends string | number>({ stops }: { stops: PlottedStop<Id>[] }) {
  const map = useMap()
  const key = stops.map(s => `${s.id}:${s.lat},${s.lng}`).join('|')
  useEffect(() => {
    if (map) fit(map, stops)
    // Refit only when the set of coordinates changes, not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key])
  return null
}

function MapControls({ stops }: { stops: LatLng[] }) {
  const map = useMap()
  const zoomBy = (delta: number) => map?.setZoom((map.getZoom() ?? 12) + delta)
  return (
    <div className="map-controls">
      <button aria-label="Zoom in" onClick={() => zoomBy(1)}>＋</button>
      <button aria-label="Zoom out" onClick={() => zoomBy(-1)}>−</button>
      <button aria-label="Reset map view" onClick={() => map && fit(map, stops)}>⌖</button>
    </div>
  )
}

export function QuestMap<Id extends string | number>({ stops, selectedId, onSelect }: QuestMapProps<Id>) {
  const plotted = useMemo(() => stops.filter(isPlotted), [stops])
  const questStops = plotted.filter(s => (s.kind ?? 'stop') === 'stop')
  const main = questStops.filter(s => !s.side)
  const side = questStops.filter(s => s.side)
  const routed = main.filter(s => s.route !== false)
  const detours = side.filter(s => s.route !== false)
  const unplotted = stops.length - plotted.length

  function markerText(s: PlottedStop<Id>) {
    const kind = s.kind ?? 'stop'
    if (kind === 'start' || kind === 'end') return ENDPOINT_LABEL[kind]
    if (s.done) return '✓'
    if (kind === 'candidate') return ''
    return s.side ? '✧' : main.findIndex(m => m.id === s.id) + 1
  }

  function markerClass(s: PlottedStop<Id>) {
    const kind = s.kind ?? 'stop'
    const role = kind === 'start' || kind === 'end' ? `endpoint ${kind}` : kind === 'candidate' ? 'candidate' : s.side ? 'side' : ''
    return `marker geo ${role} ${selectedId === s.id ? 'selected' : ''}`
  }

  function markerLayer(s: PlottedStop<Id>) {
    if (selectedId === s.id) return 10
    const kind = s.kind ?? 'stop'
    if (kind === 'start' || kind === 'end') return 3
    return s.side || kind === 'candidate' ? 1 : 2
  }

  return (
    <APIProvider apiKey={googleMapsKey}>
      <div className="google-map">
        <Map
          mapId={googleMapId}
          defaultCenter={plotted[0] ?? SAN_FRANCISCO}
          defaultZoom={13}
          disableDefaultUI
          gestureHandling="greedy"
          clickableIcons={false}
        >
          <FitToStops stops={plotted} />
          {routed.length > 0 && detours.map(s => (
            <Polyline
              key={`detour-${s.id}`}
              path={[nearest(s, routed), s]}
              strokeOpacity={0}
              icons={[{ icon: { path: 'M 0,-1 0,1', strokeOpacity: 1, strokeColor: '#7a97a9', scale: 3 }, offset: '0', repeat: '14px' }]}
            />
          ))}
          {routed.length > 1 && <Polyline path={routed} strokeColor="#fff4d6" strokeWeight={10} strokeOpacity={0.9} />}
          {routed.length > 1 && <Polyline path={routed} strokeColor="#9a7542" strokeWeight={5} strokeOpacity={1} />}
          {plotted.map(s => (
            <AdvancedMarker
              key={s.id}
              position={s}
              title={s.name}
              anchorPoint={AdvancedMarkerAnchorPoint.CENTER}
              zIndex={markerLayer(s)}
              onClick={() => onSelect(s.id)}
            >
              <span className={markerClass(s)}>
                <span>{markerText(s)}</span>
                <b>{s.name}</b>
              </span>
            </AdvancedMarker>
          ))}
        </Map>
        <MapControls stops={plotted} />
        {unplotted > 0 && (
          <span className="map-pill small unplotted-note">
            {unplotted} waypoint{unplotted === 1 ? '' : 's'} without coordinates not shown
          </span>
        )}
      </div>
    </APIProvider>
  )
}
