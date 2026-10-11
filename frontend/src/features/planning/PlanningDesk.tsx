import type { ReactNode } from 'react'

export type PlanningDeskProps = {
  conversation: ReactNode
  route: ReactNode
  priorities: ReactNode
  constraints: ReactNode
  travel: ReactNode
  location: ReactNode
}
export function PlanningDesk({
  conversation,
  route,
  priorities,
  constraints,
  travel,
  location,
}: PlanningDeskProps) {
  return (
    <section className="planning-desk">
      <div className="desk-intro">
        <div>
          <span className="eyebrow">THE GROUP CHAT, WITH A PLAN</span>
          <h2>Gather your party. Chart your quest.</h2>
        </div>
        <span className="local-badge">Local planning workspace</span>
      </div>
      <div className="desk-grid">
        {conversation}
        <div className="desk-center">
          {route}
          {priorities}
        </div>
        <div className="desk-right">
          {constraints}
          {travel}
          {location}
        </div>
      </div>
    </section>
  )
}
