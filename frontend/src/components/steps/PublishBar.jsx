export default function PublishBar({ published, publishing, onPublish, copyLabel, onCopy }) {
  return (
    <div className="flex items-center gap-3 py-2 border-t border-neutral-800">
      <button
        onClick={onPublish}
        disabled={publishing}
        className={`px-3 py-1.5 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200 disabled:opacity-50
          ${published
            ? 'border border-amber-400/40 text-amber-400 hover:bg-amber-400/10'
            : 'bg-amber-400 text-neutral-950 hover:bg-amber-300'
          }`}
      >
        {publishing ? '...' : published ? 'Unpublish' : 'Publish'}
      </button>

      {published && (
        <button
          onClick={onCopy}
          className="font-mono text-xs text-neutral-500 hover:text-amber-400 transition-colors"
        >
          {copyLabel}
        </button>
      )}

      {published && (
        <span className="font-mono text-xs text-neutral-600 ml-auto">
          Public link active
        </span>
      )}
    </div>
  )
}