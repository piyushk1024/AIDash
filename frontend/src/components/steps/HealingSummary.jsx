import { useState } from 'react'

export default function HealingSummary({ cards, errors }) {
  const [expanded, setExpanded] = useState(false)
  const healed = cards?.filter(c => c.healed) ?? []

  return (
    <div className="mt-4 border border-amber-400/30 rounded overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-2 px-3 py-2 font-mono text-xs hover:bg-amber-400/5 transition-colors"
      >
        <span className="text-amber-400">⟳</span>
        <span className="text-neutral-400">
          {healed.length > 0 && `${healed.length} healed`}
          {healed.length > 0 && errors?.length > 0 && ' · '}
          {errors?.length > 0 && `${errors.length} discarded`}
        </span>
        <span className="ml-auto text-neutral-600">{expanded ? '▴' : '▾'}</span>
      </button>

      {expanded && (
        <div className="border-t border-amber-400/20 px-3 py-3 space-y-4">
          {healed.map(c => (
            <div key={c.card_id} className="space-y-1.5">
              <div className="flex items-center gap-2 font-mono text-xs">
                <span className="text-amber-400">⟳</span>
                <span className="text-neutral-200">{c.original_chart.chart_title}</span>
                <span className="text-neutral-600">→</span>
                <span className="text-neutral-400">{c.chart_title}</span>
              </div>
              <div className="font-mono text-xs text-neutral-600 pl-4">
                {c.original_chart.aggregation}({c.original_chart.y_axis ?? c.original_chart.x_axis})
                <span className="text-neutral-700"> → </span>
                {c.healed_chart.aggregation}({c.healed_chart.y_axis ?? c.healed_chart.x_axis})
              </div>
              {c.healed_chart.reasoning && (
                <div className="font-mono text-xs text-neutral-500 pl-4 leading-relaxed">
                  {c.healed_chart.reasoning}
                </div>
              )}
            </div>
          ))}

          {errors?.map((e, i) => (
            <div key={i} className="space-y-1.5">
              <div className="flex items-center gap-2 font-mono text-xs">
                <span className="text-red-400">✕</span>
                <span className="text-neutral-200">{e.chart_title}</span>
                <span className="text-red-400/50 ml-auto">discarded</span>
              </div>
              <div className="font-mono text-xs text-neutral-600 pl-4">
                {e.chart_type} · {e.aggregation}
                {e.y_axis && ` · avg on ${e.y_axis}`}
                {e.x_axis && ` · by ${e.x_axis}`}
              </div>
              <div className="font-mono text-xs text-red-400/60 pl-4">{e.heal_error}</div>
              <div className="font-mono text-xs text-neutral-600 pl-4 leading-relaxed">
                To fix: ensure this column contains only numeric values in your CSV and re-upload.
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}