import { QuestBadge } from './QuestBadge'
export function QuestCardHeader({ kind, number }: { kind: 'main' | 'side'; number: string }) {
  return <div className="quest-card-header"><QuestBadge kind={kind}/><span className="quest-number" aria-label={`Quest ${number}`}>{number}</span></div>
}
