import type { StopView } from '../adapters'

export type PlaceDetailsProps = { stop: StopView; owner: string }

const statusLabel = { main: 'MAIN QUEST', side: 'SIDE QUEST', candidate: 'NOT IN QUESTLINE' }

export function PlaceDetails({ stop, owner }: PlaceDetailsProps) {
  return (
    <>
      <span className="eyebrow">
        {stop.categoryLabel.toUpperCase()} · {statusLabel[stop.status]}
      </span>
      <h2>{stop.name}</h2>
      <p>{stop.address}</p>
      <div className="detail-stats">
        <span>{stop.cost}</span>
        <span>{stop.hours}</span>
        {stop.arrive && <span>Arrive {stop.arrive}</span>}
        {stop.detour && <span>{stop.detour}</span>}
        <span>{stop.sourceLabel}</span>
        {stop.done && <span>✓ Quest complete</span>}
      </div>
      {stop.why && (
        <p>
          <strong>Why it's here:</strong> {stop.why}
        </p>
      )}
      <p>Owner: {owner}</p>
      <div className="import-preview">
        <strong>From the chat</strong>
        {stop.quotes.length === 0 && (
          <span>{stop.mentionedBy ? `Mentioned by ${stop.mentionedBy}. No quote is linked yet.` : 'No chat quotes for this place.'}</span>
        )}
        {stop.quotes.map(quote => (
          <span key={quote.id} style={{ whiteSpace: 'pre-line' }}>
            “{quote.text}” — {quote.author}
          </span>
        ))}
      </div>
      <p className="saved-hint">
        Place details from Google Maps.{' '}
        {stop.googleMapsUri && (
          <a href={stop.googleMapsUri} target="_blank" rel="noreferrer">
            Open in Google Maps ↗
          </a>
        )}
      </p>
    </>
  )
}
