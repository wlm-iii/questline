export type ViewNavigationProps = {
  view: string
  accepted: boolean
  onViewChange: (view: string) => void
  /** Replaces the demo's "Draft questline · Changes saved locally". */
  status?: string
}
export function ViewNavigation({
  view,
  accepted,
  onViewChange,
  status,
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
        {status ?? (
          <>
            {accepted ? '✓ Questline accepted' : '◌ Draft questline'} · Changes
            saved locally
          </>
        )}
      </span>
    </nav>
  )
}
