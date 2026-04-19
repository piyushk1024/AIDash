import { useState, useRef } from 'react'

export default function UploadStep({ dasher, isActive, isExpanded, onToggle }) {
  const { upload, status, errors, uploadResult, conflict, resolveConflict  } = dasher

  const [file, setFile] = useState(null)
  const [hint, setHint] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const isLoading = status.upload === 'loading'
  const isDone    = status.upload === 'done'

  if (isDone && uploadResult) {
    return (
      <div className="animate-fade-in">
        <button
          onClick={onToggle}
          className="w-full px-4 py-3 flex items-center gap-3 font-mono text-xs text-left rounded border border-transparent hover:border-neutral-200 dark:hover:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-900 transition-all duration-150 cursor-pointer"
          title="Click to expand"
        >
          <span className="text-neutral-500 uppercase tracking-wider">Upload</span>
          <span className="text-neutral-300 dark:text-neutral-600">—</span>
          <span className="text-neutral-700 dark:text-neutral-300">{uploadResult.original_filename}</span>
          <span className="text-neutral-400">{uploadResult.row_count} rows</span>
          <span className="text-amber-400 ml-auto">✓</span>
          <span className={`text-neutral-400 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>▾</span>
        </button>

        {isExpanded && (
          <div className="animate-fade-in mx-1 mb-3 px-4 py-3 border border-neutral-200 dark:border-neutral-800 rounded-b font-mono text-xs space-y-1.5 bg-neutral-50 dark:bg-neutral-900/50">
            <Row label="file"    value={uploadResult.original_filename} />
            <Row label="rows"    value={uploadResult.row_count} />
            <Row label="table"   value={uploadResult.table_name} />
            <Row label="dataset" value={uploadResult.dataset_id} />
          </div>
        )}
      </div>
    )
  }

  if (!isActive) return null

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
    <div className="animate-fade-in mt-6">
      <div className="rounded-lg border border-amber-400/30 bg-amber-400/[0.02] dark:bg-amber-400/[0.03] px-6 py-5">
        <StepHeader title="Upload Dataset" />
        <p className="font-mono text-xs text-neutral-500 mt-1 mb-5">
          Upload a CSV to get started. Add a business hint to improve LLM inference.
        </p>

        <div className="mb-4">
          <label className="font-mono text-xs text-neutral-500 dark:text-neutral-400 tracking-wider uppercase block mb-2">
            Business context <span className="text-neutral-400 normal-case">(optional)</span>
          </label>
          <input
            type="text"
            value={hint}
            onChange={e => setHint(e.target.value)}
            placeholder="e.g. retail mall operations, daily footfall tracking"
            className="w-full bg-transparent border border-neutral-300 dark:border-neutral-700 rounded px-3 py-2 font-mono text-sm text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:border-amber-400 transition-colors"
          />
        </div>

        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`relative cursor-pointer rounded border-2 border-dashed px-8 py-10 flex flex-col items-center justify-center gap-2 transition-all duration-200 ${dragging ? 'border-amber-400 bg-amber-400/5' : 'border-neutral-300 dark:border-neutral-700 hover:border-amber-400/50 hover:bg-amber-400/[0.02]'}`}
        >
          <input ref={inputRef} type="file" accept=".csv" onChange={handleFileChange} className="hidden" />
          <div className="text-2xl text-neutral-300 dark:text-neutral-600">↑</div>
          <div className="font-mono text-xs tracking-wider uppercase text-neutral-400">
            {file ? file.name : 'Drop CSV here or click to browse'}
          </div>
          {file && (
            <div className="font-mono text-xs text-neutral-500">
              {(file.size / 1024).toFixed(1)} KB
            </div>
          )}
        </div>
        {/* Conflict resolution */}
{conflict && (
  <div className="mt-4 p-4 border border-amber-400/40 rounded font-mono text-xs space-y-3">
    <div className="text-amber-400">
      A dataset with this filename already exists.
    </div>
    <div className="flex gap-3">
      <button
        onClick={() => resolveConflict('replace')}
        className="px-4 py-2 bg-amber-400 text-neutral-950 rounded tracking-widest uppercase hover:bg-amber-300 transition-colors"
      >
        Replace
      </button>
      <button
        onClick={() => resolveConflict('new')}
        className="px-4 py-2 border border-neutral-600 text-neutral-400 rounded tracking-widest uppercase hover:border-neutral-400 transition-colors"
      >
        Create New
      </button>
    </div>
  </div>
)}

        {errors.upload && (
          <div className="mt-3 font-mono text-xs text-red-400">✕ {errors.upload}</div>
        )}

        <div className="mt-4 flex items-center gap-4">
          <button
            onClick={handleSubmit}
            disabled={!file || isLoading}
            className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200 disabled:bg-neutral-100 dark:disabled:bg-neutral-800 disabled:text-neutral-400 dark:disabled:text-neutral-600 disabled:cursor-not-allowed enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer enabled:shadow-sm"
          >
            {isLoading ? 'Uploading...' : 'Upload'}
          </button>
          {isLoading && (
            <span className="font-mono text-xs text-neutral-500 animate-pulse">
              Loading CSV into Postgres, syncing Metabase...
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function StepHeader({ title }) {
  return (
    <h2 className="font-mono text-sm tracking-widest uppercase text-neutral-900 dark:text-neutral-100 mb-1">
      {title}
    </h2>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex gap-4">
      <span className="text-neutral-500 w-16 shrink-0">{label}</span>
      <span className="text-neutral-700 dark:text-neutral-300 break-all">{value}</span>
    </div>
  )
}