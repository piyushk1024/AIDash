// import { useState } from 'react'

// Pulled out of the retired NLAuthoringPanel.jsx — generic NL-prompt input
// with column-name autocomplete against fieldMap. Used by ChartGrid's
// per-card edit state and the trailing add-card.


export function AutocompleteInput({ value, onChange, suggestions, onSelect, onSubmit, loading, placeholder, submitLabel = 'add' }) {
  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSubmit() }
  }

  return (
    <div className="relative">
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={loading}
          autoFocus
          className="flex-1 bg-transparent border border-muted rounded px-2 py-1.5 font-mono text-xs text-fg placeholder-muted focus:outline-none focus:border-accent transition-colors disabled:opacity-50"
        />
        <button
          onClick={onSubmit}
          disabled={loading || !value.trim()}
            className="px-3 py-1.5 rounded font-mono text-xs tracking-widest uppercase transition-all disabled:bg-surface disabled:text-muted disabled:cursor-not-allowed enabled:bg-accent enabled:text-accent-fg enabled:hover:bg-accent/90"
        >
          {loading ? '...' : submitLabel}
        </button>
      </div>
      {suggestions.length > 0 && (
        <div className="absolute z-10 left-0 right-16 top-full mt-1 bg-surface border border-muted rounded shadow-lg overflow-hidden">
          {suggestions.map(col => (
            <button key={col} onClick={() => onSelect(col)}
                      className="w-full text-left px-3 py-1.5 font-mono text-xs text-fg hover:bg-bg hover:text-accent transition-colors">
              {col}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}