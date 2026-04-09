import { useState, useRef } from 'react'

export default function UploadStep({ dasher, isActive, isExpanded, onToggle }) {
  const { upload, status, errors, uploadResult } = dasher

  const [file, setFile] = useState(null)
  const [hint, setHint] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const isLoading = status.upload === 'loading'
  const isDone    = status.upload === 'done'

  // ── If step is done, show a compact summary instead of the form ──
  if (isDone && uploadResult) {
    return (
      <div className="animate-fade-in">
        {/* Collapsed summary line — always visible when done */}
        <button
          onClick={onToggle}
          className="w-full py-2 flex items-center gap-3 font-mono text-xs hover:opacity-80 transition-opacity text-left"
        >
          <span className="text-neutral-500 uppercase tracking-wider">Upload Dataset</span>
          <span className="text-neutral-600">—</span>
          <span className="text-neutral-400">{uploadResult.original_filename}</span>
          <span className="text-neutral-600">{uploadResult.row_count} rows</span>
          <span className="text-amber-400 ml-auto">✓</span>
          {/* Chevron rotates when expanded */}
          <span className={`text-neutral-600 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
            ▾
          </span>
        </button>

        {/* Expanded detail — only shown when toggled open */}
        {isExpanded && (
          <div className="animate-fade-in mb-4 p-4 border border-neutral-800 rounded font-mono text-xs space-y-1">
            <Row label="file"    value={uploadResult.original_filename} />
            <Row label="rows"    value={uploadResult.row_count} />
            <Row label="table"   value={uploadResult.table_name} />
            <Row label="dataset" value={uploadResult.dataset_id} />
          </div>
        )}
      </div>
    )
  }

  // ── Not active yet — show nothing ──
  if (!isActive) return null

  // ── Drag and drop handlers ──
  function handleDrop(e) {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped?.name.endsWith('.csv')) setFile(dropped)
  }

  function handleFileChange(e) {
    const picked = e.target.files[0]
    if (picked) setFile(picked)
  }

  function handleSubmit() {
    if (!file) return
    upload(file, hint || null)
  }

  return (
    <div className="animate-fade-in">
      <StepHeader title="Upload Dataset" />

      {/* Hint input */}
      <div className="mt-6 mb-4">
        <label className="font-mono text-xs text-neutral-500 dark:text-neutral-400 tracking-wider uppercase block mb-2">
          Business context <span className="text-neutral-400">(optional)</span>
        </label>
        <input
          type="text"
          value={hint}
          onChange={e => setHint(e.target.value)}
          placeholder="e.g. retail mall operations, daily footfall tracking"
          className="w-full bg-transparent border border-neutral-300 dark:border-neutral-700 rounded px-3 py-2 font-mono text-sm text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:border-amber-400 transition-colors"
        />
      </div>

      {/* Drop zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`
          relative cursor-pointer rounded border-2 border-dashed px-8 py-12
          flex flex-col items-center justify-center gap-3 transition-all duration-200
          ${dragging
            ? 'border-amber-400 bg-amber-400/5'
            : 'border-neutral-300 dark:border-neutral-700 hover:border-neutral-400 dark:hover:border-neutral-500'
          }
        `}
      >
        {/* Hidden real file input — triggered by clicking the drop zone */}
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          onChange={handleFileChange}
          className="hidden"
        />

        <div className="font-mono text-xs tracking-wider uppercase text-neutral-400">
          {file ? file.name : 'Drop CSV here or click to browse'}
        </div>

        {file && (
          <div className="font-mono text-xs text-neutral-500">
            {(file.size / 1024).toFixed(1)} KB
          </div>
        )}
      </div>

      {/* Error */}
      {errors.upload && (
        <div className="mt-3 font-mono text-xs text-red-400">
          ✕ {errors.upload}
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={!file || isLoading}

        className={`
          mt-4 px-6 py-2 rounded font-mono text-xs tracking-widest uppercase
          transition-all duration-200
          disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed
          enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer
      `}
      >
        {isLoading ? 'Uploading...' : 'Upload →'}
      </button>

      {/* Loading status line */}
      {isLoading && (
        <div className="mt-3 font-mono text-xs text-neutral-500 animate-pulse">
          Loading CSV into Postgres, syncing Metabase...
        </div>
      )}
    </div>
  )
}

// ── Small reusable pieces ─────────────────────────────────────

// Step header — shows title + optional done checkmark
function StepHeader({ title, done }) {
  return (
    <div className="flex items-center gap-3 mb-2">
      <h2 className="font-mono text-sm tracking-widest uppercase text-neutral-900 dark:text-neutral-100">
        {title}
      </h2>
      {done && (
        <span className="font-mono text-xs text-amber-400">✓ done</span>
      )}
    </div>
  )
}

// Key/value row for the done summary
function Row({ label, value }) {
  return (
    <div className="flex gap-4">
      <span className="text-neutral-500 w-16 shrink-0">{label}</span>
      <span className="text-neutral-300 break-all">{value}</span>
    </div>
  )
}