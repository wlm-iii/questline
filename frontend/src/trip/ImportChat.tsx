import { useMemo, useState } from 'react'
import type { Uuid } from '../api'
import { useTrip } from '../state'
import { DialogHost } from '../components/dialogs/DialogHost'
import { importView, unresolvedMentions, type ImportView } from './adapters'
import { parseChat } from './chatParse'
import { errorMessage } from './errors'
import { useAddPlace } from './useAddPlace'
import { ImportChatForm } from './ui/ImportChatForm'

export type ImportChatProps = {
  open: boolean
  onClose: () => void
}

/** The "Import chat" sheet for a live trip. Renders its own DialogHost; must sit inside TripProvider. */
export function ImportChat({ open, onClose }: ImportChatProps) {
  const { session, snapshot, mutate } = useTrip()
  const { addPlace, pending: searching, error: searchError } = useAddPlace()
  const [text, setText] = useState('')
  const [started, setStarted] = useState<{ id: Uuid; messageCount: number } | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const preview = useMemo(() => parseChat(text), [text])

  const tracked = started && snapshot?.imports.find(item => item.id === started.id)
  const progress: ImportView | null = tracked
    ? importView(tracked)
    : started && importView({ id: started.id, trip_id: session.tripId, source: 'paste', status: 'queued', message_count: started.messageCount, error: null })
  const unresolved = started && snapshot && progress?.status === 'succeeded' ? unresolvedMentions(snapshot, started.id) : []

  async function startImport() {
    setPending(true)
    setError(null)
    try {
      const result = await mutate(api => api.importChat(session.tripId, text))
      setStarted({ id: result.import_id, messageCount: result.message_count })
      setText('')
    } catch (failure) {
      setError(errorMessage(failure, { import_too_large: 'That chat is too long to import. Paste a shorter part of it.' }))
    } finally {
      setPending(false)
    }
  }

  function close() {
    if (progress && !progress.active) setStarted(null)
    onClose()
  }

  return (
    <DialogHost open={open} onClose={close}>
      <ImportChatForm
        text={text}
        preview={preview}
        pending={pending}
        error={error}
        progress={progress}
        unresolved={unresolved}
        searching={searching}
        searchError={searchError}
        onTextChange={setText}
        onImport={startImport}
        onSearch={query => void addPlace(query)}
        onDone={close}
      />
    </DialogHost>
  )
}
