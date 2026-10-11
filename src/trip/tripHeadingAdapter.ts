import type { IsoDate, Member, TripSnapshot, Uuid } from '../api'
import type { TripHeadingMember } from '../components/TripHeading'

export type TripCrewMember = TripHeadingMember & { isMe: boolean }

export type TripHeadingView = {
  name: string
  destination: string
  dateLabel: string
  /** This browser's member first, then everyone else in the order the server lists them. */
  members: TripCrewMember[]
}

export function tripHeadingFromSnapshot(snapshot: TripSnapshot, myMemberId: Uuid): TripHeadingView {
  const { trip } = snapshot
  const members = snapshot.members
    .map((member) => toCrewMember(member, myMemberId))
    .sort((a, b) => Number(b.isMe) - Number(a.isMe))
  return {
    name: trip.name,
    destination: trip.destination?.label ?? 'Destination to be decided',
    dateLabel: formatTripDates(trip.start_date, trip.end_date),
    members,
  }
}

export function formatTripDates(start: IsoDate | null, end: IsoDate | null): string {
  const first = parseIsoDate(start)
  if (first === null) return 'Dates to be decided'
  const last = parseIsoDate(end)
  const format = new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC' })
  if (last === null || last <= first) return format.format(first)
  const short = new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' })
  return short.formatRange(first, last)
}

export function initialsFor(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  const letters = words.length === 1
    ? Array.from(words[0]).slice(0, 2)
    : [Array.from(words[0])[0], Array.from(words[words.length - 1])[0]]
  return letters.join('').toUpperCase()
}

function toCrewMember(member: Member, myMemberId: Uuid): TripCrewMember {
  return { id: member.id, name: member.name, initials: initialsFor(member.name), isMe: member.id === myMemberId }
}

function parseIsoDate(value: IsoDate | null): number | null {
  const match = value ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(value) : null
  return match ? Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null
}
