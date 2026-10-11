import type { ConversationLine } from '../deskAdapters'

export type TripConversationProps = {
  lines: ConversationLine[]
  stops: { id: string; name: string }[]
  onImport: () => void
  onSelectPlace: (id: string) => void
}

/** The trip's real messages in the demo's conversation panel. Read-only. */
export function TripConversation({ lines, stops, onImport, onSelectPlace }: TripConversationProps) {
  return (
    <article className="desk-card chat-reader">
      <div className="section-title">
        <h3>Party conversation</h3>
        <span>From your group chat</span>
      </div>
      <p className="desk-copy">
        Messages from your linked iMessage group and pasted chats. Places they mention land on the map.
      </p>
      <button className="primary" onClick={onImport}>
        ＋ Import chat
      </button>
      <div className="conversation-stream">
        {lines.length === 0 ? (
          <div className="desk-empty">
            Your group’s ideas will appear here.
            <br />
            Link iMessage or import a chat to get started.
          </div>
        ) : (
          lines.map(line => (
            <div className="message" key={line.id}>
              <span className="message-avatar">{line.initial}</span>
              <div>
                <strong>{line.author}</strong>
                <p>{line.text}</p>
                {stops
                  .filter(stop => line.text.toLowerCase().includes(stop.name.toLowerCase()))
                  .map(stop => (
                    <button key={stop.id} onClick={() => onSelectPlace(stop.id)}>
                      ⌖ {stop.name} ↗
                    </button>
                  ))}
              </div>
            </div>
          ))
        )}
      </div>
    </article>
  )
}
