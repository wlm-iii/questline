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

export type MapStop = {
  id: number
  name: string
  side: boolean
  done: boolean
  lat?: number
  lng?: number
}

type PlottedStop = MapStop & { lat: number; lng: number }
type GoogleMap = NonNullable<ReturnType<typeof useMap>>

type QuestMapProps = {
  stops: MapStop[]
  selectedId: number | null
  onSelect: (id: number) => void
}

const FIT_PADDING = 80
const SAN_FRANCISCO = { lat: 37.7749, lng: -122.4194 }

function isPlotted(stop: MapStop): stop is PlottedStop {
  return typeof stop.lat === 'number' && typeof stop.lng === 'number'
}

function boundsOf(stops: PlottedStop[]) {
  return {
    north: Math.max(...stops.map(s => s.lat)),
    south: Math.min(...stops.map(s => s.lat)),
    east: Math.max(...stops.map(s => s.lng)),
    west: Math.min(...stops.map(s => s.lng)),
  }
}

function fit(map: GoogleMap, stops: PlottedStop[]) {
  if (stops.length === 0) return
  if (stops.length === 1) {
    map.setCenter(stops[0])
    map.setZoom(15)
    return
  }
  map.fitBounds(boundsOf(stops), FIT_PADDING)
}

function nearest(target: PlottedStop, candidates: PlottedStop[]) {
  return candidates.reduce((best, c) =>
    Math.hypot(c.lat - target.lat, c.lng - target.lng) < Math.hypot(best.lat - target.lat, best.lng - target.lng) ? c : best,
  )
}

function FitToStops({ stops }: { stops: PlottedStop[] }) {
  const map = useMap()
  const key = stops.map(s => `${s.id}:${s.lat},${s.lng}`).join('|')
  useEffect(() => {
    if (map) fit(map, stops)
    // Refit only when the set of coordinates changes, not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key])
  return null
}

function MapControls({ stops }: { stops: PlottedStop[] }) {
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

export function QuestMap({ stops, selectedId, onSelect }: QuestMapProps) {
  const plotted = useMemo(() => stops.filter(isPlotted), [stops])
  const main = plotted.filter(s => !s.side)
  const side = plotted.filter(s => s.side)
  const unplotted = stops.length - plotted.length

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
          {main.length > 0 && side.map(s => (
            <Polyline
              key={`detour-${s.id}`}
              path={[nearest(s, main), s]}
              strokeOpacity={0}
              icons={[{ icon: { path: 'M 0,-1 0,1', strokeOpacity: 1, strokeColor: '#7a97a9', scale: 3 }, offset: '0', repeat: '14px' }]}
            />
          ))}
          {main.length > 1 && <Polyline path={main} strokeColor="#fff4d6" strokeWeight={10} strokeOpacity={0.9} />}
          {main.length > 1 && <Polyline path={main} strokeColor="#9a7542" strokeWeight={5} strokeOpacity={1} />}
          {plotted.map(s => (
            <AdvancedMarker
              key={s.id}
              position={s}
              title={s.name}
              anchorPoint={AdvancedMarkerAnchorPoint.CENTER}
              zIndex={selectedId === s.id ? 10 : s.side ? 1 : 2}
              onClick={() => onSelect(s.id)}
            >
              <span className={`marker geo ${s.side ? 'side' : ''} ${selectedId === s.id ? 'selected' : ''}`}>
                <span>{s.done ? '✓' : s.side ? '✧' : main.findIndex(m => m.id === s.id) + 1}</span>
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
