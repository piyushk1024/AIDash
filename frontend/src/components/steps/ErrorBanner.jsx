export default function ErrorBanner({ message }) {
  if (!message) return null

  return (
    <div className="flex items-center gap-2.5 border border-danger rounded-control bg-danger/10 px-3.5 py-2.5">
      <div className="w-2 h-2 rounded-full bg-danger shrink-0" />
      <span className="font-mono text-xs text-fg">{message}</span>
    </div>
  )
}