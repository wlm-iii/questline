// Pure snapshot → view-model adapters for the live trip workspace. No React, no fetch.
// IDs stay backend UUID strings; unknown values stay unknown.
import type {
  BudgetPreset,
  Endpoint,
  Generation,
  Import,
  JobStatus,
  Member,
  Message,
  Place,
  PlaceCategory,
  PlaceSource,
  Plan,
  PlanNode,
  Trip,
  TripSnapshot,
  Uuid,
} from '../api'

export const PRICE_UNKNOWN = 'Price unknown'
export const ANYONE = 'Anyone in the crew'
export const SUGGESTED_ORDER_NOTE = 'Suggested order, not a driving route'
export const DEVICE_ORDER_NOTE = "Saved on this device only. Others won't see this order yet."
export const PLAN_ORDER_NOTE = "This order comes from the crew's questline. Your device-only order is ignored while a plan exists."
export const NO_STOPS_NOTE = 'The planner returned no stops yet.'

export const categoryLabels: Record<PlaceCategory, string> = {
  eat: 'Eat',
  do: 'Do',
  stay: 'Stay',
  along_the_way: 'Along the way',
}
export const categories = Object.keys(categoryLabels) as PlaceCategory[]

export const presetLabels: Record<BudgetPreset, string> = {
  shoestring: 'Shoestring',
  comfortable: 'Comfortable',
  treat: 'Treat',
}
export const presets = Object.keys(presetLabels) as BudgetPreset[]
export type Preset = BudgetPreset

const sourceLabels: Record<PlaceSource, string> = {
  group: 'Group pick',
  suggested: 'AI suggestion',
  added: 'Added by search',
}

// ---------------------------------------------------------------- formatting

function dollars(amount: number): string {
  return `$${Number.isInteger(amount) ? amount : amount.toFixed(2)}`
}

/** A per-person range. Null is unknown, never free. */
export function formatAmount(low: number | null | undefined, high: number | null | undefined): string {
  if (low == null && high == null) return PRICE_UNKNOWN
  if (low != null && high != null) return low === high ? dollars(low) : `${dollars(low)}–${dollars(high)}`
  return low != null ? `From ${dollars(low)}` : `Up to ${dollars(high as number)}`
}

export function formatCost(low: number | null | undefined, high: number | null | undefined): string {
  const amount = formatAmount(low, high)
  return amount === PRICE_UNKNOWN ? amount : `${amount} / person est.`
}

function sentence(text: string): string {
  return /[.!?…]$/.test(text) ? text : `${text}.`
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`
}

function timeOf(iso: string | null, timezone: string): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  try {
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: timezone })
  } catch {
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  }
}

// ---------------------------------------------------------------- evidence

export type Quote = { id: Uuid; author: string; text: string }

export function quotesFor(messageIds: readonly string[], messages: Message[], members: Member[]): Quote[] {
  const byId = new Map(messages.map(message => [message.id, message]))
  const names = new Map(members.map(member => [member.id, member.name]))
  return messageIds.flatMap(id => {
    const message = byId.get(id)
    if (!message) return []
    const author = (message.member_id && names.get(message.member_id)) || message.author_id
    return [{ id: message.id, author, text: message.text }]
  })
}

export type UnresolvedMention = { key: string; text: string; quotes: Quote[] }

/** `trip.unresolved_mentions` entries are `{mention_text, message_ids}` from extraction. Malformed ones are skipped. */
export function unresolvedMentions(snapshot: TripSnapshot, importId: Uuid | null = null): UnresolvedMention[] {
  const fromImport = importId === null
    ? null
    : new Set(snapshot.messages.filter(message => message.import_id === importId).map(message => message.id))
  return (snapshot.trip.unresolved_mentions ?? []).flatMap((entry, index) => {
    const text = typeof entry.mention_text === 'string' ? entry.mention_text.trim() : ''
    if (!text) return []
    const ids = Array.isArray(entry.message_ids) ? entry.message_ids.filter((id): id is string => typeof id === 'string') : []
    if (fromImport && !ids.some(id => fromImport.has(id))) return []
    return [{ key: `${index}:${text}`, text, quotes: quotesFor(ids, snapshot.messages, snapshot.members) }]
  })
}

export type ImportView = {
  id: Uuid
  status: JobStatus
  active: boolean
  label: string
}

export function importView(imported: Import): ImportView {
  const messages = plural(imported.message_count, 'message')
  const labels: Record<JobStatus, string> = {
    queued: `Waiting to read ${messages}…`,
    running: `Finding places in ${messages}…`,
    succeeded: `Read ${messages}. Places are on the map.`,
    failed: imported.error || 'Import failed. Import again to retry.',
  }
  return {
    id: imported.id,
    status: imported.status,
    active: imported.status === 'queued' || imported.status === 'running',
    label: labels[imported.status],
  }
}

/** Imports still running, plus the most recent one when it failed. */
export function importsToShow(imports: Import[]): ImportView[] {
  const views = imports.map(importView)
  const active = views.filter(view => view.active)
  const last = views.at(-1)
  return last && last.status === 'failed' ? [...active, last] : active
}

// ---------------------------------------------------------------- places

export type QuestStatus = 'main' | 'side' | 'candidate'

export type StopView = {
  id: Uuid
  name: string
  address: string
  category: PlaceCategory
  categoryLabel: string
  lat: number
  lng: number
  googleMapsUri: string | null
  cost: string
  costLow: number | null
  costHigh: number | null
  sourceLabel: string
  mentionedBy: string | null
  quotes: Quote[]
  /** Shared state: from the current plan, or `candidate` when the place is not in it. */
  status: QuestStatus
  /** 1-based main quest position in the plan. */
  number: number | null
  why: string | null
  /** Side quests only: "+6 min" or "detour unknown". */
  detour: string | null
  arrive: string | null
  hours: string
  ownerName: string | null
  /** Shared "Quest complete" check-off. */
  done: boolean
}

type PlanStops = { main: PlanNode[]; side: PlanNode[] }

/** Stop nodes of a plan in travel order. Start and end nodes are never stops. */
export function planStops(plan: Plan | null): PlanStops | null {
  if (!plan?.content?.graph?.nodes) return null
  const nodes = plan.content.graph.nodes
  const rank = new Map<string, number>()
  for (const day of plan.content.days ?? []) {
    for (const id of day.node_ids) if (!rank.has(id)) rank.set(id, rank.size)
  }
  const stops = nodes
    .map((node, index) => ({ node, index }))
    .filter(({ node }) => node.role === 'stop')
    .sort((a, b) => (rank.get(a.node.id) ?? Infinity) - (rank.get(b.node.id) ?? Infinity) || a.index - b.index)
    .map(({ node }) => node)
  return { main: stops.filter(node => node.quest !== 'side'), side: stops.filter(node => node.quest === 'side') }
}

function memberName(members: Member[], id: Uuid | null): string | null {
  return (id && members.find(member => member.id === id)?.name) || null
}

function stopView(snapshot: TripSnapshot, place: Place, node: PlanNode | undefined, number: number | null): StopView {
  const [low, high] = node?.est_cost ?? [place.est_cost_low, place.est_cost_high]
  const side = node?.quest === 'side'
  return {
    id: place.id,
    name: place.name,
    address: place.address,
    category: place.category,
    categoryLabel: categoryLabels[place.category] ?? place.category,
    lat: place.lat,
    lng: place.lng,
    googleMapsUri: place.google_maps_uri,
    cost: formatCost(low, high),
    costLow: low ?? null,
    costHigh: high ?? null,
    sourceLabel: sourceLabels[place.source] ?? place.source,
    mentionedBy: place.mentioned_by_name,
    quotes: quotesFor(place.source_message_ids, snapshot.messages, snapshot.members),
    status: node ? (side ? 'side' : 'main') : 'candidate',
    number,
    why: node?.why || null,
    detour: side ? (node.detour_min == null ? 'detour unknown' : `+${node.detour_min} min`) : null,
    arrive: node ? timeOf(node.arrive, snapshot.trip.timezone) : null,
    hours: node?.hours_status === 'verified' ? 'Hours fit the schedule' : 'Hours unverified',
    ownerName: memberName(snapshot.members, node?.owner_member_id ?? null),
    done: snapshot.checkins.some(checkin => checkin.place_id === place.id),
  }
}

/** Every place with its shared status. Nodes that don't match a place are left out rather than invented. */
export function stopViews(snapshot: TripSnapshot): StopView[] {
  const plan = planStops(snapshot.current_plan)
  const nodes = new Map([...(plan?.main ?? []), ...(plan?.side ?? [])].map(node => [node.id, node]))
  const placeIds = new Set(snapshot.places.map(place => place.id))
  const mainOrder = (plan?.main ?? []).filter(node => placeIds.has(node.id)).map(node => node.id)
  return snapshot.places.map(place => {
    const node = nodes.get(place.id)
    const position = mainOrder.indexOf(place.id)
    return stopView(snapshot, place, node, node && position >= 0 ? position + 1 : null)
  })
}

// ---------------------------------------------------------------- ordering

type Point = { id: Uuid; lat: number; lng: number }

function distance(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const x = (b.lng - a.lng) * Math.cos(((a.lat + b.lat) / 2) * (Math.PI / 180))
  return Math.hypot(x, b.lat - a.lat)
}

/** Greedy nearest neighbour by straight-line distance, from the origin when there is one. Not a route. */
export function suggestedOrder(points: Point[], origin: { lat: number; lng: number } | null): Uuid[] {
  const pending = [...points].sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
  const order: Uuid[] = []
  let from = origin ?? pending[0]
  while (pending.length > 0) {
    let best = 0
    for (let i = 1; i < pending.length; i++) {
      if (distance(from, pending[i]) < distance(from, pending[best])) best = i
    }
    const [next] = pending.splice(best, 1)
    order.push(next.id)
    from = next
  }
  return order
}

/** A device-only draft: order and side quests, saved in localStorage per trip. */
export type DeviceOrder = { order: Uuid[]; side: Uuid[] }

export function isDeviceOrder(value: unknown): value is DeviceOrder {
  if (typeof value !== 'object' || value === null) return false
  const { order, side } = value as Record<string, unknown>
  return [order, side].every(list => Array.isArray(list) && list.every(id => typeof id === 'string'))
}

/** Device order first, then places it hasn't seen yet in suggested order. Unknown IDs are dropped. */
export function applyDeviceOrder(suggested: Uuid[], device: DeviceOrder | null): DeviceOrder {
  if (!device) return { order: suggested, side: [] }
  const known = new Set(suggested)
  const kept = device.order.filter(id => known.has(id))
  const seen = new Set(kept)
  return {
    order: [...kept, ...suggested.filter(id => !seen.has(id))],
    side: device.side.filter(id => known.has(id)),
  }
}

export function moveInDraft(draft: DeviceOrder, id: Uuid, offset: number): DeviceOrder {
  const order = [...draft.order]
  const index = order.indexOf(id)
  const target = index + offset
  if (index < 0 || target < 0 || target >= order.length) return draft
  ;[order[index], order[target]] = [order[target], order[index]]
  return { order, side: draft.side }
}

export function toggleDraftSide(draft: DeviceOrder, id: Uuid): DeviceOrder {
  const side = draft.side.includes(id) ? draft.side.filter(other => other !== id) : [...draft.side, id]
  return { order: draft.order, side }
}

// ---------------------------------------------------------------- questline

export type QuestlineRow = {
  stop: StopView
  /** Plan mode: the plan's role. Draft mode: the device-only role. */
  side: boolean
  number: number | null
}

export type QuestlineView = {
  source: 'plan' | 'device' | 'suggested'
  rows: QuestlineRow[]
  /** Places the current plan leaves out (plan mode only). */
  notInPlan: StopView[]
  draft: DeviceOrder
  orderNote: string
  deviceOverridesIgnored: boolean
}

function byName(a: StopView, b: StopView) {
  return a.name.localeCompare(b.name)
}

export function questlineView(snapshot: TripSnapshot, stops: StopView[], device: DeviceOrder | null): QuestlineView {
  const origin = snapshot.trip.origin
  const draft = applyDeviceOrder(suggestedOrder(stops, origin), device)
  const inPlan = stops.filter(stop => stop.status !== 'candidate')
  if (inPlan.length > 0) {
    const main = inPlan.filter(stop => stop.status === 'main').sort((a, b) => (a.number ?? 0) - (b.number ?? 0))
    const anchors = new Map((planStops(snapshot.current_plan)?.side ?? []).map(node => [node.id, node.anchor]))
    const sides = inPlan.filter(stop => stop.status === 'side')
    const sidesOf = (anchor: string | null) => sides.filter(stop => anchors.get(stop.id) === anchor)
    const placed = new Set<Uuid>()
    const ordered = [...sidesOf('start'), ...main.flatMap(stop => [stop, ...sidesOf(stop.id)])]
    ordered.forEach(stop => placed.add(stop.id))
    const rest = sides.filter(stop => !placed.has(stop.id))
    return {
      source: 'plan',
      rows: [...ordered, ...rest].map(stop => ({ stop, side: stop.status === 'side', number: stop.number })),
      notInPlan: stops.filter(stop => stop.status === 'candidate').sort(byName),
      draft,
      orderNote: device ? PLAN_ORDER_NOTE : "This order comes from the crew's questline.",
      deviceOverridesIgnored: device !== null,
    }
  }
  const byId = new Map(stops.map(stop => [stop.id, stop]))
  const side = new Set(draft.side)
  let number = 0
  const rows = draft.order.flatMap(id => {
    const stop = byId.get(id)
    if (!stop) return []
    const isSide = side.has(id)
    return [{ stop, side: isSide, number: isSide ? null : ++number }]
  })
  return {
    source: device ? 'device' : 'suggested',
    rows,
    notInPlan: [],
    draft,
    orderNote: device ? DEVICE_ORDER_NOTE : SUGGESTED_ORDER_NOTE,
    deviceOverridesIgnored: false,
  }
}

export type Estimate = { amount: string; note: string | null }

/** Sums draft main quests with a full known range. Anything else is counted as unpriced, never as $0. */
export function draftEstimate(rows: QuestlineRow[]): Estimate {
  const main = rows.filter(row => !row.side).map(row => row.stop)
  const priced = main.filter(stop => stop.costLow !== null && stop.costHigh !== null)
  const unknown = main.length - priced.length
  if (priced.length === 0) return { amount: PRICE_UNKNOWN, note: unknown ? `${plural(unknown, 'place')} without a price` : null }
  const low = priced.reduce((sum, stop) => sum + (stop.costLow ?? 0), 0)
  const high = priced.reduce((sum, stop) => sum + (stop.costHigh ?? 0), 0)
  return { amount: formatAmount(low, high), note: unknown ? `Partial: ${plural(unknown, 'place')} without a price` : null }
}

// ---------------------------------------------------------------- map

export type MapPointKind = 'stop' | 'candidate' | 'start' | 'end'

export type MapPoint = {
  id: string
  name: string
  side: boolean
  done: boolean
  lat: number
  lng: number
  kind: MapPointKind
  /** Live trips have no routing yet, so nothing is joined by a line. */
  route: false
}

function samePlace(a: Endpoint, b: Endpoint) {
  return a.google_place_id === b.google_place_id || (a.lat === b.lat && a.lng === b.lng)
}

export function endpointPoints(trip: Trip): MapPoint[] {
  const { origin, destination } = trip
  const point = (id: 'start' | 'end', name: string, at: Endpoint): MapPoint => ({
    id, name, side: false, done: false, lat: at.lat, lng: at.lng, kind: id, route: false,
  })
  if (origin && destination && samePlace(origin, destination)) return [point('start', `Start & end: ${origin.label}`, origin)]
  return [
    ...(origin ? [point('start', `Start: ${origin.label}`, origin)] : []),
    ...(destination ? [point('end', `End: ${destination.label}`, destination)] : []),
  ]
}

/** Endpoints, then main quests in plan order (QuestMap numbers them by position), then the rest. */
export function mapPoints(trip: Trip, stops: StopView[]): MapPoint[] {
  const main = stops.filter(stop => stop.status === 'main').sort((a, b) => (a.number ?? 0) - (b.number ?? 0))
  const rest = stops.filter(stop => stop.status !== 'main')
  return [
    ...endpointPoints(trip),
    ...[...main, ...rest].map(stop => ({
      id: stop.id,
      name: stop.name,
      side: stop.status === 'side',
      done: stop.done,
      lat: stop.lat,
      lng: stop.lng,
      kind: stop.status === 'candidate' ? 'candidate' as const : 'stop' as const,
      route: false as const,
    })),
  ]
}

// ---------------------------------------------------------------- quest log

export type MemberOption = { id: Uuid; name: string }

export type TaskView = { id: Uuid; text: string; done: boolean; ownerId: Uuid | null; ownerName: string | null }

export type QuestLogEntry = { stop: StopView; owner: string; tasks: TaskView[] }

export type QuestLogView = {
  entries: QuestLogEntry[]
  /** Main quests only; start and end are never counted. Null without a plan. */
  progress: { done: number; total: number } | null
  canCheckOff: boolean
  hint: string | null
  nextUp: StopView | null
}

export function questLogView(snapshot: TripSnapshot, questline: QuestlineView): QuestLogView {
  const plan = snapshot.current_plan
  const accepted = plan?.status === 'accepted'
  const stops = questline.rows.map(row => row.stop)
  const entries = stops.map(stop => {
    const tasks = snapshot.tasks
      .filter(task => task.place_id === stop.id)
      .map(task => ({
        id: task.id,
        text: task.text,
        done: task.done_at !== null,
        ownerId: task.owner_member_id,
        ownerName: memberName(snapshot.members, task.owner_member_id),
      }))
    const taskOwners = [...new Set(tasks.flatMap(task => (task.ownerName ? [task.ownerName] : [])))]
    return { stop, owner: stop.ownerName ?? (taskOwners.join(', ') || ANYONE), tasks }
  })
  const main = questline.source === 'plan' ? stops.filter(stop => stop.status === 'main') : []
  return {
    entries,
    progress: main.length ? { done: main.filter(stop => stop.done).length, total: main.length } : null,
    canCheckOff: accepted,
    hint: accepted
      ? null
      : plan
        ? 'Accept the questline to check off quests.'
        : 'Build and accept a questline to check off quests. Tasks work now.',
    nextUp: accepted ? main.find(stop => !stop.done) ?? null : null,
  }
}

// ---------------------------------------------------------------- build

export type JobView = { id: Uuid; status: JobStatus; active: boolean; label: string }

export type PlanView = {
  id: Uuid
  revision: number
  accepted: boolean
  statusLabel: string
  title: string
  presetLabel: string
  mainCount: number
  sideCount: number
  hasStops: boolean
  estimate: Estimate
  warnings: string[]
  conflicts: string[]
  changes: string[]
  assumptions: string[]
}

export type BuildView = { plan: PlanView | null; job: JobView | null; building: boolean }

function jobView(job: Generation, hasPlan: boolean): JobView {
  const preset = presetLabels[job.budget_preset] ?? job.budget_preset
  const labels: Record<JobStatus, string> = {
    queued: `${preset} build queued…`,
    running: `Building a ${preset} questline…`,
    succeeded: `${preset} build finished.`,
    failed: `${sentence(`The ${preset} build failed${job.error ? `: ${job.error.trim()}` : ''}`)}${hasPlan ? ' The previous questline is still shown.' : ''}`,
  }
  return { id: job.id, status: job.status, active: job.status === 'queued' || job.status === 'running', label: labels[job.status] }
}

function planEstimate(plan: Plan): Estimate {
  const content = plan.content
  const [low, high] = content.per_person_estimate ?? [null, null]
  const notes = [
    content.estimate_is_partial ? `Partial: ${plural(content.unpriced_node_ids?.length ?? 0, 'stop')} without a price` : null,
    content.excluded_costs?.length ? `Excludes ${content.excluded_costs.join(', ')}` : null,
  ].filter(Boolean)
  return { amount: formatAmount(low, high), note: notes.join('. ') || null }
}

/** `trackedId` is the generation this browser just started, so its status shows even if others exist. */
export function buildView(snapshot: TripSnapshot, trackedId: Uuid | null = null): BuildView {
  const plan = snapshot.current_plan
  const stops = planStops(plan)
  const jobs = snapshot.jobs
  const job = jobs.find(j => j.id === trackedId) ?? jobs.find(j => j.status === 'queued' || j.status === 'running') ?? jobs.at(-1) ?? null
  const view = job ? jobView(job, plan !== null) : null
  return {
    plan: plan && {
      id: plan.id,
      revision: plan.revision,
      accepted: plan.status === 'accepted',
      statusLabel: plan.status === 'accepted' ? 'Accepted' : 'Draft',
      title: plan.content?.title ?? '',
      presetLabel: presetLabels[plan.budget_preset] ?? plan.budget_preset,
      mainCount: stops?.main.length ?? 0,
      sideCount: stops?.side.length ?? 0,
      hasStops: Boolean(stops && stops.main.length + stops.side.length > 0),
      estimate: planEstimate(plan),
      warnings: plan.content?.warnings ?? [],
      conflicts: (plan.content?.conflicts ?? []).map(conflict => conflict.detail),
      changes: plan.content?.changed_from_previous ?? [],
      assumptions: plan.content?.assumptions ?? [],
    },
    job: view,
    building: view?.active ?? false,
  }
}

// ---------------------------------------------------------------- workspace

export type WorkspaceView = {
  stops: StopView[]
  questline: QuestlineView
  questLog: QuestLogView
  build: BuildView
  map: MapPoint[]
  members: MemberOption[]
  imports: ImportView[]
  unresolved: UnresolvedMention[]
  stats: string
  defaultPreset: BudgetPreset
}

export function workspaceView(snapshot: TripSnapshot, device: DeviceOrder | null, trackedGenerationId: Uuid | null = null): WorkspaceView {
  const stops = stopViews(snapshot)
  const questline = questlineView(snapshot, stops, device)
  return {
    stops,
    questline,
    questLog: questLogView(snapshot, questline),
    build: buildView(snapshot, trackedGenerationId),
    map: mapPoints(snapshot.trip, stops),
    members: snapshot.members.map(member => ({ id: member.id, name: member.name })),
    imports: importsToShow(snapshot.imports),
    unresolved: unresolvedMentions(snapshot),
    stats: `${plural(stops.length, 'waypoint')} from ${plural(snapshot.messages.length, 'message')}`,
    defaultPreset: snapshot.trip.budget_preset,
  }
}
