export type NavigationRailProps = {
  view: string
  onViewChange: (view: string) => void
  onQuestLog: () => void
}
export function NavigationRail({
  view,
  onViewChange,
  onQuestLog,
}: NavigationRailProps) {
  return (
    <aside className="rail">
      <a className="brand" href="#" aria-label="Questline home">
        q<span>↗</span>
      </a>
      <button
        className={view === 'Map' ? 'rail-active' : ''}
        aria-label="Trip map"
        onClick={() => onViewChange('Map')}
      >
        ◇
      </button>
      <button
        aria-label="Trip overview"
        className={view === 'Overview' ? 'rail-active' : ''}
        onClick={() => onViewChange('Overview')}
      >
        ▦
      </button>
      <button aria-label="Open quest log" onClick={onQuestLog}>
        ☷
      </button>
      <div className="rail-bottom">
        <span className="avatar">JS</span>
      </div>
    </aside>
  )
}
