import { useEffect } from 'react'

export default function Modal({ open, onClose, children, size = 'default' }) {
  useEffect(() => {
    if (!open) return
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  if (!open) return null

  const sizeClass = size === 'large' ? 'max-w-4xl' : 'max-w-[420px]'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
      onClick={onClose}
    >
      <div
        className={`bg-bg border border-muted rounded-card p-6 w-full ${sizeClass}`}
        onClick={e => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}