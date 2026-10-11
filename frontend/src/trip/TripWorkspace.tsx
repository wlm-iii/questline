import { useMemo, useState } from 'react'
import { isApiError, newIdempotencyKey, type MemberApi, type PlanOperation, type Uuid, type VoteKind } from '../api'
import { useTrip } from '../state'
import { DialogHost } from '../components/dialogs/DialogHost'
import { Notice } from '../components/Notice'
import { googleMapsEnabled } from '../features/map/config'
import { ANYONE, draftEstimate, moveInDraft, toggleDraftSide, workspaceView, type Preset, type StopView, type TaskView } from './adapters'
import { BUILD_UNAVAILABLE, PLAN_CHANGED, errorCode, errorMessage, isConflict, isRetryable } from './errors'
import { useAddPlace } from './useAddPlace'
import { useDeviceOrder } from './useDeviceOrder'
import { PlaceDetails } from './ui/PlaceDetails'
import { QuestLogPanel } from './ui/QuestLogPanel'
import { QuestlinePanel, type BuildMessage, type ResolveState } from './ui/QuestlinePanel'
import { TripBoard, type BoardTab } from './ui/TripBoard'
import { TripMapPanel } from './ui/TripMapPanel'
import { TripPlaceCard } from './ui/TripPlaceCard'
import { WaypointsPanel } from './ui/WaypointsPanel'

type BuildAttempt = { preset: Preset; key: string }

export type TripWorkspaceProps = {
  /** Controlled board tab; uncontrolled when absent. */
  tab?: BoardTab
  onTabChange?: (tab: BoardTab) => void
  /** Opens the trip's single Import chat dialog, owned by TripApp. */
  onImport: () => void
}

/** The live map and quest board for the trip in the surrounding TripProvider. */
export function TripWorkspace({ tab: controlledTab, onTabChange, onImport }: TripWorkspaceProps) {
  const { session, snapshot, error, mutate } = useTrip()
  const tripId = session.tripId
  const [device, setDevice] = useDeviceOrder(tripId)
  const places = useAddPlace()
  const [selectedId, setSelectedId] = useState<Uuid | null>(null)
  const [ownTab, setOwnTab] = useState<BoardTab>('Waypoints')
  const tab = controlledTab ?? ownTab
  const setTab = onTabChange ?? setOwnTab
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const [preset, setPreset] = useState<Preset | null>(null)
  const [attempt, setAttempt] = useState<BuildAttempt | null>(null)
  const [requesting, setRequesting] = useState(false)
  const [buildMessage, setBuildMessage] = useState<BuildMessage | null>(null)
  const [trackedGeneration, setTrackedGeneration] = useState<Uuid | null>(null)
  const [accepting, setAccepting] = useState(false)
  const [acceptMessage, setAcceptMessage] = useState<string | null>(null)
  const [pending, setPending] = useState<string[]>([])
  const [logMessage, setLogMessage] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [editMessage, setEditMessage] = useState<string | null>(null)
  const [resolving, setResolving] = useState<ResolveState | null>(null)

  const view = useMemo(
    () => (snapshot ? workspaceView(snapshot, device, trackedGeneration, session.memberId) : null),
    [snapshot, device, trackedGeneration, session.memberId],
  )

  if (!view) {
    return (
      <div className="planner">
        <section className="map-panel">
          <div className="empty-map" role="status">
            <h2>{error ? "Couldn't load the trip." : 'Loading the trip…'}</h2>
            <p>{error ? `${errorMessage(error)} Retrying automatically.` : 'Fetching places and the questline.'}</p>
          </div>
        </section>
        <aside className="sidebar" />
      </div>
    )
  }

  const selected = view.stops.find(stop => stop.id === selectedId) ?? null
  const activePreset = preset ?? view.defaultPreset
  const plan = view.build.plan
  const fromPlan = view.questline.source === 'plan'

  function select(id: string) {
    if (view?.stops.some(stop => stop.id === id)) setSelectedId(id)
  }

  function ownerOf(stop: StopView) {
    return view?.questLog.entries.find(entry => entry.stop.id === stop.id)?.owner ?? stop.ownerName ?? ANYONE
  }

  async function addPlace(query: string) {
    const place = await places.addPlace(query)
    if (!place) return false
    setSelectedId(place.id)
    setNotice(`${place.name} is on the map.`)
    return true
  }

  async function runBuild(next: BuildAttempt) {
    setAttempt(next)
    setRequesting(true)
    setBuildMessage(null)
    try {
      const { generation } = await mutate(api => api.startGeneration(tripId, next.preset, next.key))
      setTrackedGeneration(generation.id)
      setAttempt(null)
    } catch (failure) {
      if (errorCode(failure) === 'provider_unavailable') {
        setBuildMessage({ text: BUILD_UNAVAILABLE, canRetry: true })
      } else if (errorCode(failure) === 'plan_in_progress') {
        setAttempt(null)
        const running = isApiError(failure) ? failure.details.generation_id : null
        if (typeof running === 'string') setTrackedGeneration(running)
        setBuildMessage({ text: 'Another budget preset is already building. Wait for it to finish, then build again.', canRetry: false })
      } else {
        if (!isRetryable(failure)) setAttempt(null)
        setBuildMessage({ text: errorMessage(failure), canRetry: isRetryable(failure) })
      }
    } finally {
      setRequesting(false)
    }
  }

  async function accept() {
    if (!plan) return
    setAccepting(true)
    setAcceptMessage(null)
    try {
      await mutate(api => api.acceptPlan(plan.id, plan.revision))
      setTab('Quest log')
      setNotice('Questline accepted. Check off each quest as you go.')
    } catch (failure) {
      setAcceptMessage(isConflict(failure) ? PLAN_CHANGED : errorMessage(failure))
    } finally {
      setAccepting(false)
    }
  }

  async function write(key: string, action: (api: MemberApi) => Promise<unknown>) {
    setPending(current => [...current, key])
    setLogMessage(null)
    try {
      await mutate(action)
      return true
    } catch (failure) {
      setLogMessage(errorMessage(failure))
      return false
    } finally {
      setPending(current => current.filter(other => other !== key))
    }
  }

  const vote = (stop: StopView, kind: VoteKind) => void write(`vote:${stop.id}`, api => api.vote(stop.id, kind))
  const voting = pending.flatMap(key => (key.startsWith('vote:') ? [key.slice(5)] : []))

  async function edit(operations: PlanOperation[]) {
    if (!plan) return false
    setEditing(true)
    setEditMessage(null)
    try {
      await mutate(api => api.editPlan(plan.id, plan.revision, operations))
      setResolving(null)
      return true
    } catch (failure) {
      setEditMessage(isConflict(failure) ? 'Someone else just changed the questline. Check it and try again.' : errorMessage(failure))
      return false
    } finally {
      setEditing(false)
    }
  }

  async function resolve(stop: StopView) {
    if (!plan) return
    setResolving({ stopId: stop.id, options: null, error: null })
    try {
      const { options } = await mutate(api => api.resolve(plan.id, stop.id))
      setResolving({ stopId: stop.id, options, error: null })
    } catch (failure) {
      setResolving({ stopId: stop.id, options: null, error: errorMessage(failure) })
    }
  }

  const assignOwner = (stop: StopView, memberId: string | null) =>
    void write(`owner:${stop.id}`, api =>
      plan ? api.editPlan(plan.id, plan.revision, [{ op: 'assign_owner', node_id: stop.id, member_id: memberId }]) : Promise.resolve(),
    )

  const createTask = (placeId: string, text: string, ownerId: string | null) =>
    write(`new-task:${placeId}`, api =>
      api.createTask(tripId, { place_id: placeId, text: text.trim(), ...(ownerId ? { owner_member_id: ownerId } : {}) }),
    )
  const toggleTask = (task: TaskView) => void write(task.id, api => api.updateTask(task.id, { done: !task.done }))
  const unassign = (task: TaskView) => void write(task.id, api => api.updateTask(task.id, { owner_member_id: null }))
  const toggleDone = (stop: StopView) =>
    void write(`checkin:${stop.id}`, api => (stop.done ? api.undoCheckIn(stop.id) : api.checkIn(stop.id)))

  return (
    <>
      <div className="planner">
        <TripMapPanel
          points={view.map}
          routes={view.routes}
          selectedId={selectedId}
          mapEnabled={googleMapsEnabled}
          hasPlaces={view.stops.length > 0}
          onSelect={select}
          onImport={onImport}
        >
          {selected && (
            <TripPlaceCard stop={selected} voting={voting.includes(selected.id)} onVote={vote} onView={() => setDetailsOpen(true)} />
          )}
        </TripMapPanel>
        <TripBoard tab={tab} onTabChange={setTab}>
          {tab === 'Waypoints' && (
            <WaypointsPanel
              stops={view.stops}
              selectedId={selectedId}
              stats={view.stats}
              imports={view.imports}
              unresolved={view.unresolved}
              adding={places.pending}
              addError={places.error}
              onAddPlace={addPlace}
              onSelect={select}
              onImport={onImport}
              voting={voting}
              onVote={vote}
            />
          )}
          {tab === 'Questline' && (
            <QuestlinePanel
              questline={view.questline}
              build={view.build}
              estimate={fromPlan && plan ? plan.estimate : draftEstimate(view.questline.rows)}
              preset={activePreset}
              selectedId={selectedId}
              requesting={requesting}
              buildMessage={buildMessage}
              accepting={accepting}
              acceptMessage={acceptMessage}
              onPresetChange={setPreset}
              onBuild={() => void runBuild({ preset: activePreset, key: newIdempotencyKey() })}
              onRetry={() => attempt && void runBuild(attempt)}
              onAccept={() => void accept()}
              onOpenLog={() => setTab('Quest log')}
              onSelect={select}
              onMove={(id, offset) => setDevice(moveInDraft(view.questline.draft, id, offset))}
              onToggleSide={id => setDevice(toggleDraftSide(view.questline.draft, id))}
              onResetOrder={() => setDevice(null)}
              editing={editing}
              editMessage={editMessage}
              onEdit={operations => void edit(operations)}
              resolving={resolving}
              onResolve={stop => void resolve(stop)}
              onCloseResolve={() => setResolving(null)}
            />
          )}
          {tab === 'Quest log' && (
            <QuestLogPanel
              log={view.questLog}
              members={view.members}
              selectedId={selectedId}
              accepted={plan?.accepted ?? false}
              pending={pending}
              message={logMessage}
              onSelect={select}
              onCreateTask={createTask}
              onToggleTask={toggleTask}
              onUnassign={unassign}
              onToggleDone={toggleDone}
              onAssignOwner={assignOwner}
            />
          )}
        </TripBoard>
      </div>
      {notice && <Notice message={notice} onDismiss={() => setNotice('')} />}
      <DialogHost open={detailsOpen && selected !== null} onClose={() => setDetailsOpen(false)}>
        {selected && <PlaceDetails stop={selected} owner={ownerOf(selected)} />}
      </DialogHost>
    </>
  )
}
