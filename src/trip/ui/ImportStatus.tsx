import type { ImportView, UnresolvedMention } from '../adapters'

export type ImportStatusProps = {
  imports: ImportView[]
  unresolved: UnresolvedMention[]
  /** The mention being searched, or null. */
  searching: string | null
  onSearch: (text: string) => void
  /** `board` fits the quest board; `dialog` fits the import sheet. */
  variant: 'board' | 'dialog'
}

export function ImportStatus({ imports, unresolved, searching, onSearch, variant }: ImportStatusProps) {
  const box = (failed: boolean) => (variant === 'dialog' ? 'import-preview' : failed ? 'inline-warning' : 'route-summary')
  return (
    <>
      {imports.map(item => (
        <div className={box(item.status === 'failed')} key={item.id} role="status">
          <strong>{item.status === 'failed' ? 'Import failed' : item.active ? 'Importing chat' : 'Import finished'}</strong>{' '}
          <span>{item.label}</span>
        </div>
      ))}
      {unresolved.length > 0 && (
        <div className={box(true)}>
          <strong>Couldn't place ({unresolved.length})</strong>
          {unresolved.map(mention => (
            <div key={mention.key}>
              “{mention.text}”{mention.quotes[0] && <> · {mention.quotes[0].author}</>}{' '}
              <button
                className="text-button"
                disabled={searching !== null}
                aria-label={`Search for ${mention.text}`}
                onClick={() => onSearch(mention.text)}
              >
                {searching === mention.text ? 'Searching…' : 'Search →'}
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
