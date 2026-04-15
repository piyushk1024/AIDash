import { useState } from 'react'

export default function SemanticsStep({ dasher, isActive, isExpanded, onToggle }) {
  const { inferSemantics, status, errors, semantics } = dasher
  const [hint, setHint] = useState('')

  const isLoading = status.semantics === 'loading'
  const isDone    = status.semantics === 'done'

  if (isDone && semantics) {
    const allColumns = [
      ...semantics.date_columns,
      ...semantics.dimensions,
      ...semantics.measures,
      ...semantics.flags,
      ...semantics.identifiers,
      ...semantics.unknown,
    ]
    return (
      <div className="animate-fade-in">
        <button
          onClick={onToggle}
          className="w-full px-4 py-3 flex items-center gap-3 font-mono text-xs text-left rounded border border-transparent hover:border-neutral-200 dark:hover:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-900 transition-all duration-150 cursor-pointer"
          title="Click to expand"
        >
          <span className="text-neutral-500 uppercase tracking-wider">Semantics</span>
          <span className="text-neutral-300 dark:text-neutral-600">—</span>
          <span className="text-neutral-700 dark:text-neutral-300">{allColumns.length} columns</span>
          <span className="text-neutral-400 truncate max-w-48">{semantics.dataset_grain}</span>
          <span className="text-amber-400 ml-auto">✓</span>
          <span className={`text-neutral-400 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>▾</span>
        </button>

        {isExpanded && (
          <div className="animate-fade-in mx-1 mb-3 px-4 py-3 border border-neutral-200 dark:border-neutral-800 rounded-b bg-neutral-50 dark:bg-neutral-900/50">
            <div className="flex flex-wrap gap-2 mb-3">
              {allColumns.map(col => <ColumnChip key={col.column} col={col} />)}
            </div>
            {semantics.notes?.length > 0 && (
              <div className="space-y-1 mt-2 border-t border-neutral-200 dark:border-neutral-800 pt-2">
                {semantics.notes.map((note, i) => (
                  <div key={i} className="font-mono text-xs text-neutral-500">— {note}</div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  if (!isActive) return null

  return (
    <div className="animate-fade-in mt-6">
      <div className="rounded-lg border border-amber-400/30 bg-amber-400/[0.02] dark:bg-amber-400/[0.03] px-6 py-5">
        <StepHeader title="Infer Semantics" />
        <p className="font-mono text-xs text-neutral-500 mt-1 mb-5">
          Gemini classifies every column — measures, dimensions, dates, flags.
        </p>

        <div className="mb-4">
          <label className="font-mono text-xs text-neutral-500 tracking-wider uppercase block mb-2">
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

        {errors.semantics && (
          <div className="mb-3 font-mono text-xs text-red-400">✕ {errors.semantics}</div>
        )}

        <div className="flex items-center gap-4">
          <button
            onClick={() => inferSemantics(hint || null)}
            disabled={isLoading}
            className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200 disabled:bg-neutral-100 dark:disabled:bg-neutral-800 disabled:text-neutral-400 dark:disabled:text-neutral-600 disabled:cursor-not-allowed enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer enabled:shadow-sm"
          >
            {isLoading ? 'Analysing...' : 'Run Inference'}
          </button>
          {isLoading && (
            <span className="font-mono text-xs text-neutral-500 animate-pulse">
              Profiling columns, calling Gemini...
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

const ROLE_COLOURS = {
  date:       'border-blue-500/40    text-blue-400    bg-blue-500/5',
  dimension:  'border-violet-500/40  text-violet-400  bg-violet-500/5',
  measure:    'border-emerald-500/40 text-emerald-400 bg-emerald-500/5',
  flag:       'border-amber-500/40   text-amber-400   bg-amber-500/5',
  identifier: 'border-neutral-500/40 text-neutral-500 bg-neutral-500/5',
  unknown:    'border-neutral-600/40 text-neutral-600 bg-neutral-600/5',
}

function ColumnChip({ col }) {
  const role = col.semantic_role?.toLowerCase().includes('date')       ? 'date'
             : col.semantic_role?.toLowerCase().includes('measure')    ? 'measure'
             : col.semantic_role?.toLowerCase().includes('dimension')  ? 'dimension'
             : col.semantic_role?.toLowerCase().includes('flag')       ? 'flag'
             : col.semantic_role?.toLowerCase().includes('identifier') ? 'identifier'
             : 'unknown'

  const colours = ROLE_COLOURS[role] ?? ROLE_COLOURS.unknown

  return (
    <div className={`border rounded px-2 py-1 font-mono text-xs flex items-center gap-1.5 ${colours} ${!col.chartable ? 'opacity-40' : ''}`}>
      <span>{col.column}</span>
      {!col.chartable && <span className="text-[10px] opacity-60">n/c</span>}
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