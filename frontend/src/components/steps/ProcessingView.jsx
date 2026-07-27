import AgentTrace from './AgentTrace'

const STANDARD_PHASES = [
  { key: 'profile',   label: 'PROFILE' },
  { key: 'semantics', label: 'SEMANTICS' },
  { key: 'plan',      label: 'PLAN' },
  { key: 'build',     label: 'BUILD' },
]

function errorIcon() {
  return (
    <div className="relative w-11 h-11 mx-auto">
      <div className="w-11 h-11 rounded-full border-2 border-danger box-border" />
      <div className="absolute left-1/2 top-[11px] w-[3px] h-4 -ml-[1.5px] rounded bg-danger" />
      <div className="absolute left-1/2 top-[31px] w-1 h-1 -ml-[2px] rounded-full bg-danger" />
    </div>
  )
}

function dotClasses(status) {
  const base = 'w-[13px] h-[13px] rounded-full shrink-0 box-border'
  if (status === 'done')   return `${base} bg-accent border border-accent`
  if (status === 'active') return `${base} bg-transparent border-2 border-accent`
  if (status === 'error')  return `${base} bg-danger border border-danger`
  return `${base} bg-transparent border border-muted`
}

function labelClasses(status) {
  const base = 'font-display font-semibold text-[13px] tracking-wide'
  if (status === 'pending') return `${base} text-muted`
  if (status === 'error')   return `${base} text-danger`
  return `${base} text-fg`
}

function detailClasses(status) {
  return `font-mono text-xs leading-relaxed mt-1 block ${status === 'error' ? 'text-danger' : 'text-muted'}`
}

function lineClasses(status, isLast) {
  if (isLast) return 'w-px flex-1 mt-1 opacity-0'
  const color = status === 'done' ? 'bg-accent' : status === 'error' ? 'bg-danger' : 'bg-muted'
  const opacity = (status === 'done' || status === 'error') ? '' : 'opacity-40'
  return `w-px flex-1 mt-1 ${color} ${opacity}`
}

// Builds the 4 Standard-mode rows from raw SSE events.
function buildStandardSteps(events) {
  const phaseStarted = phase => events.some(e => e.type === 'step_started' && e.phase === phase)
  const phaseDone    = phase => events.find(e => e.type === 'step_done' && e.phase === phase)
  const finishEvent  = events.find(e => e.type === 'finish')
  const errorEvent   = events.find(e => e.type === 'phase_error')

  return STANDARD_PHASES.map(({ key, label }) => {
    const done = key === 'build' ? Boolean(finishEvent) : Boolean(phaseDone(key))
    const started = phaseStarted(key)
    let status = 'pending'
    if (done) status = 'done'
    else if (started) status = 'active'
    if (errorEvent && errorEvent.phase === key) status = 'error'

    let detail = ''
    if (key === 'profile' && phaseDone('profile')) {
      detail = `Scanned ${phaseDone('profile').profile?.columns?.length ?? '?'} columns.`
    } else if (key === 'semantics' && phaseDone('semantics')) {
      detail = 'Semantic roles inferred.'
    } else if (key === 'plan' && phaseDone('plan')) {
      const chartCount = phaseDone('plan').plan?.charts?.length
      detail = chartCount ? `Drafted ${chartCount} charts.` : 'Dashboard plan drafted.'
    } else if (key === 'build' && finishEvent) {
      detail = 'Charts built.'
    } else if (status === 'active') {
      detail = 'In progress…'
    } else if (status === 'error' && errorEvent) {
      detail = errorEvent.error
    }

    return { key, label, status, detail, time: '' }
  })
}

// Builds the 3 Agent-mode rows. Row 3 ("Agent Run") absorbs the whole
// tool-call loop and stays active until a top-level `finish` event arrives.
function buildAgentSteps(events) {
  const phaseStarted = phase => events.some(e => e.type === 'step_started' && e.phase === phase)
  const phaseDone    = phase => events.find(e => e.type === 'step_done' && e.phase === phase)
  const buildStarted = events.some(e => e.type === 'step_started' && e.phase === 'build')
  const finishEvent  = events.find(e => e.type === 'finish')
  const errorEvent   = events.find(e => e.type === 'phase_error')

  const rows = [
    { key: 'profile', label: 'PROFILE' },
    { key: 'semantics', label: 'SEMANTICS' },
    { key: 'agent_run', label: 'AGENT RUN' },
  ].map(({ key, label }) => {
    let status
    let detail = ''

    if (key === 'profile') {
      status = phaseDone('profile') ? 'done' : phaseStarted('profile') ? 'active' : 'pending'
      if (phaseDone('profile')) detail = 'CSV profiled.'
    } else if (key === 'semantics') {
      status = phaseDone('semantics') ? 'done' : phaseStarted('semantics') ? 'active' : 'pending'
      if (phaseDone('semantics')) detail = 'Semantic roles inferred.'
    } else {
      status = finishEvent ? 'done' : buildStarted ? 'active' : 'pending'
      if (finishEvent) {
        const count = finishEvent.charts_built?.length
        detail = count ? `Built ${count} charts.` : 'Agent run complete.'
      } else if (buildStarted) {
        detail = 'Agent is inspecting and building…'
      }
    }

    if (errorEvent && (errorEvent.phase === key || (errorEvent.phase === 'build' && key === 'agent_run'))) {
       status = 'error'
    }
    return { key, label, status, detail, time: '' }
  })

  return rows
}

function toTraceEntries(events) {
  return events
    .filter(e => !['step_started', 'healing', 'rationale', 'finish', 'dataset_created'].includes(e.type))
    .map(({ type: _, ...rest }) => rest)
}

export default function ProcessingView({ mode, events, streaming, streamError, datasetLabel, onCancel, onEditHint, onUploadDifferent }) {
  const errorEvent = events.find(e => e.type === 'phase_error')
  const isTerminal = Boolean(errorEvent) && !streaming
  const steps = mode === 'pipeline' ? buildStandardSteps(events) : buildAgentSteps(events)
  const traceEntries = mode === 'agent' ? toTraceEntries(events) : []
  const showAgentTrace = mode === 'agent' && traceEntries.length > 0

  const footerNote = mode === 'pipeline'
    ? 'Standard pipeline — single pass, no self-correction.'
    : 'Agent pipeline — will loop back into self-healing if issues are found while building.'

  return (
    <div className="animate-fade-in max-w-xl w-full mx-auto bg-surface border border-muted rounded-card p-7">
      <div className="flex items-center justify-between gap-4 mb-6">
        <div>
          <div className="font-mono font-semibold text-[10.5px] uppercase tracking-wider text-muted mb-1.5">
            Building Dashboard
          </div>
          <div className="font-display font-medium text-base text-fg">
            {datasetLabel ?? 'Untitled dataset'}
          </div>
        </div>
      </div>

      {isTerminal ? (
        <div className="flex flex-col items-center text-center gap-3.5 py-5 px-2">
          {errorIcon()}
          <div className="font-display font-semibold text-[15px] text-fg">
            Couldn't build any charts from this file
          </div>
          <div className="font-mono text-xs text-muted leading-relaxed max-w-[380px]">
            {errorEvent?.error ?? 'Something went wrong during the build. Adjust the steering hint or upload a corrected file.'}
          </div>
          <div className="flex gap-2.5 mt-1.5">
            <button
              onClick={onEditHint}
              className="px-4 py-2.5 rounded-control font-display font-semibold text-xs tracking-wide bg-accent text-accent-fg"
            >
              EDIT HINT &amp; RETRY
            </button>
            <button
              onClick={onUploadDifferent}
              className="px-4 py-2.5 rounded-control font-display font-medium text-xs tracking-wide border border-muted text-fg"
            >
              UPLOAD DIFFERENT FILE
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4.5">
          {streamError && !errorEvent && (
            <div className="flex items-center gap-2.5 border border-danger rounded-control bg-danger/10 px-3.5 py-2.5">
              <div className="w-2 h-2 rounded-full bg-danger shrink-0" />
              <span className="font-mono text-xs text-fg">{streamError}</span>
            </div>
          )}

          <div className="flex flex-col">
            {steps.map((step, i) => (
              <div key={step.key} className="flex gap-4">
                <div className="flex flex-col items-center w-[14px] shrink-0">
                  <div className={dotClasses(step.status)} />
                  <div className={lineClasses(step.status, i === steps.length - 1)} />
                </div>
                <div className="flex-1 pb-6.5">
                  <div className="flex items-baseline justify-between gap-2.5">
                    <span className={labelClasses(step.status)}>{step.label}</span>
                    {step.time && <span className="font-mono text-[11px] text-muted shrink-0">{step.time}</span>}
                  </div>
                  <span className={detailClasses(step.status)}>{step.detail}</span>
                </div>
              </div>
            ))}
          </div>

          {showAgentTrace && <AgentTrace trace={traceEntries} />}

          <div className="flex items-center justify-between pt-1 border-t border-muted">
            <span className="font-mono text-[11.5px] text-muted pt-4">{footerNote}</span>
            <button
              onClick={onCancel}
              className="mt-4 px-4 py-2.5 rounded-control font-display font-semibold text-xs text-danger border border-danger"
            >
              CANCEL
            </button>
          </div>
        </div>
      )}
    </div>
  )
}