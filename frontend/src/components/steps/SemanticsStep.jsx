import { useState } from 'react'

export default function SemanticsStep({ dasher, isActive, isExpanded, onToggle }) {
  const { inferSemantics, status, errors, semantics, uploadResult } = dasher
  const [hint, setHint] = useState('')

  const isLoading = status.semantics === 'loading'
  const isDone    = status.semantics === 'done'

  // ── Done — show a compact column summary ──
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
          className="w-full py-2 flex items-center gap-3 font-mono text-xs hover:opacity-80 transition-opacity text-left"
        >
          <span className="text-neutral-500 uppercase tracking-wider">Infer Semantics</span>
          <span className="text-neutral-600">—</span>
          <span className="text-neutral-400">{allColumns.length} columns</span>
          <span className="text-neutral-600">{semantics.dataset_grain}</span>
          <span className="text-amber-400 ml-auto">✓</span>
          <span className={`text-neutral-600 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
            ▾
          </span>
        </button>

        {isExpanded && (
          <div className="animate-fade-in mb-4">
            <div className="flex flex-wrap gap-2 mb-3">
              {allColumns.map(col => <ColumnChip key={col.column} col={col} />)}
            </div>
            {semantics.notes?.length > 0 && (
              <div className="space-y-1">
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
    <div className="animate-fade-in mt-12">
      <StepHeader title="Infer Semantics" />

      <p className="font-mono text-xs text-neutral-500 dark:text-neutral-500 mt-2 mb-6">
        Gemini will classify every column — measures, dimensions, dates, flags.
      </p>

      {/* Optional hint — pre-filled from upload if provided */}
      <div className="mb-4">
        <label className="font-mono text-xs text-neutral-500 tracking-wider uppercase block mb-2">
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

      {errors.semantics && (
        <div className="mb-3 font-mono text-xs text-red-400">
          ✕ {errors.semantics}
        </div>
      )}

      <button
        onClick={() => inferSemantics(hint || null)}
        disabled={isLoading}
        className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200
          disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed
          enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer"
      >
        {isLoading ? 'Analysing...' : 'Run Inference →'}
      </button>

      {isLoading && (
        <div className="mt-3 font-mono text-xs text-neutral-500 animate-pulse">
          Profiling columns, calling Gemini...
        </div>
      )}
    </div>
  )
}

// ── Role → colour mapping ─────────────────────────────────────
// Each semantic role gets a distinct muted colour so the chip grid
// is scannable at a glance without being loud
const ROLE_COLOURS = {
  date:       'border-blue-500/40   text-blue-400',
  dimension:  'border-violet-500/40 text-violet-400',
  measure:    'border-emerald-500/40 text-emerald-400',
  flag:       'border-amber-500/40  text-amber-400',
  identifier: 'border-neutral-500/40 text-neutral-500',
  unknown:    'border-neutral-600/40 text-neutral-600',
}

function roleKey(col, semantics) {
  // Work out which category this column came from so we can colour it
  if (!semantics) return 'unknown'
  if (semantics.date_columns?.find(c => c.column === col.column)) return 'date'
  if (semantics.dimensions?.find(c => c.column === col.column))   return 'dimension'
  if (semantics.measures?.find(c => c.column === col.column))     return 'measure'
  if (semantics.flags?.find(c => c.column === col.column))        return 'flag'
  if (semantics.identifiers?.find(c => c.column === col.column))  return 'identifier'
  return 'unknown'
}

function ColumnChip({ col }) {
  // Derive role from the column's semantic_role string directly
  const role = col.semantic_role?.toLowerCase().includes('date')       ? 'date'
             : col.semantic_role?.toLowerCase().includes('measure')    ? 'measure'
             : col.semantic_role?.toLowerCase().includes('dimension')  ? 'dimension'
             : col.semantic_role?.toLowerCase().includes('flag')       ? 'flag'
             : col.semantic_role?.toLowerCase().includes('identifier') ? 'identifier'
             : 'unknown'

  const colours = ROLE_COLOURS[role] ?? ROLE_COLOURS.unknown

  return (
    <div className={`
      border rounded px-2 py-1 font-mono text-xs flex items-center gap-2
      ${colours}
      ${!col.chartable ? 'opacity-40' : ''}
    `}>
      <span>{col.column}</span>
      {!col.chartable && (
        <span className="text-neutral-600 text-[10px]">non-chartable</span>
      )}
    </div>
  )
}

function StepHeader({ title, done }) {
  return (
    <div className="flex items-center gap-3 mb-2">
      <h2 className="font-mono text-sm tracking-widest uppercase text-neutral-900 dark:text-neutral-100">
        {title}
      </h2>
      {done && <span className="font-mono text-xs text-amber-400">✓ done</span>}
    </div>
  )
}