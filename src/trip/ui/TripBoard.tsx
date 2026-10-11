import type { ReactNode } from 'react'

export type BoardTab = 'Waypoints' | 'Questline' | 'Quest log'

const boardTabs: BoardTab[] = ['Waypoints', 'Questline', 'Quest log']

export type TripBoardProps = {
  tab: BoardTab
  onTabChange: (tab: BoardTab) => void
  children: ReactNode
}

export function TripBoard({ tab, onTabChange, children }: TripBoardProps) {
  return (
    <aside className="sidebar">
      <div className="panel-heading">
        <div>
          <h2>The quest board</h2>
          <p>Less scrolling. More going.</p>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {boardTabs.map(option => (
          <button
            key={option}
            role="tab"
            aria-selected={tab === option}
            className={tab === option ? 'active' : ''}
            onClick={() => onTabChange(option)}
          >
            {option}
          </button>
        ))}
      </div>
      {children}
    </aside>
  )
}
