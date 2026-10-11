import { useEffect, useRef, type ReactNode } from 'react'

export type DialogHostProps = { open: boolean; onClose: () => void; children: ReactNode }

export function DialogHost({ open, onClose, children }: DialogHostProps) {
 const dialogRef = useRef<HTMLDialogElement>(null)
 useEffect(() => {
  if (open) dialogRef.current?.showModal()
  else dialogRef.current?.close()
 }, [open])
 return <dialog ref={dialogRef} className="full-dialog" onCancel={onClose} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
  <div className="dialog-content"><button className="modal-close" aria-label="Close dialog" onClick={onClose}>×</button>{children}</div>
 </dialog>
}
