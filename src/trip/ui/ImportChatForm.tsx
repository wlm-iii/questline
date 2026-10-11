import type { ImportView, UnresolvedMention } from '../adapters'
import type { ChatPreview } from '../chatParse'
import { ImportStatus } from './ImportStatus'

export type ImportChatFormProps = {
  text: string
  preview: ChatPreview
  pending: boolean
  error: string | null
  /** The import this sheet started, once the backend accepted it. */
  progress: ImportView | null
  unresolved: UnresolvedMention[]
  searching: string | null
  searchError: string | null
  onTextChange: (text: string) => void
  onImport: () => void
  onSearch: (text: string) => void
  onDone: () => void
}

const PREVIEW_LINES = 4

export function ImportChatForm({
  text,
  preview,
  pending,
  error,
  progress,
  unresolved,
  searching,
  searchError,
  onTextChange,
  onImport,
  onSearch,
  onDone,
}: ImportChatFormProps) {
  const count = preview.messages.length
  if (progress) {
    return (
      <>
        <span className="eyebrow">FROM CHAT TO ADVENTURE</span>
        <h2>{progress.active ? 'Reading the chat…' : progress.status === 'failed' ? 'That import failed.' : 'Chat imported.'}</h2>
        <p>The map stays usable while Questline reads. New places appear on it as soon as they're found.</p>
        <ImportStatus imports={[progress]} unresolved={unresolved} searching={searching} onSearch={onSearch} variant="dialog" />
        {searchError && <p role="alert">{searchError}</p>}
        <button className="primary" onClick={onDone}>
          {progress.active ? 'Keep reading in the background' : 'Done'}
        </button>
      </>
    )
  }
  return (
    <>
      <span className="eyebrow">FROM CHAT TO ADVENTURE</span>
      <h2>Bring the conversation along.</h2>
      <p>
        Paste the group chat, one message per line as <strong>Name: text</strong>. Questline finds the places people
        mention and shows each one with who said it. Places it can't find are listed, never invented.
      </p>
      <textarea
        autoFocus
        aria-label="Chat transcript"
        value={text}
        onChange={e => onTextChange(e.target.value)}
        placeholder={'Alex: We should go to Tartine Bakery!\nMorgan: Mission Dolores Park after?'}
      />
      <div className="import-preview" aria-live="polite">
        <strong>
          {count} message{count === 1 ? '' : 's'} from {preview.authors.length}{' '}
          {preview.authors.length === 1 ? 'person' : 'people'}
          {count > 0 && !preview.error ? ' · Looks right?' : ''}
        </strong>
        {preview.error && <span role="alert">{preview.error}</span>}
        {preview.messages.slice(0, PREVIEW_LINES).map((message, index) => (
          <span key={index}>
            {message.author}: {message.text}
          </span>
        ))}
        {count > PREVIEW_LINES && <span>…and {count - PREVIEW_LINES} more</span>}
      </div>
      {error && <p role="alert">{error}</p>}
      <button className="primary" disabled={pending || count === 0 || preview.error !== null} onClick={onImport}>
        {pending ? 'Importing…' : `Import ${count} message${count === 1 ? '' : 's'} →`}
      </button>
    </>
  )
}
