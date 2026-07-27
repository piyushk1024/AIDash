import { useState, useRef } from 'react'
import ProcessingView from './ProcessingView'
import { useEventStream } from '../../hooks/useEventStream'
import { api } from '../../lib/api'

const fieldLabel = "font-mono font-semibold text-[10.5px] uppercase tracking-wider text-muted"
const fieldInput = "w-full bg-surface border border-muted rounded-control px-3 py-2.5 font-mono text-[13px] text-fg placeholder-muted/60 focus:outline-none focus:border-accent transition-colors disabled:opacity-50"

export default function LaunchCard({ dasher, onDone }) {
  const { applyLaunchEvents } = dasher

  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [name, setName] = useState('')
  const [comment, setComment] = useState('')
  const [mode, setMode] = useState('pipeline')
  const [hint, setHint] = useState('')
  const [localError, setLocalError] = useState(null)
  const [showProcessing, setShowProcessing] = useState(false)
  const inputRef = useRef(null)

  const { events, streaming, streamError, startStream, reset } = useEventStream()

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

  async function handleLaunch() {
    if (!file) return
    setLocalError(null)
    reset()
    setShowProcessing(true)

    const formData = new FormData()
    formData.append('file', file)
    if (name.trim()) formData.append('name', name.trim())
    if (comment.trim()) formData.append('comment', comment.trim())
    formData.append('mode', mode)
    if (hint.trim()) formData.append('hint', hint.trim())

    const result = await startStream(api.launchStreamUrl(), formData)

    const hasFinish = result.some(e => e.type === 'finish')
    if (hasFinish) {
      applyLaunchEvents(result, mode)
      onDone()
    }
  }

  function handleCancel() {
    setShowProcessing(false)
    reset()
  }

  function handleEditHint() {
    setShowProcessing(false)
    reset()
  }

  function handleUploadDifferent() {
    setShowProcessing(false)
    setFile(null)
    reset()
  }

  if (showProcessing) {
    return (
      <ProcessingView
        mode={mode}
        events={events}
        streaming={streaming}
        streamError={streamError}
        datasetLabel={name.trim() || file?.name}
        onCancel={handleCancel}
        onEditHint={handleEditHint}
        onUploadDifferent={handleUploadDifferent}
      />
    )
  }

  return (
    <div className="animate-fade-in max-w-xl w-full mx-auto bg-surface border border-muted rounded-card p-7">
      <h1 className="font-display font-semibold text-[15px] text-fg mb-1">Launch Dashboard</h1>
      <p className="font-mono text-[12px] text-muted leading-relaxed mb-6">
        Upload a CSV — Dasher profiles it, infers semantics, and builds the dashboard in one run.
      </p>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`relative cursor-pointer rounded-card border border-dashed px-8 py-10 flex flex-col items-center justify-center gap-2 transition-colors duration-150 ${dragging ? 'border-accent bg-accent-wash-soft' : 'border-muted bg-bg hover:border-accent/50'}`}
      >
        <input ref={inputRef} type="file" accept=".csv" onChange={handleFileChange} className="hidden" />
        <div className="text-2xl text-muted">↑</div>
        <div className="font-mono text-[12px] tracking-wide text-fg">
          {file ? file.name : 'Drop CSV here or click to browse'}
        </div>
        {file && (
          <div className="font-mono text-[11px] text-muted">
            {(file.size / 1024).toFixed(1)} KB
          </div>
        )}
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className={fieldLabel}>Name <span className="normal-case tracking-normal opacity-70">(optional)</span></label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Dashboard name"
            className={fieldInput}
          />
        </div>
        <div className="space-y-1.5">
          <label className={fieldLabel}>Comment <span className="normal-case tracking-normal opacity-70">(optional)</span></label>
          <input
            type="text"
            value={comment}
            onChange={e => setComment(e.target.value)}
            placeholder="Notes about this dataset"
            className={fieldInput}
          />
        </div>
      </div>

      <div className="mt-5 space-y-1.5">
        <label className={fieldLabel}>Build mode</label>
        <div className="flex items-center gap-[3px] p-[3px] border border-muted rounded-control bg-bg w-fit">
          <button
            onClick={() => setMode('pipeline')}
            className={`px-3 py-1.5 rounded-icon font-display text-[12px] font-medium uppercase tracking-wide transition-colors ${mode === 'pipeline' ? 'bg-accent text-accent-fg font-semibold' : 'text-muted hover:text-fg'}`}
          >
            Standard
          </button>
          <button
            onClick={() => setMode('agent')}
            className={`px-3 py-1.5 rounded-icon font-display text-[12px] font-medium uppercase tracking-wide transition-colors ${mode === 'agent' ? 'bg-accent text-accent-fg font-semibold' : 'text-muted hover:text-fg'}`}
          >
            Agent
          </button>
        </div>
        <p className="font-mono text-[11px] text-muted">
          {mode === 'pipeline'
            ? 'Plans and builds charts in one deterministic pass.'
            : 'Goal-directed agent inspects the data and decides what to build.'}
        </p>
      </div>

      <div className="mt-5 space-y-1.5">
        <label className={fieldLabel}>
          {mode === 'pipeline' ? 'Business hint' : 'Goal'} <span className="normal-case tracking-normal opacity-70">(optional)</span>
        </label>
        <textarea
          value={hint}
          onChange={e => setHint(e.target.value)}
          placeholder={mode === 'pipeline'
            ? 'e.g. This is retail sales data, focus on revenue trends'
            : 'e.g. Build a dashboard for C-suite executives focusing on top-line revenue and regional performance'}
          rows={3}
          className={`${fieldInput} resize-none`}
        />
      </div>

      {localError && (
        <div className="mt-4 font-mono text-[12px] text-danger">✕ {localError}</div>
      )}

      <div className="mt-6">
        <button
          onClick={handleLaunch}
          disabled={!file}
          className="px-6 py-2.5 rounded-control font-display text-[12.5px] font-semibold uppercase tracking-wide transition-opacity duration-150 disabled:opacity-40 disabled:cursor-not-allowed enabled:bg-accent enabled:text-accent-fg enabled:cursor-pointer"
        >
          Launch Dashboard →
        </button>
      </div>
    </div>
  )
}