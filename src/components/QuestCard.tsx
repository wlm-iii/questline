import { useId, useState } from 'react'
import { Card, Button, Stamp } from '@dendelion/paper-ui'

type QuestCardProps = {
  title?: string
  category?: string
  kind?: 'main' | 'side'
  number?: string
  contested?: boolean
}

export function QuestCard({
  title = 'McWay Falls',
  category = 'Nature',
  kind = 'main',
  number = '01',
  contested = true,
}: QuestCardProps) {
  const [expanded, setExpanded] = useState(false)
  const detailId = useId()

  return (
    <Card texture={false} className="quest-card">
      <div className="quest-card-header">
        <Stamp ring={false} textColor={kind === 'main' ? 'var(--forest)' : 'var(--ink)'} className={`quest-stamp quest-stamp--${kind}`}>
          {kind === 'main' ? 'Main Quest' : 'Side Quest'}
        </Stamp>
        <span className="quest-number" aria-label={`Quest ${number}`}>{number}</span>
      </div>
      <div className="quest-card-body">
        <h3>{title}</h3>
        <p className="quest-description">{category} · {kind === 'main' ? 'Along the questline' : 'An optional detour'}</p>
      </div>
      <div className="quest-card-footer">
        {contested ? <span className="quest-status">Contested waypoint</span> : <span>Sample waypoint</span>}
        <Button
          className="quest-button quest-button--primary"
          aria-expanded={expanded}
          aria-controls={detailId}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? 'Close quest' : 'View quest'}
        </Button>
      </div>
      <p id={detailId} hidden={!expanded}>
        Demo preview only. Place details, votes, and trip planning are not connected yet.
      </p>
    </Card>
  )
}
