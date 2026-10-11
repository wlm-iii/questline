// Pure snapshot → view-model logic for the live Overview and Planning desk. No React, no fetch.
import type { Plan, TripSnapshot, VoteKind } from '../api'
import type { Tier } from '../components/tiers'
import type { RouteGraphStop } from '../features/planning/RouteGraph'
import { planStops, voteKinds, voteLabels, type StopView } from './adapters'

/** A tier is a vote: S/A I'm in, B/C Sure, D–F Skip. */
export const tierVote: Record<Tier, VoteKind> = { S: 'in', A: 'in', B: 'ok', C: 'ok', D: 'out', E: 'out', F: 'out' }
/** Where a vote shows when this device has no matching tier. */
export const voteTier: Record<VoteKind, Tier> = { in: 'A', ok: 'C', out: 'E' }

/** The viewer's tiers: their saved tier when it still matches their vote, else the vote's default. Unvoted places are unranked. */
export function displayedTiers(stops: StopView[], saved: Partial<Record<string, Tier>>): Partial<Record<string, Tier>> {
  const ranks: Partial<Record<string, Tier>> = {}
  for (const stop of stops) {
    if (!stop.myVote) continue
    const local = saved[stop.id]
    ranks[stop.id] = local && tierVote[local] === stop.myVote ? local : voteTier[stop.myVote]
  }
  return ranks
}

/** The vote to send for a new tier, or null when it already is the viewer's vote (the API toggles). */
export function voteForRank(current: VoteKind | null, tier: Tier): VoteKind | null {
  const next = tierVote[tier]
  return next === current ? null : next
}

/** The viewer's vote after sending `sent`: the API toggles, so the current kind clears it. */
export function afterVote(current: VoteKind | null, sent: VoteKind): VoteKind | null {
  return current === sent ? null : sent
}

/** Stops with the viewer's in-flight votes applied, so repeated actions compute against them. */
export function withPendingVotes(stops: StopView[], pending: Partial<Record<string, VoteKind | null>>): StopView[] {
  return stops.map(stop => (stop.id in pending ? { ...stop, myVote: pending[stop.id] ?? null } : stop))
}

export const voteChoices: string[] = voteKinds.map(kind => voteLabels[kind])

export function kindForChoice(choice: string): VoteKind | null {
  return voteKinds.find(kind => voteLabels[kind] === choice) ?? null
}

/** place id → member name → vote label, for the tier list's Party votes section. */
export function partyVotes(stops: StopView[]): Record<string, Record<string, string>> {
  return Object.fromEntries(
    stops.map(stop => [
      stop.id,
      Object.fromEntries(voteKinds.flatMap(kind => stop.votes[kind].map(name => [name, voteLabels[kind]]))),
    ]),
  )
}

/** Total main-route distance and drive time, or null before a plan exists. */
export function routeTotals(plan: Plan | null): { miles: number; minutes: number } | null {
  const legs = plan?.content?.graph?.edges.filter(edge => edge.kind === 'travel') ?? []
  if (legs.length === 0) return null
  const meters = legs.reduce((sum, leg) => sum + (leg.distance_m ?? 0), 0)
  const minutes = legs.reduce((sum, leg) => sum + (leg.drive_min ?? 0), 0)
  return { miles: Math.round(meters / 1609.344), minutes: Math.round(minutes) }
}

/** The plan's quests in travel order for RouteGraph; side quests keep their anchor. */
export function graphStops(plan: Plan | null, stops: StopView[]): RouteGraphStop<string>[] {
  const nodes = planStops(plan)
  if (!nodes) return []
  const byId = new Map(stops.map(stop => [stop.id, stop]))
  const main = nodes.main.flatMap(node => {
    const stop = byId.get(node.id)
    return stop ? [{ id: stop.id, name: stop.name, side: false, time: stop.arrive ?? '' }] : []
  })
  const side = nodes.side.flatMap(node => {
    const stop = byId.get(node.id)
    return stop
      ? [{ id: stop.id, name: stop.name, side: true, time: '', anchorId: node.anchor, branchNote: stop.detour ?? 'detour unknown' }]
      : []
  })
  return [...main, ...side]
}

export type ConversationLine = { id: string; author: string; initial: string; text: string }

/** Messages oldest first, attributed to member names when known. */
export function conversationLines(snapshot: TripSnapshot): ConversationLine[] {
  const names = new Map(snapshot.members.map(member => [member.id, member.name]))
  return [...snapshot.messages]
    .sort((a, b) => a.sent_at.localeCompare(b.sent_at))
    .map(message => {
      const author = (message.member_id && names.get(message.member_id)) || message.author_id
      return { id: message.id, author, initial: author.slice(0, 1).toUpperCase(), text: message.text }
    })
}
