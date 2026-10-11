import type { ReactNode } from 'react'

export type OverviewProps = {
  hero: ReactNode
  stats: ReactNode
  party: ReactNode
  preparation: ReactNode
}
export function Overview({ hero, stats, party, preparation }: OverviewProps) {
  return (
    <section className="overview">
      {hero}
      {stats}
      <div className="overview-grid">
        {party}
        {preparation}
      </div>
    </section>
  )
}
