import { createContext, useContext } from 'react'

export const ToastContext = createContext(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx.toast
}

export function useToastList() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToastList must be used within ToastProvider')
  return { toasts: ctx.toasts, dismiss: ctx.dismiss }
}