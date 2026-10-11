import { QuestBadge } from '../../components/QuestBadge'
import type { QuestStatus } from '../adapters'

export function StatusBadge({ status }: { status: QuestStatus }) {
  return status === 'candidate' ? <QuestBadge kind="info">Not in questline</QuestBadge> : <QuestBadge kind={status} />
}
