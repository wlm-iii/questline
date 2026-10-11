export function LocationCard() {
  return (
    <article className="desk-card location-card">
      <span className="location-icon">⌖</span>
      <h3>Find your crew</h3>
      <p>Keep everyone together on the day.</p>
      <span className="connection-status">Location sharing not connected</span>
      <p className="desk-footnote">
        Apple location and Life360 are future integrations. No location data is
        collected.
      </p>
    </article>
  )
}
