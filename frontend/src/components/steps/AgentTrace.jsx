import { useState } from 'react'

const TOOL_STYLE = {
  inspect_data:        { icon: '⊕', label: 'inspect' },
  build_and_add_chart: { icon: '▣', label: 'build chart' },
  edit_existing_chart: { icon: '✎', label: 'edit chart' },
  delete_existing_chart: { icon: '✕', label: 'delete chart' },
  finish:              { icon: '✓', label: 'finish' },
}

function formatObservation(obs) {
  if (typeof obs === 'string') return obs
  if (obs.error) return `✕ ${obs.error}`
  if (obs.success) return `✓ ${obs.chart_title}`
  if (obs.acknowledged) return 'Done'
  if (obs.rows) return `${obs.rows.length} rows · ${obs.columns?.length ?? 0} columns`
  return JSON.stringify(obs)
}

export default function AgentTrace({ trace }) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="border border-muted rounded-control overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-2 px-3 py-2 font-mono text-xs hover:bg-accent-wash-soft transition-colors"
      >
        <span className="text-muted uppercase tracking-wider">Agent trace</span>
        <span className="text-muted/60 ml-1">— {trace.length} steps</span>
        <span className="ml-auto text-muted">{expanded ? '▴' : '▾'}</span>
      </button>

      {expanded && (
        <div className="border-t border-muted">
          {trace.map((step, idx) => {
            const style = TOOL_STYLE[step.tool] ?? { icon: '·', label: step.tool }
            const isLast = idx === trace.length - 1

            return (
              <div key={step.step} className="flex gap-3 px-3 py-3">
                <div className="flex flex-col items-center shrink-0">
                  <span className="font-mono text-[10px] uppercase border border-muted rounded px-1.5 py-0.5 text-accent">
                    {style.icon}
                  </span>
                  {!isLast && <div className="w-px flex-1 bg-muted mt-1.5" />}
                </div>

                <div className="pb-3 min-w-0 space-y-1">
                  <div className="flex items-center gap-2 font-mono text-xs">
                    <span className="text-[10px] uppercase tracking-wider text-accent">
                      {style.label}
                    </span>
                    <span className="text-muted/60">step {step.step}</span>
                  </div>
                  {step.reasoning && (
                    <div className="font-mono text-xs text-muted leading-relaxed">
                      {step.reasoning}
                    </div>
                  )}
                  {step.observation && (
                    <div className="font-mono text-[10px] text-muted/80 leading-relaxed border-l border-muted pl-2 mt-1">
                     {formatObservation(step.observation)}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}