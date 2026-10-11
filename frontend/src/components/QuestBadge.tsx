import type { ReactNode } from 'react'
export type QuestKind = 'main' | 'side' | 'info' | 'danger'
export function QuestBadge({ kind = 'main', children }: { kind?: QuestKind; children?: ReactNode }) {
  return <span className={`quest-stamp quest-stamp--${kind}`}>{children ?? (kind === 'main' ? 'Main Quest' : 'Side Quest')}</span>
}
