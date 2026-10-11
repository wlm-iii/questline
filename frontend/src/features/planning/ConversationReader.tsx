import type { Stop } from '../../demo/types'

export type ConversationReaderProps = {
  stops: Stop[]
  messages: string[]
  chatDraft: string
  onDraftChange: (text: string) => void
  onReadConversation: (text: string) => void
  onSelectPlace: (id: number) => void
}
export function ConversationReader({
  stops,
  messages,
  chatDraft,
  onDraftChange,
  onReadConversation,
  onSelectPlace,
}: ConversationReaderProps) {
  return (
    <article className="desk-card chat-reader">
      <div className="section-title">
        <h3>Party conversation</h3>
        <span>Paste your group chat</span>
      </div>
      <p className="desk-copy">
        Keep the conversation visible while you plan. Messages are saved here;
        this does not send anything to your group.
      </p>
      <textarea
        aria-label="Group conversation"
        value={chatDraft}
        onChange={(e) => onDraftChange(e.target.value)}
        placeholder="Alex: Let's stop for coffee…"
      />
      <button
        className="primary"
        disabled={!chatDraft.trim()}
        onClick={() => onReadConversation(chatDraft)}
      >
        Read conversation →
      </button>
      <div className="conversation-stream">
        {messages.length === 0 ? (
          <div className="desk-empty">
            Your group’s ideas will appear here.
            <br />
            Paste a conversation to get started.
          </div>
        ) : (
          messages.map((m, i) => {
            const colon = m.indexOf(':')
            return (
              <div className="message" key={i}>
                <span className="message-avatar">
                  {colon > 0 ? m.slice(0, 1).toUpperCase() : '•'}
                </span>
                <div>
                  <strong>{colon > 0 ? m.slice(0, colon) : 'Message'}</strong>
                  <p>{colon > 0 ? m.slice(colon + 1) : m}</p>
                  {stops
                    .filter((stop) =>
                      m.toLowerCase().includes(stop.name.toLowerCase()),
                    )
                    .map((stop) => (
                      <button
                        key={stop.id}
                        onClick={() => onSelectPlace(stop.id)}
                      >
                        ⌖ {stop.name} ↗
                      </button>
                    ))}
                </div>
              </div>
            )
          })
        )}
      </div>
    </article>
  )
}
