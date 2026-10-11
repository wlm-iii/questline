import type { Stop, Trip, PartyVotes } from '../../demo/types'
import { StopRow } from './StopRow'
import { BudgetSummary } from './BudgetSummary'

export type QuestBoardProps = {
  stops: Stop[]
  main: Stop[]
  displayed: Stop[]
  selected: number
  tab: string
  filter: string
  search: string
  partyVotes: PartyVotes
  owners: Record<number, string>
  done: number[]
  accepted: boolean
  total: number
  trip: Trip
  onTabChange: (tab: string) => void
  onFilterChange: (filter: string) => void
  onSearchChange: (text: string) => void
  onSelect: (id: number) => void
  onMove: (id: number, offset: number) => void
  onDetails: (id: number) => void
  onToggleDone: (id: number) => void
  onAddWaypoint: () => void
  onBuildPlan: () => void
  onAccept: () => void
}
export function QuestBoard({
  stops,
  main,
  displayed,
  selected,
  tab,
  filter,
  search,
  partyVotes,
  owners,
  done,
  accepted,
  total,
  trip,
  onTabChange,
  onFilterChange,
  onSearchChange,
  onSelect,
  onMove,
  onDetails,
  onToggleDone,
  onAddWaypoint,
  onBuildPlan,
  onAccept,
}: QuestBoardProps) {
  return (
    <aside className="sidebar">
      <div className="panel-heading">
        <div>
          <h2>The quest board</h2>
          <p>Less scrolling. More going.</p>
        </div>
      </div>
      <div className="tabs">
        {['Waypoints', 'Questline', 'Quest log'].map((t) => (
          <button
            className={tab === t ? 'active' : ''}
            key={t}
            onClick={() => onTabChange(t)}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === 'Quest log' ? (
        <div className="intro">
          <h3>
            {accepted
              ? 'Adventure in progress'
              : 'Your day, one stop at a time'}
          </h3>
          <p>
            {done.filter((id) => main.some((s) => s.id === id)).length} of{' '}
            {main.length} main quests complete
          </p>
          <progress
            value={done.filter((id) => main.some((s) => s.id === id)).length}
            max={main.length || 1}
          />
        </div>
      ) : (
        <div className="intro">
          <h3>
            {tab === 'Waypoints'
              ? 'Good places. Great company.'
              : 'A little plan. A lot to discover.'}
          </h3>
          <p>
            {stops.length} waypoints · {main.length} main quests ·{' '}
            {stops.length - main.length} side quests
          </p>
        </div>
      )}
      <div className="board-tools">
        <label className="search-field">
          <span>⌕</span>
          <input
            aria-label="Search waypoints"
            placeholder="Find a waypoint…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </label>
        <button aria-label="Add waypoint" onClick={onAddWaypoint}>
          ＋
        </button>
      </div>
      {tab === 'Questline' && (
        <div className="route-summary">
          <button className="text-button" onClick={onBuildPlan}>
            Rebuild route →
          </button>
          <span>↗ {main.length} main stops</span>
          <span>✧ {stops.length - main.length} optional detours</span>
          <p>
            Reorder stops below to shape your day. Travel times and map geometry
            are illustrative.
          </p>
        </div>
      )}
      {tab === 'Quest log' && !accepted && (
        <div className="inline-warning">
          Accept your questline to begin checking off stops.
        </div>
      )}
      {tab === 'Waypoints' && (
        <div className="filters">
          {['All', 'Eat', 'Do'].map((f) => (
            <button
              key={f}
              className={filter === f ? 'active' : ''}
              onClick={() => onFilterChange(f)}
            >
              {f === 'Eat' ? '☕ ' : f === 'Do' ? '✳ ' : ''}
              {f}
            </button>
          ))}
        </div>
      )}
      <div className="stop-list">
        {displayed.length === 0 && (
          <div className="empty-list">
            <strong>No waypoints found</strong>
            <p>Try another search or add a place to explore.</p>
          </div>
        )}
        {displayed.map((s) => (
          <StopRow
            key={s.id}
            stop={s}
            number={main.findIndex((m) => m.id === s.id) + 1}
            selected={selected === s.id}
            tab={tab}
            interested={
              Object.values(partyVotes[s.id] ?? {}).filter(
                (v) => v === 'I’m in',
              ).length
            }
            owner={owners[s.id] || ''}
            done={done.includes(s.id)}
            accepted={accepted}
            canMoveEarlier={stops[0]?.id !== s.id}
            canMoveLater={stops.at(-1)?.id !== s.id}
            onSelect={onSelect}
            onMove={onMove}
            onDetails={onDetails}
            onToggleDone={onToggleDone}
          />
        ))}
      </div>
      <div className="board-bottom">
        <div className="tip">
          <p>
            A side quest is a possibility, not a promise.
            <br />
            <strong>Leave a little room for the unexpected.</strong>
          </p>
        </div>
        <BudgetSummary total={total} budget={trip.budget} />
        <button
          disabled={main.length === 0}
          className="primary accept"
          onClick={onAccept}
        >
          {accepted ? 'Open your quest log →' : 'Accept this questline →'}
        </button>
        <p className="footer-note">
          Made for the plans that finally leave the group chat.
        </p>
      </div>
    </aside>
  )
}
