import { QuestButton } from './QuestButton'
export function QuestCardFooter({ contested, status, expanded, detailId, onView }: { contested: boolean; status: string; expanded?: boolean; detailId?: string; onView: () => void }) {
  return <div className="quest-card-footer"><span className={contested ? 'quest-status' : ''}>{status}</span><QuestButton aria-expanded={expanded} aria-controls={detailId} onClick={onView}>{expanded ? 'Close quest' : 'View quest'}</QuestButton></div>
}
