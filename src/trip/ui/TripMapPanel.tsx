import type { ReactNode } from 'react'
import { QuestMap } from '../../features/map/QuestMap'
import type { MapPoint } from '../adapters'

export type TripMapPanelProps = {
  points: MapPoint[]
  selectedId: string | null
  mapEnabled: boolean
  hasPlaces: boolean
  onSelect: (id: string) => void
  onImport: () => void
  /** The selected place's card. */
  children?: ReactNode
}

export function TripMapPanel({ points, selectedId, mapEnabled, hasPlaces, onSelect, onImport, children }: TripMapPanelProps) {
  const hasQuests = points.some(point => point.kind === 'stop')
  const empty = (
    <>
      <p>
        Import the group chat, or add a place by search in the quest board. Both put places on the map.
      </p>
      <button className="primary" onClick={onImport}>
        Import chat
      </button>
    </>
  )
  return (
    <section className="map-panel">
      <div className="map-top">
        <span className="map-pill">
          <i /> Your next adventure, mapped.
        </span>
        <span className="map-pill small">{mapEnabled ? 'Google Maps · no routes yet' : 'Map unavailable'}</span>
      </div>
      {mapEnabled && <QuestMap stops={points} selectedId={selectedId} onSelect={onSelect} />}
      {mapEnabled && !hasPlaces && (
        <div className="empty-map">
          <h2>No places yet.</h2>
          {empty}
        </div>
      )}
      {!mapEnabled && (
        <div className="empty-map" style={{ top: 72 }} role="note">
          <h2>The map needs a browser key.</h2>
          <p>
            Set <code>VITE_GOOGLE_MAPS_BROWSER_KEY</code> and restart the app to see this trip on a Google map. Places,
            the questline and the quest log still work.
          </p>
          {!hasPlaces && empty}
        </div>
      )}
      {children}
      <div className="map-legend">
        <span>
          <i className="endpoint" /> A start · B end
        </span>
        {hasQuests && (
          <>
            <span>
              <i /> Main quest
            </span>
            <span>
              <i className="outline" /> Side quest
            </span>
          </>
        )}
        <span>
          <i className="candidate" /> Candidate
        </span>
        <span>No driving routes yet</span>
      </div>
    </section>
  )
}
