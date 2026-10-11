export type PartyMember = {
  id: string
  initials: string
  name: string
  role: string
  tag?: string
}

export type PartyCardProps = {
  /** Without it the card shows the demo crew. */
  members?: PartyMember[]
}

const demoCrew: PartyMember[] = [
  ['JS', 'Jerry', 'Trip organizer'],
  ['AL', 'Alex', 'Coffee & pastry enthusiast'],
  ['MK', 'Morgan', 'Taking the scenic route'],
  ['SL', 'Sam', 'Here for the food'],
].map(([initials, name, role]) => ({ id: name, initials, name, role, tag: 'Ready to explore' }))

export function PartyCard({ members }: PartyCardProps) {
  const crew = members ?? demoCrew
  return (
    <article className="overview-card">
      <div className="section-title">
        <h3>Your party</h3>
        <span>{members ? `${crew.length} ${crew.length === 1 ? 'adventurer' : 'adventurers'}` : '4 adventurers'}</span>
      </div>
      {crew.map(({ id, initials, name, role, tag }) => (
        <div className="crew-row" key={id}>
          <span className="avatar">{initials}</span>
          <div>
            <strong>{name}</strong>
            <p>{role}</p>
          </div>
          {tag && <span className="crew-tag">{tag}</span>}
        </div>
      ))}
    </article>
  )
}
