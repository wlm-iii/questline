import type { Stop } from '../../demo/types'

export type ImportChatDialogProps = {
  transcript: string
  matches: Stop[]
  onTranscriptChange: (text: string) => void
  onImport: (text: string) => void
}
export function ImportChatDialog({
  transcript,
  matches,
  onTranscriptChange,
  onImport,
}: ImportChatDialogProps) {
  return (
    <>
      <span className="eyebrow">FROM CHAT TO ADVENTURE</span>
      <h2>Bring the conversation along.</h2>
      <p>
        Paste your chat. This local demo can match names of the five sample
        places; new places can be added manually.
      </p>
      <textarea
        autoFocus
        value={transcript}
        onChange={(e) => onTranscriptChange(e.target.value)}
        placeholder={
          'Alex: We should go to Tartine Bakery!\nMorgan: Mission Dolores Park after?'
        }
      />
      <div className="import-preview">
        <strong>
          {transcript.split('\n').filter((l) => l.trim()).length} messages ·{' '}
          {matches.length} sample places matched
        </strong>
        {matches.map((s) => (
          <span key={s.id}>✓ {s.name}</span>
        ))}
      </div>
      <button
        className="primary"
        disabled={!transcript.trim()}
        onClick={() => onImport(transcript)}
      >
        Add matched places →
      </button>
    </>
  )
}
