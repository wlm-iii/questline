export type ViewNavigationProps = {
  view: string
  accepted: boolean
  onViewChange: (view: string) => void
}
export function ViewNavigation({
  view,
  accepted,
  onViewChange,
}: ViewNavigationProps) {
  return (
    <nav className="view-nav">
      <div>
        {['Map', 'Overview', 'Planning desk'].map((v) => (
          <button
            key={v}
            className={view === v ? 'active' : ''}
            onClick={() => onViewChange(v)}
          >
            {v === 'Map' ? '◇' : '▦'} {v}
          </button>
        ))}
      </div>
      <span>
        {accepted ? '✓ Questline accepted' : '◌ Draft questline'} · Changes
        saved locally
      </span>
    </nav>
  )
}
