import { useState } from 'react'
import { api } from '../../lib/api'

// --- useAutocomplete ---

function useAutocomplete(fieldMap) {
  const [value, setValue] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [selectedColumns, setSelectedColumns] = useState([])

  function handleChange(raw) {
    setValue(raw)
    const lastWord = raw.split(' ').pop().toLowerCase()
    if (lastWord.length < 1) { setSuggestions([]); return }
    const keys = Object.keys(fieldMap ?? {})
    setSuggestions(keys.filter(k => k.toLowerCase().includes(lastWord)).slice(0, 6))
  }

  function onSelect(col) {
    const parts = value.split(' ')
    parts[parts.length - 1] = col
    setValue(parts.join(' ') + ' ')
    setSuggestions([])
    setSelectedColumns(prev => prev.includes(col) ? prev : [...prev, col])
  }

  function reset() { setValue(''); setSuggestions([]); setSelectedColumns([]) }

  return { value, handleChange, suggestions, selectedColumns, onSelect, reset }
}

// --- AutocompleteInput ---

function AutocompleteInput({ value, onChange, suggestions, onSelect, onSubmit, loading, placeholder, submitLabel = '+ add' }) {
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
          className="flex-1 bg-transparent border border-neutral-700 rounded px-3 py-2 font-mono text-xs text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-amber-400 transition-colors disabled:opacity-50"
        />
        <button
          onClick={onSubmit}
          disabled={loading || !value.trim()}
          className="px-4 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300"
        >
          {loading ? '...' : submitLabel}
        </button>
      </div>
      {suggestions.length > 0 && (
        <div className="absolute z-10 left-0 right-20 top-full mt-1 bg-neutral-900 border border-neutral-700 rounded shadow-lg overflow-hidden">
          {suggestions.map(col => (
            <button key={col} onClick={() => onSelect(col)}
              className="w-full text-left px-3 py-1.5 font-mono text-xs text-neutral-300 hover:bg-neutral-800 hover:text-amber-400 transition-colors">
              {col}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// --- CardRow ---

function CardRow({ card, onEdit, onDelete }) {
  const TYPE_STYLE = {
    bar:    'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    line:   'bg-blue-500/10    text-blue-400    border-blue-500/20',
    scalar: 'bg-amber-500/10   text-amber-400   border-amber-500/20',
    pie:    'bg-violet-500/10  text-violet-400  border-violet-500/20',
  }[card.chart_type] ?? 'bg-neutral-800 text-neutral-500 border-neutral-700'

  const usedColumns = [card.x_axis, card.y_axis].filter(Boolean)

  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded bg-neutral-900 border border-neutral-800 hover:border-neutral-700 font-mono text-xs group transition-colors">
      <span className={`border rounded px-1.5 py-0.5 text-[10px] uppercase shrink-0 ${TYPE_STYLE}`}>
        {card.chart_type ?? '—'}
      </span>
      <span className="text-neutral-200 flex-1 truncate">{card.chart_title}</span>
      {usedColumns.length > 0 && (
        <div className="hidden group-hover:flex items-center gap-1">
          {usedColumns.map(col => (
            <span key={col} className="px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-500 text-[10px] border border-neutral-700">
              {col}
            </span>
          ))}
        </div>
      )}
      {card.healed && <span className="text-amber-400/60 text-[10px] shrink-0">healed</span>}
      <div className="hidden group-hover:flex items-center gap-2 shrink-0">
        <button onClick={onEdit} className="bg-transparent text-neutral-200 hover:text-amber-400 transition-colors text-[10px] uppercase tracking-wider">
          Edit
        </button>
        <button onClick={onDelete} className="bg-transparent text-neutral-200 hover:text-amber-400 transition-colors text-[10px] uppercase tracking-wider">
          Delete
        </button>
      </div>
    </div>
  )
}

// --- NLEditRow ---

function NLEditRow({ card, datasetId, fieldMap, onDone, onCancel }) {
  const edit = useAutocomplete(fieldMap)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  async function handleSubmit() {
    if (!edit.value.trim()) return
    setLoading(true); setError(null)
    try {
      const result = await api.editNLChart(datasetId, card.card_id, edit.value.trim(), edit.selectedColumns)
      setSuccess(true)
      setTimeout(() => onDone(result), 1000)
    } catch (e) {
      setError(typeof e.message === 'string' ? e.message : JSON.stringify(e.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="py-1.5 space-y-1.5 border-l-2 border-amber-400/30 pl-3">
      <div className="font-mono text-[10px] text-neutral-600 truncate">editing: {card.chart_title}</div>
      <AutocompleteInput
        value={edit.value}
        onChange={edit.handleChange}
        suggestions={edit.suggestions}
        onSelect={edit.onSelect}
        onSubmit={handleSubmit}
        loading={loading}
        placeholder="Describe the replacement chart..."
        submitLabel="save"
      />
      {error && <div className="font-mono text-xs text-red-400">✕ {error}</div>}
      {success && <div className="font-mono text-xs text-emerald-400">✓ Chart updated</div>}
      <button onClick={onCancel} className="font-mono text-[10px] text-neutral-600 hover:text-neutral-400 transition-colors">
        cancel
      </button>
    </div>
  )
}

// --- NLAuthoringPanel (default export) ---

export default function NLAuthoringPanel({ datasetId, fieldMap, cards, onCardAdded, onCardEdited, onCardDeleted }) {
  const add = useAutocomplete(fieldMap)
  const [addLoading, setAddLoading] = useState(false)
  const [addError, setAddError] = useState(null)
  const [editingCardId, setEditingCardId] = useState(null)
  const [addSuccess, setAddSuccess] = useState(false)

  async function handleAdd() {
    if (!add.value.trim()) return
    setAddLoading(true); setAddError(null)
    try {
      const result = await api.addNLChart(datasetId, add.value.trim(), add.selectedColumns)
      onCardAdded(result)
      add.reset()
      setAddSuccess(true)
      setTimeout(() => setAddSuccess(false), 3000)
    } catch (e) {
      setAddError(e.message)
    } finally {
      setAddLoading(false)
    }
  }

  async function handleDelete(cardId) {
    try {
      await api.deleteNLChart(datasetId, cardId)
      onCardDeleted(cardId)
    } catch (e) {
      // silently ignore — card stays in list
    }
  }

  return (
    <div className="border border-neutral-800 rounded overflow-hidden">
      <div className="px-3 py-2 border-b border-neutral-800 font-mono text-[10px] text-neutral-600 uppercase tracking-wider">
        Natural language authoring
      </div>
      <div className="p-3 space-y-3">
        <AutocompleteInput
          value={add.value}
          onChange={add.handleChange}
          suggestions={add.suggestions}
          onSelect={add.onSelect}
          onSubmit={handleAdd}
          loading={addLoading}
          placeholder='e.g. "bar chart of sales by region"'
        />
        {addSuccess && (
          <div className="font-mono text-xs text-emerald-400">✓ Chart added — reload iframe to see it</div>
        )}
        {addError && <div className="font-mono text-xs text-red-400">✕ {addError}</div>}

        {cards.length > 0 && (
          <div className="border-t border-neutral-800 pt-3 space-y-0.5">
            <div className="font-mono text-[10px] text-neutral-600 uppercase tracking-wider mb-2">Current charts</div>
            {cards.map(card => (
              editingCardId === card.card_id
                ? <NLEditRow
                    key={card.card_id}
                    card={card}
                    datasetId={datasetId}
                    fieldMap={fieldMap}
                    onDone={updated => { onCardEdited(card.card_id, updated); setEditingCardId(null) }}
                    onCancel={() => setEditingCardId(null)}
                  />
                : <CardRow
                    key={card.card_id}
                    card={card}
                    onEdit={() => setEditingCardId(card.card_id)}
                    onDelete={() => handleDelete(card.card_id)}
                  />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}