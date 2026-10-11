import { QuestBadge } from '../../components/QuestBadge'
import {
  NO_STOPS_NOTE,
  presetLabels,
  presets,
  type BuildView,
  type Estimate,
  type Preset,
  type QuestlineView,
} from '../adapters'
import { StatusBadge } from './StatusBadge'
import { TripBudget } from './TripBudget'
import { TripStopRow } from './TripStopRow'

export type BuildMessage = { text: string; canRetry: boolean }

export type QuestlinePanelProps = {
  questline: QuestlineView
  build: BuildView
  estimate: Estimate
  preset: Preset
  selectedId: string | null
  /** A build request is in flight. */
  requesting: boolean
  buildMessage: BuildMessage | null
  accepting: boolean
  acceptMessage: string | null
  onPresetChange: (preset: Preset) => void
  onBuild: () => void
  onRetry: () => void
  onAccept: () => void
  onOpenLog: () => void
  onSelect: (id: string) => void
  onMove: (id: string, offset: number) => void
  onToggleSide: (id: string) => void
  onResetOrder: () => void
}

export function QuestlinePanel({
  questline,
  build,
  estimate,
  preset,
  selectedId,
  requesting,
  buildMessage,
  accepting,
  acceptMessage,
  onPresetChange,
  onBuild,
  onRetry,
  onAccept,
  onOpenLog,
  onSelect,
  onMove,
  onToggleSide,
  onResetOrder,
}: QuestlinePanelProps) {
  const { plan, job } = build
  const fromPlan = questline.source === 'plan'
  const rows = questline.rows
  const busy = requesting || build.building
  return (
    <>
      <div className="intro">
        <h3>{plan?.title || 'A little plan. A lot to discover.'}</h3>
        <p>
          {plan
            ? `${plan.presetLabel} · ${plan.statusLabel} · revision ${plan.revision}`
            : "No questline yet. Build one from the crew's places."}
        </p>
      </div>
      <div className="filters" role="group" aria-label="Budget preset">
        {presets.map(option => (
          <button key={option} className={preset === option ? 'active' : ''} aria-pressed={preset === option} onClick={() => onPresetChange(option)}>
            {presetLabels[option]}
          </button>
        ))}
      </div>
      <div className="route-summary">
        <button className="text-button" disabled={busy} onClick={onBuild}>
          {requesting ? 'Requesting a build…' : plan ? `Rebuild as ${presetLabels[preset]} →` : `Build a ${presetLabels[preset]} questline →`}
        </button>
        {plan?.hasStops && (
          <>
            <span>↗ {plan.mainCount} main quests</span>
            <span>✧ {plan.sideCount} side quests</span>
          </>
        )}
        <p>
          {questline.orderNote}
          {questline.source === 'device' && (
            <>
              <br />
              Not a driving route.
            </>
          )}
        </p>
      </div>
      {job?.active && <div className="route-summary" role="status">{job.label}</div>}
      {job?.status === 'failed' && !buildMessage && (
        <div className="inline-warning" role="alert">
          {job.label}{' '}
          <button className="text-button" disabled={busy} onClick={onBuild}>
            Build again →
          </button>
        </div>
      )}
      {buildMessage && (
        <div className="inline-warning" role="alert">
          {buildMessage.text}{' '}
          {buildMessage.canRetry && (
            <button className="text-button" disabled={busy} onClick={onRetry}>
              Try again →
            </button>
          )}
        </div>
      )}
      {plan && !plan.hasStops && <div className="inline-warning">{NO_STOPS_NOTE}</div>}
      <div className="stop-list">
        {rows.length === 0 && (
          <div className="empty-list">
            <strong>No places yet</strong>
            <p>Import the group chat or add a place by search on the Waypoints tab.</p>
          </div>
        )}
        {rows.map(({ stop, side, number }, index) => (
          <TripStopRow
            key={stop.id}
            stop={stop}
            marker={side ? '✧' : String(number ?? '·')}
            hollow={side}
            selected={selectedId === stop.id}
            details={
              fromPlan
                ? [
                    [stop.arrive, stop.categoryLabel, stop.cost].filter(Boolean).join(' · '),
                    ...(stop.detour ? [stop.detour] : []),
                    ...(stop.why ? [stop.why] : []),
                  ]
                : [`${stop.categoryLabel} · ${stop.cost}`]
            }
            badge={fromPlan ? <StatusBadge status={stop.status} /> : <QuestBadge kind={side ? 'side' : 'main'}>{side ? 'Side (draft)' : 'Main (draft)'}</QuestBadge>}
            onSelect={onSelect}
          >
            {!fromPlan && (
              <div className="row-actions">
                <button disabled={index === 0} aria-label={`Move ${stop.name} earlier`} onClick={() => onMove(stop.id, -1)}>
                  ↑ Earlier
                </button>
                <button disabled={index === rows.length - 1} aria-label={`Move ${stop.name} later`} onClick={() => onMove(stop.id, 1)}>
                  ↓ Later
                </button>
                <button onClick={() => onToggleSide(stop.id)}>Make {side ? 'main' : 'side'} quest</button>
              </div>
            )}
          </TripStopRow>
        ))}
        {questline.notInPlan.length > 0 && (
          <section aria-label="Not in this questline">
            <p className="eyebrow" style={{ padding: '12px 10px 4px' }}>
              NOT IN THIS QUESTLINE · {questline.notInPlan.length}
            </p>
            {questline.notInPlan.map(stop => (
              <TripStopRow
                key={stop.id}
                stop={stop}
                marker="·"
                hollow
                selected={selectedId === stop.id}
                details={[`${stop.categoryLabel} · ${stop.cost}`]}
                onSelect={onSelect}
              />
            ))}
          </section>
        )}
        {plan && plan.conflicts.length + plan.warnings.length + plan.changes.length > 0 && (
          <section aria-label="Planner notes">
            <p className="eyebrow" style={{ padding: '12px 10px 4px' }}>
              PLANNER NOTES
            </p>
            <div className="inline-warning" style={{ margin: '0 0 12px' }}>
              {plan.conflicts.map(conflict => <div key={conflict}>⚠ {conflict}</div>)}
              {plan.warnings.map(warning => <div key={warning}>{warning}</div>)}
              {plan.changes.length > 0 && <div>Changed from the previous plan: {plan.changes.join('; ')}</div>}
            </div>
          </section>
        )}
      </div>
      <div className="board-bottom">
        {questline.source === 'device' && (
          <button className="text-button" onClick={onResetOrder}>
            Reset to the suggested order
          </button>
        )}
        <TripBudget estimate={estimate} scope={fromPlan ? 'Main quests in this plan' : 'Draft main quests'} />
        {plan && (
          <button className="primary accept" disabled={!plan.hasStops || accepting} onClick={plan.accepted ? onOpenLog : onAccept}>
            {plan.accepted ? 'Accepted · Open the quest log →' : accepting ? 'Accepting…' : 'Accept the questline →'}
          </button>
        )}
        {acceptMessage && (
          <p className="budget-warning" role="alert">
            {acceptMessage}
          </p>
        )}
        <p className="footer-note">Made for the plans that finally leave the group chat.</p>
      </div>
    </>
  )
}
