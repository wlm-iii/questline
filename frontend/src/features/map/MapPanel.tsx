import type { ReactNode } from 'react'
import type { Stop } from '../../demo/types'
import { QuestMap, type MapStop } from './QuestMap'
import { IllustratedMap } from './IllustratedMap'

export type MapPanelProps = {
  stops: Stop[]
  mapStops: MapStop[]
  selectedId: number
  done: number[]
  zoom: number
  googleMapsEnabled: boolean
  onSelect: (id: number) => void
  onZoomIn: () => void
  onZoomOut: () => void
  onReset: () => void
  children?: ReactNode
}
export function MapPanel({
  stops,
  mapStops,
  selectedId,
  done,
  zoom,
  googleMapsEnabled,
  onSelect,
  onZoomIn,
  onZoomOut,
  onReset,
  children,
}: MapPanelProps) {
  return (
    <section className="map-panel">
      <div className="map-top">
        <span className="map-pill">
          <i /> Your next adventure, mapped.
        </span>
        <span className="map-pill small">
          {googleMapsEnabled
            ? 'Google Maps · sample coordinates'
            : 'Illustrated demo map'}
        </span>
      </div>
      {googleMapsEnabled ? (
        <QuestMap
          stops={mapStops}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ) : (
        <IllustratedMap
          stops={stops}
          selectedId={selectedId}
          done={done}
          zoom={zoom}
          onSelect={onSelect}
          onZoomIn={onZoomIn}
          onZoomOut={onZoomOut}
          onReset={onReset}
        />
      )}
      {children}
      <div className="map-legend">
        <span>
          <i /> Main quest
        </span>
        <span>
          <i className="outline" /> Side quest
        </span>
        <span>Route is illustrative</span>
      </div>
    </section>
  )
}
