export type NoticeProps = {
  message: string
  onDismiss: () => void
}
export function Notice({ message, onDismiss }: NoticeProps) {
  return (
    <div className="notice" role="status">
      {message}
      <button aria-label="Dismiss notification" onClick={onDismiss}>
        ×
      </button>
    </div>
  )
}
