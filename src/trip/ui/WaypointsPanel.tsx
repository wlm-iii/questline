import { useState, type FormEvent } from 'react'
import { categories, categoryLabels, type ImportView, type StopView, type UnresolvedMention } from '../adapters'
import { ImportStatus } from './ImportStatus'
import { StatusBadge } from './StatusBadge'
import { TripStopRow } from './TripStopRow'

export type WaypointsPanelProps = {
  stops: StopView[]
  selectedId: string | null
  stats: string
  imports: ImportView[]
  unresolved: UnresolvedMention[]
  /** The query being searched, or null. */
  adding: string | null
  addError: string | null
  /** Resolves true when the place was added, so the field can clear. */
  onAddPlace: (query: string) => Promise<boolean>
  onSelect: (id: string) => void
  onImport: () => void
}

const filterIcons: Record<string, string> = { eat: '☕ ', do: '✳ ' }

export function WaypointsPanel({
  stops,
  selectedId,
  stats,
  imports,
  unresolved,
  adding,
  addError,
  onAddPlace,
  onSelect,
  onImport,
}: WaypointsPanelProps) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<string>('all')
  const groups = categories
    .filter(category => filter === 'all' || filter === category)
    .map(category => ({ category, stops: stops.filter(stop => stop.category === category).sort((a, b) => a.name.localeCompare(b.name)) }))
    .filter(group => group.stops.length > 0)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (await onAddPlace(query)) setQuery('')
  }

  return (
    <>
      <div className="intro">
        <h3>Good places. Great company.</h3>
        <p>{stats}</p>
      </div>
      <form className="board-tools" onSubmit={submit}>
        <label className="search-field">
          <span>⌕</span>
          <input
            aria-label="Add a place by search"
            placeholder="Add a place by name or address…"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </label>
        <button type="submit" aria-label="Add place" disabled={adding !== null || !query.trim()}>
          ＋
        </button>
      </form>
      {adding !== null && <div className="route-summary" role="status">Searching for “{adding}”…</div>}
      {addError && <div className="inline-warning" role="alert">{addError}</div>}
      <ImportStatus imports={imports} unresolved={unresolved} searching={adding} onSearch={text => void onAddPlace(text)} variant="board" />
      <div className="filters">
        {['all', ...categories].map(option => (
          <button key={option} className={filter === option ? 'active' : ''} onClick={() => setFilter(option)}>
            {filterIcons[option] ?? ''}
            {option === 'all' ? 'All' : categoryLabels[option as keyof typeof categoryLabels]}
          </button>
        ))}
      </div>
      <div className="stop-list">
        {groups.length === 0 && (
          <div className="empty-list">
            <strong>{stops.length ? 'Nothing in this category' : 'No places yet'}</strong>
            <p>Import the group chat or search for a place above.</p>
          </div>
        )}
        {groups.map(group => (
          <section key={group.category} aria-label={categoryLabels[group.category]}>
            <p className="eyebrow" style={{ padding: '12px 10px 4px' }}>
              {categoryLabels[group.category].toUpperCase()} · {group.stops.length}
            </p>
            {group.stops.map(stop => (
              <TripStopRow
                key={stop.id}
                stop={stop}
                marker={stop.status === 'main' && stop.number ? String(stop.number) : stop.status === 'side' ? '✧' : '·'}
                hollow={stop.status !== 'main'}
                selected={selectedId === stop.id}
                details={[
                  `${stop.categoryLabel} · ${stop.cost}`,
                  stop.mentionedBy ? `${stop.sourceLabel} · mentioned by ${stop.mentionedBy}` : stop.sourceLabel,
                ]}
                badge={<StatusBadge status={stop.status} />}
                onSelect={onSelect}
              />
            ))}
          </section>
        ))}
      </div>
      <div className="board-bottom">
        <div className="tip">
          <p>
            Places are candidates until the crew builds a questline.
            <br />
            <strong>Every place shows who mentioned it.</strong>
          </p>
        </div>
        <button className="quiet accept" style={{ marginTop: 12 }} onClick={onImport}>
          Import chat
        </button>
      </div>
    </>
  )
}
