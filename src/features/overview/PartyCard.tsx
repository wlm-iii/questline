export function PartyCard() {
  return (
    <article className="overview-card">
      <div className="section-title">
        <h3>Your party</h3>
        <span>4 adventurers</span>
      </div>
      {[
        ['JS', 'Jerry', 'Trip organizer'],
        ['AL', 'Alex', 'Coffee & pastry enthusiast'],
        ['MK', 'Morgan', 'Taking the scenic route'],
        ['SL', 'Sam', 'Here for the food'],
      ].map(([initials, name, role]) => (
        <div className="crew-row" key={name}>
          <span className="avatar">{initials}</span>
          <div>
            <strong>{name}</strong>
            <p>{role}</p>
          </div>
          <span className="crew-tag">Ready to explore</span>
        </div>
      ))}
    </article>
  )
}
