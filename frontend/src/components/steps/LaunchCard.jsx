import {useEffect, useState, useRef } from 'react'
import ProcessingView from './ProcessingView'
import { useEventStream } from '../../hooks/useEventStream'
import { api } from '../../lib/api'


const fieldLabel = "font-mono font-semibold text-[10.5px] uppercase tracking-wider text-muted"
const fieldInput = "w-full bg-surface border border-muted rounded-control px-3 py-2.5 font-mono text-[13px] text-fg placeholder-muted/60 focus:outline-none focus:border-accent transition-colors disabled:opacity-50"

const MAX_FILE_MB = 25
const MAX_ROWS = 100_000
const MAX_COLUMNS = 50
// rebuildContext (optional): { name, comment, hint, mode }
// When present: dropzone/name/comment are disabled (no re-upload), mode +
// hint stay editable, and submitting re-infers/rebuilds on the existing
// dataset instead of launching a new one.
export default function LaunchCard({ dasher, onDone, rebuildContext, user, onProcessingChange }) { {
  const { applyLaunchEvents, applyAgentEvents, inferSemantics, generatePlan, createDashboard, datasetId, agentResult } = dasher
  const isRebuild = Boolean(rebuildContext)

  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [name, setName] = useState(rebuildContext?.name ?? '')
  const [comment, setComment] = useState(rebuildContext?.comment ?? '')
  const [mode, setMode] = useState(rebuildContext?.mode ?? 'pipeline')
  // const [hint, setHint] = useState(rebuildContext?.hint ?? '')
  const [pipelineHint, setPipelineHint] = useState(rebuildContext?.pipelineHint ?? '')
  const [agentGoal, setAgentGoal] = useState(rebuildContext?.agentGoal ?? '')
  const hint = mode === 'pipeline' ? pipelineHint : agentGoal
  const setHint = mode === 'pipeline' ? setPipelineHint : setAgentGoal

  

  const [localError, setLocalError] = useState(null)
  const [showProcessing, setShowProcessing] = useState(false)
  const [rebuilding, setRebuilding] = useState(false) // pipeline rebuild: no SSE, simple busy state
  const inputRef = useRef(null)

  const { events, streaming, streamError, startStream, reset } = useEventStream()
  const maxFileMb = user?.is_privileged ? MAX_FILE_MB * 4 : MAX_FILE_MB

  useEffect(() => {
    onProcessingChange?.(showProcessing)
  }, [showProcessing]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!showProcessing) return
    const handler = (e) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [showProcessing])

  function handleDrop(e) {
    e.preventDefault()
    setDragging(false)
    if (isRebuild) return
    const dropped = e.dataTransfer.files[0]
    if (!dropped?.name.endsWith('.csv')) return
    if (dropped.size > maxFileMb * 1024 * 1024) {
      setLocalError(`File exceeds ${maxFileMb}MB limit`)
      return
    }
    setLocalError(null)
    setFile(dropped)
  }

  function handleFileChange(e) {
    if (isRebuild) return
    const picked = e.target.files[0]
    if (!picked) return
    if (picked.size > maxFileMb * 1024 * 1024) {
      setLocalError(`File exceeds ${maxFileMb}MB limit`)
      e.target.value = ''
      return
    }
    setLocalError(null)
    setFile(picked)
  }

  async function handleFreshLaunch() {
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
      const createdEvent = result.find(e => e.type === 'dataset_created')
      // console.log('DEBUG createdEvent:', createdEvent, 'full result:', result)
      applyLaunchEvents(result, mode, {
        name: name.trim() || null,
        comment: comment.trim() || null,
        original_filename: file.name,
      })
      
      onDone(createdEvent?.dataset_id)
    }
  }

  async function handlePipelineRebuild() {
    setLocalError(null)
    setRebuilding(true)
    try {
      await inferSemantics(pipelineHint.trim() || null, true)
      await generatePlan()
      await createDashboard()
      onDone()
    } catch (e) {
      setLocalError(e.message)
    } finally {
      setRebuilding(false)
    }
  }

  async function handleAgentRebuild() {
    setLocalError(null)
    reset()
    setShowProcessing(true)
    const isAgentMode = Boolean(agentResult)
    const submittedGoal = agentGoal.trim()
    const result = await startStream(
      api.agentStreamUrl(datasetId),
      { ...(submittedGoal ? { goal: submittedGoal } : {}), nudge: isAgentMode }
    )
    const errorEvent = result.find(e => e.type === 'phase_error')
    if (!errorEvent) {
      applyAgentEvents(result, isAgentMode, submittedGoal || null, datasetId)
      onDone()
    }
    // on error, ProcessingView shows its own terminal state; dismiss handlers
    // below just return to this form so the hint can be edited and retried
  }

  function handleLaunch() {
    if (!isRebuild) return handleFreshLaunch()
    if (mode === 'pipeline') return handlePipelineRebuild()
    return handleAgentRebuild()
  }

  // function handleCancel() {
  //   setShowProcessing(false)
  //   reset()
  // }

  function handleEditHint() {
    setShowProcessing(false)
    reset()
  }

  function handleUploadDifferent() {
    setShowProcessing(false)
    if (!isRebuild) setFile(null)
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
        // onCancel={handleCancel}
        onEditHint={handleEditHint}
        onUploadDifferent={handleUploadDifferent}
      />
    )
  }

  const canSubmit = isRebuild ? !rebuilding : Boolean(file)

  return (
    <div className="animate-fade-in max-w-xl w-full mx-auto bg-surface border border-muted rounded-card p-7">
      <h1 className="font-display font-semibold text-[15px] text-fg mb-1">
        {isRebuild ? 'Rebuild Dashboard' : 'Launch Dashboard'}
      </h1>
      <p className="font-mono text-[12px] text-muted leading-relaxed mb-6">
        {isRebuild
          ? 'Adjust build mode or steering hint, then rebuild on this dataset.'
          : 'Upload a CSV — Dasher profiles it, infers semantics, and builds the dashboard in one run.'}
      </p>

      <div
        onClick={() => !isRebuild && inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); if (!isRebuild) setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`relative rounded-card border border-dashed px-8 py-10 flex flex-col items-center justify-center gap-2 transition-colors duration-150 ${
          isRebuild
            ? 'border-muted bg-bg opacity-50 cursor-not-allowed'
            : dragging ? 'border-accent bg-accent-wash-soft cursor-pointer' : 'border-muted bg-bg hover:border-accent/50 cursor-pointer'
        }`}
      >
        <input ref={inputRef} type="file" accept=".csv" onChange={handleFileChange} disabled={isRebuild} className="hidden" />
        <div className="text-2xl text-muted">↑</div>
        <div className="font-mono text-[12px] tracking-wide text-fg">
          {isRebuild ? (rebuildContext.name || rebuildContext.comment ? 'Existing dataset' : 'Existing dataset') : (file ? file.name : 'Drop CSV here or click to browse')}
        </div>
        {!isRebuild && file && (
          <div className="font-mono text-[11px] text-muted">
            {(file.size / 1024).toFixed(1)} KB
          </div>
        )}
      </div>
      {!isRebuild && (
        <div className="mt-2 font-mono text-[11px] text-muted">
          Max {MAX_FILE_MB}MB · {MAX_ROWS.toLocaleString()} rows · {MAX_COLUMNS} columns
        </div>
      )}

      <div className="mt-5 grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className={fieldLabel}>Name <span className="normal-case tracking-normal opacity-70">(optional)</span></label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Dashboard name"
            disabled={isRebuild}
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
            disabled={isRebuild}
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
          disabled={!canSubmit}
          className="px-6 py-2.5 rounded-control font-display text-[12.5px] font-semibold uppercase tracking-wide transition-opacity duration-150 disabled:opacity-40 disabled:cursor-not-allowed enabled:bg-accent enabled:text-accent-fg enabled:cursor-pointer"
        >
          {isRebuild ? (rebuilding ? 'Rebuilding…' : 'Rebuild Dashboard') : 'Launch Dashboard →'}
        </button>
        {isRebuild && (
          <button
            onClick={onDone}
            disabled={rebuilding}
            className="px-6 py-2.5 rounded-control font-display text-[12.5px] font-semibold uppercase tracking-wide text-muted hover:text-fg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  )
}}