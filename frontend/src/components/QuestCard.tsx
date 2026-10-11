import { useId, useState, type ReactNode } from 'react'
import { QuestCardHeader } from './QuestCardHeader'
import { QuestCardBody } from './QuestCardBody'
import { QuestCardFooter } from './QuestCardFooter'
export type QuestCardProps = { title?: string; category?: string; description?: string; kind?: 'main' | 'side'; number?: string; contested?: boolean; status?: string; onView?: () => void; children?: ReactNode; className?: string }
export function QuestCard({ title = 'McWay Falls', category = 'Nature', description, kind = 'main', number = '01', contested = false, status, onView, children, className = '' }: QuestCardProps) {
  const [expanded, setExpanded] = useState(false)
  const detailId = useId()
  return <article className={`quest-card ${className}`}><QuestCardHeader kind={kind} number={number}/><QuestCardBody title={title} description={description ?? `${category} · ${kind === 'main' ? 'Along the questline' : 'An optional detour'}`}/>{children}<QuestCardFooter contested={contested} status={status ?? (contested ? 'Contested waypoint' : 'Trip member')} onView={onView ?? (() => setExpanded(!expanded))} expanded={onView ? undefined : expanded} detailId={onView ? undefined : detailId}/>{!onView && <p id={detailId} hidden={!expanded}>Sample quest card. Open a waypoint in the dashboard to edit its details.</p>}</article>
}
