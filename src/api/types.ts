// Mirrors backend/src/questline/schemas.py and persistence_schemas.py.
// Keep in sync with the backend; the FastAPI schema at /docs is the source of truth.

/** A backend UUID. Never substitute a Google place ID. */
export type Uuid = string
/** ISO 8601 date, `YYYY-MM-DD`. */
export type IsoDate = string
/** ISO 8601 date-time with an offset. */
export type IsoDateTime = string

export type BudgetPreset = 'shoestring' | 'comfortable' | 'treat'
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed'
export type VoteKind = 'in' | 'ok' | 'out'
export type PlaceCategory = 'eat' | 'do' | 'stay' | 'along_the_way'
export type PlaceSource = 'group' | 'suggested' | 'added'

export type Endpoint = {
  label: string
  google_place_id: string
  lat: number
  lng: number
}

export type Member = {
  id: Uuid
  trip_id: Uuid
  name: string
  imessage_handle: string | null
  discord_user_id: string | null
}

export type Trip = {
  id: Uuid
  name: string
  origin: Endpoint | null
  destination: Endpoint | null
  start_date: IsoDate | null
  end_date: IsoDate | null
  timezone: string
  budget_preset: BudgetPreset
  current_plan_id: Uuid | null
  imessage_chat_guid: string | null
  unresolved_mentions: Record<string, unknown>[]
  /** Trip revision. Distinct from a plan's revision. */
  revision: number
  created_at: IsoDateTime
}

export type TripCreate = {
  name: string
  origin: string
  destination: string
  start_date: IsoDate
  /** One to three inclusive days after `start_date`. */
  end_date: IsoDate
  /** IANA timezone, for example `America/Los_Angeles`. */
  timezone: string
  organizer_name: string
}

export type JoinResult = {
  member: Member
  member_token: string
}

export type TripCreated = JoinResult & { trip: Trip }

export type Message = {
  id: Uuid
  external_id: string
  author_id: string
  sent_at: IsoDateTime
  text: string
  member_id: Uuid | null
  source: string
  import_id: Uuid | null
  reply_to_guid: string | null
  reply_to_id: Uuid | null
}

export type MessageInput = {
  external_id: string
  author_id: string
  sent_at: IsoDateTime
  text: string
}

export type IngestResult = {
  inserted: number
  revision: number
}

export type Place = {
  id: Uuid
  trip_id: Uuid
  google_place_id: string
  name: string
  category: PlaceCategory
  address: string
  lat: number
  lng: number
  google_maps_uri: string | null
  price_level: number | null
  /** Null means unknown, not free. */
  est_cost_low: number | null
  est_cost_high: number | null
  cost_basis: string | null
  source: PlaceSource
  mentioned_by: Uuid | null
  mentioned_by_name: string | null
  source_message_ids: Uuid[]
  vote_tallies: Record<VoteKind, number>
  /** True when the place has at least one `in` and one `out` vote. */
  contested: boolean
}

export type Vote = {
  id: Uuid
  trip_id: Uuid
  place_id: Uuid
  member_id: Uuid
  kind: VoteKind
}

export type Import = {
  id: Uuid
  trip_id: Uuid
  source: 'paste' | 'imessage'
  status: JobStatus
  message_count: number
  error: string | null
}

export type ImportStarted = {
  import_id: Uuid
  message_count: number
  inserted: number
  status: JobStatus
}

export type Task = {
  id: Uuid
  trip_id: Uuid
  place_id: Uuid
  text: string
  owner_member_id: Uuid | null
  done_at: IsoDateTime | null
  created_by: Uuid | null
}

export type TaskCreate = {
  place_id: Uuid
  text: string
  owner_member_id?: Uuid | null
}

/** Omitted fields are left unchanged. `owner_member_id: null` unassigns. */
export type TaskUpdate = {
  text?: string
  owner_member_id?: Uuid | null
  done?: boolean
}

export type Checkin = {
  id: Uuid
  trip_id: Uuid
  place_id: Uuid
  member_id: Uuid | null
  completed_at: IsoDateTime
}

export type Generation = {
  id: Uuid
  trip_id: Uuid
  transcript_revision: number
  budget_preset: BudgetPreset
  previous_plan_id: Uuid | null
  status: JobStatus
  plan_id: Uuid | null
  error: string | null
}

export type PlanNode = {
  id: string
  kind: 'place' | 'activity' | 'lodging'
  role: 'start' | 'stop' | 'end'
  quest: 'main' | 'side'
  /** For side quests, the ID of the main node it branches from. */
  anchor: string | null
  title: string
  notes: string
  source_message_ids: Uuid[]
  place_id: string | null
  lat: number | null
  lng: number | null
  category: PlaceCategory | null
  arrive: IsoDateTime | null
  depart: IsoDateTime | null
  duration_min: number | null
  detour_min: number | null
  est_cost: [number, number] | null
  cost_basis: string | null
  hours_status: 'verified' | 'unknown'
  source: PlaceSource
  why: string
  owner_member_id: Uuid | null
}

export type PlanEdge = {
  id: string
  source: string
  target: string
  kind: 'precedes' | 'travel' | 'alternative' | 'detour'
  drive_min: number | null
  distance_m: number | null
  /** Encoded polyline, when routing exists. */
  polyline: string | null
  detour_min: number | null
}

export type PlanDay = {
  date: IsoDate
  start_at: IsoDateTime
  end_at: IsoDateTime
  node_ids: string[]
}

export type Conflict = {
  node_id: string
  kind: 'split_vote' | 'over_budget' | 'does_not_fit' | 'hours'
  detail: string
}

export type PlanContent = {
  title: string
  budget_preset: BudgetPreset
  currency: 'USD'
  timezone: string
  derived_stale: boolean
  graph: { nodes: PlanNode[]; edges: PlanEdge[] }
  days: PlanDay[]
  per_person_estimate: [number, number] | null
  estimate_scope: 'food_and_activities_main_quest'
  estimate_is_partial: boolean
  unpriced_node_ids: string[]
  excluded_costs: string[]
  conflicts: Conflict[]
  changed_from_previous: string[]
  assumptions: string[]
  open_questions: string[]
  warnings: string[]
}

export type Plan = {
  id: Uuid
  trip_id: Uuid
  generation_id: Uuid
  budget_preset: BudgetPreset
  /** Plan revision. Distinct from the trip revision. */
  revision: number
  status: 'draft' | 'accepted'
  accepted_at: IsoDateTime | null
  content: PlanContent
}

export type TripSnapshot = {
  trip: Trip
  members: Member[]
  places: Place[]
  votes: Vote[]
  tasks: Task[]
  checkins: Checkin[]
  imports: Import[]
  messages: Message[]
  current_plan: Plan | null
  jobs: Generation[]
  revision: number
}

export type TripUnchanged = { unchanged: true; revision: number }

export type TripPoll = TripSnapshot | TripUnchanged
