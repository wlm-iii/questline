import type { Stop } from '../../demo/types'

export type IllustratedMapProps = {
  stops: Stop[]
  selectedId: number
  done: number[]
  zoom: number
  onSelect: (id: number) => void
  onZoomIn: () => void
  onZoomOut: () => void
  onReset: () => void
}
export function IllustratedMap({
  stops,
  selectedId,
  done,
  zoom,
  onSelect,
  onZoomIn,
  onZoomOut,
  onReset,
}: IllustratedMapProps) {
  const main = stops.filter((stop) => !stop.side)
  return (
    <>
      <div className="map-art" style={{ transform: `scale(${zoom})` }}>
        <svg
          viewBox="0 0 800 700"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            <pattern
              id="blocks"
              width="56"
              height="43"
              patternTransform="rotate(-12)"
              patternUnits="userSpaceOnUse"
            >
              <rect width="56" height="43" fill="#f1eee6" />
              <rect x="5" y="5" width="45" height="32" rx="3" fill="#e7e4db" />
              <path d="M0 0H56V43" stroke="#fffdf6" strokeWidth="5" />
            </pattern>
          </defs>
          <rect width="800" height="700" fill="url(#blocks)" />
          <path d="M0 0H175L140 95 85 174 58 290 0 355Z" fill="#bdd6d5" />
          <path
            d="M0 315L124 285 173 380 255 414 205 484 0 445Z"
            fill="#ccdac0"
          />
          <path d="M232 543L311 529 340 626 261 647Z" fill="#c5d6b8" />
          <path d="M310 280L397 267 415 330 323 349Z" fill="#c5d6b8" />
          <path
            d="M0 505L800 338M166 0L342 700M0 179L800 91M558 0L720 700"
            stroke="#ded7bd"
            strokeWidth="15"
          />
          <path
            d="M0 505L800 338M166 0L342 700M0 179L800 91M558 0L720 700"
            stroke="#fff9e6"
            strokeWidth="10"
          />
          {main.length > 0 &&
            stops
              .filter((s) => s.side)
              .map((s) => {
                const anchor = main.reduce(
                  (nearest, candidate) =>
                    Math.hypot(candidate.x - s.x, candidate.y - s.y) <
                    Math.hypot(nearest.x - s.x, nearest.y - s.y)
                      ? candidate
                      : nearest,
                  main[0],
                )
                return (
                  <path
                    key={s.id}
                    d={`M${anchor.x * 8} ${anchor.y * 7}L${s.x * 8} ${s.y * 7}`}
                    stroke="#85846b"
                    strokeWidth="3"
                    strokeDasharray="6 7"
                  />
                )
              })}
          {main.length > 1 && (
            <polyline
              points={main.map((s) => `${s.x * 8},${s.y * 7}`).join(' ')}
              fill="none"
              stroke="#fff"
              strokeWidth="12"
              strokeLinejoin="round"
            />
          )}
          {main.length > 1 && (
            <polyline
              points={main.map((s) => `${s.x * 8},${s.y * 7}`).join(' ')}
              fill="none"
              stroke="#657b45"
              strokeWidth="6"
              strokeLinejoin="round"
            />
          )}
        </svg>
        <span className="district d1">PACIFIC HEIGHTS</span>
        <span className="district d2">WESTERN ADDITION</span>
        <span className="district d3">THE MISSION</span>
        <span className="district d4">GOLDEN GATE PARK</span>
        <span className="water-label">
          Pacific
          <br />
          Ocean
        </span>
        {stops.map((s) => (
          <button
            key={s.id}
            className={`marker ${s.side ? 'side' : ''} ${selectedId === s.id ? 'selected' : ''}`}
            style={{ left: `${s.x}%`, top: `${s.y}%` }}
            onClick={() => onSelect(s.id)}
            aria-label={`Select ${s.name}`}
          >
            <span>
              {done.includes(s.id)
                ? '✓'
                : s.side
                  ? '✧'
                  : main.findIndex((m) => m.id === s.id) + 1}
            </span>
            <b>{s.name}</b>
          </button>
        ))}
      </div>
      <div className="map-controls">
        <button aria-label="Zoom in" onClick={onZoomIn}>
          ＋
        </button>
        <button aria-label="Zoom out" onClick={onZoomOut}>
          −
        </button>
        <button aria-label="Reset map view" onClick={onReset}>
          ⌖
        </button>
      </div>
    </>
  )
}
