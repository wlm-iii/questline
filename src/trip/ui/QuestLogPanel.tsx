import { useState, type FormEvent } from 'react'
import { ANYONE, type MemberOption, type QuestLogView, type StopView, type TaskView } from '../adapters'
import { StatusBadge } from './StatusBadge'
import { TripStopRow } from './TripStopRow'

export type QuestLogPanelProps = {
  log: QuestLogView
  members: MemberOption[]
  selectedId: string | null
  accepted: boolean
  /** Keys of writes in flight: a task ID, `checkin:<placeId>`, or `new-task:<placeId>`. */
  pending: string[]
  message: string | null
  onSelect: (id: string) => void
  /** Resolves true when the task was created, so the form can clear. */
  onCreateTask: (placeId: string, text: string, ownerId: string | null) => Promise<boolean>
  onToggleTask: (task: TaskView) => void
  onUnassign: (task: TaskView) => void
  onToggleDone: (stop: StopView) => void
}

export function QuestLogPanel({
  log,
  members,
  selectedId,
  accepted,
  pending,
  message,
  onSelect,
  onCreateTask,
  onToggleTask,
  onUnassign,
  onToggleDone,
}: QuestLogPanelProps) {
  const [draft, setDraft] = useState({ text: '', ownerId: '' })
  const { progress } = log

  async function submit(event: FormEvent, placeId: string) {
    event.preventDefault()
    if (await onCreateTask(placeId, draft.text, draft.ownerId || null)) setDraft({ text: '', ownerId: '' })
  }

  return (
    <>
      <div className="intro">
        <h3>{accepted ? 'Adventure in progress' : 'Your trip, one quest at a time'}</h3>
        {progress ? (
          <>
            <p>
              {progress.done} of {progress.total} main quests complete
            </p>
            <progress value={progress.done} max={progress.total} />
          </>
        ) : (
          <p>Progress shows once the crew has a questline.</p>
        )}
      </div>
      {log.nextUp && (
        <div className="route-summary">
          <span>Next up: {log.nextUp.name}</span>
          {log.nextUp.arrive && <span>Arrive {log.nextUp.arrive}</span>}
        </div>
      )}
      {log.hint && <div className="inline-warning">{log.hint}</div>}
      {message && (
        <div className="inline-warning" role="alert">
          {message}
        </div>
      )}
      <div className="stop-list">
        {log.entries.length === 0 && (
          <div className="empty-list">
            <strong>No quests yet</strong>
            <p>Add places, then build and accept a questline.</p>
          </div>
        )}
        {log.entries.map(({ stop, owner, tasks }) => {
          const selected = selectedId === stop.id
          return (
            <TripStopRow
              key={stop.id}
              stop={stop}
              marker={stop.status === 'main' && stop.number ? String(stop.number) : stop.status === 'side' ? '✧' : '·'}
              hollow={stop.status !== 'main'}
              selected={selected}
              details={[`${stop.categoryLabel} · ${stop.cost}`]}
              badge={<StatusBadge status={stop.status} />}
              onSelect={onSelect}
            >
              <p className="owner-label">Owner: {owner}</p>
              {tasks.map(task => (
                <div className="complete" key={task.id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={task.done}
                      disabled={pending.includes(task.id)}
                      onChange={() => onToggleTask(task)}
                    />{' '}
                    {task.text}
                    {task.ownerName && ` · ${task.ownerName}`}
                  </label>
                  {task.ownerName && (
                    <button
                      className="text-button"
                      disabled={pending.includes(task.id)}
                      aria-label={`Unassign ${task.ownerName} from ${task.text}`}
                      onClick={() => onUnassign(task)}
                    >
                      Unassign
                    </button>
                  )}
                </div>
              ))}
              {selected ? (
                <form onSubmit={e => submit(e, stop.id)}>
                  <div className="row-actions">
                    <label className="search-field">
                      <input
                        aria-label={`New task for ${stop.name}`}
                        placeholder="Add a task…"
                        value={draft.text}
                        onChange={e => setDraft({ ...draft, text: e.target.value })}
                      />
                    </label>
                  </div>
                  <div className="row-actions">
                    <select
                      aria-label="Task owner"
                      style={{ flex: 1, fontSize: 10 }}
                      value={draft.ownerId}
                      onChange={e => setDraft({ ...draft, ownerId: e.target.value })}
                    >
                      <option value="">Owner: {ANYONE}</option>
                      {members.map(member => (
                        <option key={member.id} value={member.id}>
                          Owner: {member.name}
                        </option>
                      ))}
                    </select>
                    <button type="submit" disabled={!draft.text.trim() || pending.includes(`new-task:${stop.id}`)}>
                      Add task
                    </button>
                  </div>
                </form>
              ) : (
                <div className="row-actions">
                  <button onClick={() => onSelect(stop.id)}>＋ Task</button>
                </div>
              )}
              <label className="complete">
                <input
                  type="checkbox"
                  disabled={!log.canCheckOff || pending.includes(`checkin:${stop.id}`)}
                  checked={stop.done}
                  onChange={() => onToggleDone(stop)}
                />{' '}
                Quest complete
              </label>
            </TripStopRow>
          )
        })}
      </div>
      <div className="board-bottom">
        <div className="tip">
          <p>
            Check-offs are shared with the whole crew.
            <br />
            <strong>A side quest is a possibility, not a promise.</strong>
          </p>
        </div>
      </div>
    </>
  )
}
