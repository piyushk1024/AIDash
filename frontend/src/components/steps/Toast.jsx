import { useCallback, useRef, useState } from 'react'
import { ToastContext, useToastList } from '../../hooks/useToast'

let nextId = 1

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef({})

  const dismiss = useCallback((id) => {
    setToasts(t => t.filter(x => x.id !== id))
    clearTimeout(timers.current[id])
    delete timers.current[id]
  }, [])

  const push = useCallback((message, variant = 'info', duration = 4000) => {
    const id = nextId++
    setToasts(t => [...t, { id, message, variant }])
    timers.current[id] = setTimeout(() => dismiss(id), duration)
    return id
  }, [dismiss])

  const toast = {
    show: push,
    success: (msg, duration) => push(msg, 'success', duration),
    error: (msg, duration) => push(msg, 'error', duration),
    info: (msg, duration) => push(msg, 'info', duration),
  }

  return (
    <ToastContext.Provider value={{ toasts, toast, dismiss }}>
      {children}
    </ToastContext.Provider>
  )
}

const VARIANT_STYLE = {
  success: 'border-accent bg-accent text-accent-fg',
  error: 'border-danger bg-danger text-white',
  info: 'border-muted bg-bg text-fg',
}

const VARIANT_ICON = {
  success: 'Success: ',
  error: 'Error: ',
  info: 'Info: ',
}

export default function Toast() {
  const { toasts, dismiss } = useToastList()

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-[360px]">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`flex items-start gap-2.5 border rounded-control px-3.5 py-2.5 font-mono text-xs shadow-lg ${VARIANT_STYLE[t.variant] ?? VARIANT_STYLE.info}`}
        >
          <span className="flex-1 leading-relaxed">{VARIANT_ICON[t.variant] ?? VARIANT_ICON.info}{t.message}</span>
          <button
            onClick={() => dismiss(t.id)}
            className="shrink-0 text-white/70 hover:text-white transition-colors"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}