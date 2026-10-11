import { request } from './client'
import type {
  BudgetPreset,
  Checkin,
  Generation,
  ImportStarted,
  IngestResult,
  JoinResult,
  MessageInput,
  Place,
  Plan,
  Task,
  TaskCreate,
  TaskUpdate,
  TripCreate,
  TripCreated,
  TripPoll,
  Uuid,
  Vote,
  VoteKind,
} from './types'

type Call = { signal?: AbortSignal }

const seg = encodeURIComponent

/** Routes that need no member token. */
export const publicApi = {
  createTrip(body: TripCreate, { signal }: Call = {}) {
    return request<TripCreated>('/trips', { method: 'POST', body, signal })
  },
  joinTrip(tripId: Uuid, name: string, { signal }: Call = {}) {
    return request<JoinResult>(`/trips/${seg(tripId)}/members`, { method: 'POST', body: { name }, signal })
  },
}

/** Trip-scoped routes a browser member can call. Service-only routes are deliberately absent. */
export type MemberApi = {
  /** Pass the last known trip revision to get `{ unchanged: true }` instead of a full snapshot. */
  getTrip(tripId: Uuid, revision?: number, call?: Call): Promise<TripPoll>
  /** Paste a `Name: text` transcript. Extraction runs as a background job. */
  importChat(tripId: Uuid, text: string, call?: Call): Promise<ImportStarted>
  /** Stores messages only; it does not start place extraction. */
  addMessages(tripId: Uuid, messages: MessageInput[], call?: Call): Promise<IngestResult>
  addPlace(tripId: Uuid, query: string, call?: Call): Promise<{ place: Place }>
  /** Voting the member's current choice again clears it and returns `vote: null`. */
  vote(placeId: Uuid, kind: VoteKind, call?: Call): Promise<{ vote: Vote | null }>
  createTask(tripId: Uuid, body: TaskCreate, call?: Call): Promise<{ task: Task }>
  updateTask(taskId: Uuid, body: TaskUpdate, call?: Call): Promise<{ task: Task }>
  /** Shared for the whole trip, not per member. */
  checkIn(placeId: Uuid, call?: Call): Promise<{ checkin: Checkin }>
  undoCheckIn(placeId: Uuid, call?: Call): Promise<void>
  /** Reuse `idempotencyKey` when retrying the same build; use a new one for a new build. */
  startGeneration(tripId: Uuid, budgetPreset: BudgetPreset, idempotencyKey: string, call?: Call): Promise<{ generation: Generation }>
  getGeneration(generationId: Uuid, call?: Call): Promise<{ generation: Generation }>
  getPlan(planId: Uuid, call?: Call): Promise<{ plan: Plan }>
  /** `revision` is the plan's revision. A stale one fails with 409. */
  acceptPlan(planId: Uuid, revision: number, call?: Call): Promise<{ plan: Plan }>
}

export function createMemberApi(memberToken: string): MemberApi {
  const auth = { memberToken }
  return {
    getTrip(tripId, revision, { signal } = {}) {
      const query = revision === undefined ? '' : `?revision=${revision}`
      return request(`/trips/${seg(tripId)}${query}`, { ...auth, signal })
    },
    importChat(tripId, text, { signal } = {}) {
      return request(`/trips/${seg(tripId)}/import`, { ...auth, method: 'POST', body: { text }, signal })
    },
    addMessages(tripId, messages, { signal } = {}) {
      return request(`/trips/${seg(tripId)}/messages/batch`, { ...auth, method: 'POST', body: { messages }, signal })
    },
    addPlace(tripId, query, { signal } = {}) {
      return request(`/trips/${seg(tripId)}/places`, { ...auth, method: 'POST', body: { query }, signal })
    },
    vote(placeId, kind, { signal } = {}) {
      return request(`/places/${seg(placeId)}/votes`, { ...auth, method: 'POST', body: { kind }, signal })
    },
    createTask(tripId, body, { signal } = {}) {
      return request(`/trips/${seg(tripId)}/tasks`, { ...auth, method: 'POST', body, signal })
    },
    updateTask(taskId, body, { signal } = {}) {
      return request(`/tasks/${seg(taskId)}`, { ...auth, method: 'PATCH', body, signal })
    },
    checkIn(placeId, { signal } = {}) {
      return request(`/places/${seg(placeId)}/checkins`, { ...auth, method: 'POST', signal })
    },
    undoCheckIn(placeId, { signal } = {}) {
      return request(`/places/${seg(placeId)}/checkins`, { ...auth, method: 'DELETE', signal })
    },
    startGeneration(tripId, budgetPreset, idempotencyKey, { signal } = {}) {
      return request(`/trips/${seg(tripId)}/plan-generations`, {
        ...auth,
        method: 'POST',
        body: { budget_preset: budgetPreset },
        headers: { 'Idempotency-Key': idempotencyKey },
        signal,
      })
    },
    getGeneration(generationId, { signal } = {}) {
      return request(`/plan-generations/${seg(generationId)}`, { ...auth, signal })
    },
    getPlan(planId, { signal } = {}) {
      return request(`/plans/${seg(planId)}`, { ...auth, signal })
    },
    acceptPlan(planId, revision, { signal } = {}) {
      return request(`/plans/${seg(planId)}/accept`, { ...auth, method: 'POST', body: { revision }, signal })
    },
  }
}

export function newIdempotencyKey(): string {
  // randomUUID only exists in secure contexts; a LAN dev URL over plain HTTP lacks it.
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('')
}
