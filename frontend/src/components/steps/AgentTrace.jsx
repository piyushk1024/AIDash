import { useState } from 'react'

const TOOL_STYLE = {
  inspect_data:        { badge: 'border-blue-500/30 text-blue-400',       color: 'text-blue-400',    icon: '⊕', label: 'inspect' },
  build_and_add_chart: { badge: 'border-emerald-500/30 text-emerald-400', color: 'text-emerald-400', icon: '▣', label: 'build chart' },
  finish:              { badge: 'border-amber-500/30 text-amber-400',     color: 'text-amber-400',   icon: '✓', label: 'finish' },
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
    <div className="border border-neutral-800 rounded overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-2 px-3 py-2 font-mono text-xs hover:bg-neutral-800/50 transition-colors"
      >
        <span className="text-neutral-500 uppercase tracking-wider">Agent trace</span>
        <span className="text-neutral-700 ml-1">— {trace.length} steps</span>
        <span className="ml-auto text-neutral-600">{expanded ? '▴' : '▾'}</span>
      </button>

      {expanded && (
        <div className="border-t border-neutral-800">
          {trace.map((step, idx) => {
            const style = TOOL_STYLE[step.tool] ?? { badge: 'border-neutral-700 text-neutral-500', icon: '·', label: step.tool }
            const isLast = idx === trace.length - 1

            return (
              <div key={step.step} className="flex gap-3 px-3 py-3">
                <div className="flex flex-col items-center shrink-0">
                  <span className={`font-mono text-xs border rounded px-1.5 py-0.5 text-[10px] uppercase ${style.badge}`}>
                    {style.icon}
                  </span>
                  {!isLast && <div className="w-px flex-1 bg-neutral-800 mt-1.5" />}
                </div>

                <div className="pb-3 min-w-0 space-y-1">
                  <div className="flex items-center gap-2 font-mono text-xs">
                    <span className={`text-[10px] uppercase tracking-wider ${style.badge.split(' ')[1]}`}>
                      {style.label}
                    </span>
                    <span className="text-neutral-700">step {step.step}</span>
                  </div>
                  {step.reasoning && (
                    <div className="font-mono text-xs text-neutral-400 leading-relaxed">
                      {step.reasoning}
                    </div>
                  )}
                  {step.observation && (
                    <div className="font-mono text-[10px] text-neutral-600 leading-relaxed border-l border-neutral-800 pl-2 mt-1">
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