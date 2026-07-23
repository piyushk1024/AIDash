import { useState } from 'react'
import { api } from '../../lib/api'
// import { useAutocomplete, AutocompleteInput } from './NLInput'
import Plot from 'react-plotly.js'

import { useAutocomplete } from './useAutocomplete'
import { AutocompleteInput } from './NLInput'

// import createPlotlyComponent from 'react-plotly.js/factory'
// import Plotly from '../../lib/plotly-custom'
// const Plot = createPlotlyComponent(Plotly)

// --- RenderedChartCard ---
// Card shape: {card_id, chart_title, chart_type, rows, spec, healed, failed}.
// cardState: 'view' | 'editing' | 'confirm-delete' — local UI state per card,
// owned by the parent grid so it can swap the card body without remounting Plotly.

function RenderedChartCard({ card, fieldMap, cardState, onEdit, onCancel, onSubmitEdit, onRequestDelete, onConfirmDelete, editLoading, editError }) {
  const edit = useAutocomplete(fieldMap)

  if (cardState === 'confirm-delete') {
    return (
      <div className="border border-red-500/30 rounded p-4 font-mono text-xs flex flex-col gap-3">
        <span className="text-neutral-300 truncate">{card.chart_title}</span>
        <span className="text-red-400">Delete this chart?</span>
        <div className="flex gap-3">
          <button onClick={onConfirmDelete} className="bg-transparent text-red-400 hover:text-red-300 uppercase tracking-wider">
            Yes, delete
          </button>
          <button onClick={onCancel} className="bg-transparent text-neutral-500 hover:text-neutral-300 uppercase tracking-wider">
            Cancel
          </button>
        </div>
      </div>
    )
  }

  if (cardState === 'editing') {
    return (
      <div className="border border-amber-400/30 rounded p-3 flex flex-col gap-2">
        <span className="font-mono text-[10px] text-neutral-600 truncate">editing: {card.chart_title}</span>
        <AutocompleteInput
          value={edit.value}
          onChange={edit.handleChange}
          suggestions={edit.suggestions}
          onSelect={edit.onSelect}
          onSubmit={() => onSubmitEdit(edit.value.trim(), edit.selectedColumns)}
          loading={editLoading}
          placeholder="Describe the replacement chart..."
          submitLabel="save"
        />
        {editError && <div className="font-mono text-xs text-red-400">✕ {editError}</div>}
        <button onClick={onCancel} className="font-mono text-[10px] text-neutral-600 hover:text-neutral-400 transition-colors self-start">
          cancel
        </button>
      </div>
    )
  }

  if (card.failed || !card.spec) {
    return (
      <div className="border border-red-500/30 rounded p-4 font-mono text-xs text-red-400 relative group">
        ✕ {card.chart_title ?? 'Untitled chart'} — could not be built
        <button onClick={onRequestDelete} className="hidden group-hover:block absolute top-2 right-2 bg-transparent text-neutral-500 hover:text-red-400">
          ✕
        </button>
      </div>
    )
  }

  // Horizontal bar ('row') charts need height proportional to category
  // count — a fixed height either clips long category lists or wastes
  // space on short ones. ~28px per category + 100px baseline for
  // title/axes/margins is the standard formula for this (same approach
  // used across Highcharts, Chart.js, Plotly Dash for dynamic bar charts).
  const rowCount = card.rows?.length ?? 0
  const chartHeight = card.chart_type === 'row'
    ? Math.max(320, rowCount * 28 + 100)
    : 320

  return (
    <div className="border border-neutral-800 rounded p-2 relative group">
      <div className="hidden group-hover:flex absolute top-2 right-2 gap-2 z-10 bg-neutral-950/80 rounded px-1.5 py-1">
        <button onClick={onEdit} title="Edit" className="bg-transparent text-neutral-400 hover:text-amber-400 text-xs">
          ✎
        </button>
        <button onClick={onRequestDelete} title="Delete" className="bg-transparent text-neutral-400 hover:text-red-400 text-xs">
          ✕
        </button>
      </div>
      <Plot
        data={card.spec.data ?? []}
        layout={{ autosize: true,
          margin: { t: 32, r: 16, b: 60, l: 60 },
          xaxis: { automargin: true, ...card.spec.layout?.xaxis },
          yaxis: { automargin: true, ...card.spec.layout?.yaxis },
           ...card.spec.layout }}
        useResizeHandler
        style={{ width: '100%', height: `${chartHeight}px` }}
        config={{ displayModeBar: false, responsive: true }}
      />
      {card.healed && (
        <div className="px-2 pb-1 font-mono text-[10px] text-amber-400/60">healed</div>
      )}
    </div>
  )
}

// --- AddChartCard ---
// Trailing blank card in the grid. Click to reveal the NL input; submit adds
// a chart, cancel collapses back to the blank "+" state.

function AddChartCard({ fieldMap, onAdd }) {
  const [active, setActive] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const add = useAutocomplete(fieldMap)

  async function handleSubmit() {
    if (!add.value.trim()) return
    setLoading(true); setError(null)
    try {
      await onAdd(add.value.trim(), add.selectedColumns)
      add.reset()
      setActive(false)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (!active) {
    return (
      <button
        onClick={() => setActive(true)}
        className="border border-dashed border-neutral-700 rounded p-2 min-h-[200px] flex items-center justify-center font-mono text-2xl text-neutral-600 hover:text-amber-400 hover:border-amber-400/40 transition-colors bg-transparent"
      >
        +
      </button>
    )
  }

  return (
    <div className="border border-amber-400/30 rounded p-3 min-h-[200px] flex flex-col gap-2 justify-center">
      <span className="font-mono text-[10px] text-neutral-600">new chart</span>
      <AutocompleteInput
        value={add.value}
        onChange={add.handleChange}
        suggestions={add.suggestions}
        onSelect={add.onSelect}
        onSubmit={handleSubmit}
        loading={loading}
        placeholder='e.g. "bar chart of sales by region"'
      />
      {error && <div className="font-mono text-xs text-red-400">✕ {error}</div>}
      <button onClick={() => { setActive(false); setError(null) }} className="font-mono text-[10px] text-neutral-600 hover:text-neutral-400 transition-colors self-start">
        cancel
      </button>
    </div>
  )
}

// --- ChartGrid (default export) ---
// mode: 'pipeline' | 'agent' — targets which dashboard add/edit/delete apply to.

export default function ChartGrid({ cards, datasetId, fieldMap, mode = 'pipeline', onCardAdded, onCardEdited, onCardDeleted }) {
  const [cardStates, setCardStates] = useState({})   // card_id -> 'editing' | 'confirm-delete'
  const [editLoading, setEditLoading] = useState(null) // card_id currently saving
  const [editErrors, setEditErrors] = useState({})     // card_id -> error message

  function setState(cardId, state) {
    setCardStates(prev => ({ ...prev, [cardId]: state }))
  }

  async function handleSubmitEdit(cardId, value, selectedColumns) {
    setEditLoading(cardId)
    setEditErrors(prev => ({ ...prev, [cardId]: null }))
    try {
      const result = await api.editNLChart(datasetId, cardId, value, selectedColumns, mode)
      onCardEdited(cardId, result)
      setState(cardId, 'view')
    } catch (e) {
      setEditErrors(prev => ({ ...prev, [cardId]: e.message }))
    } finally {
      setEditLoading(null)
    }
  }

  async function handleConfirmDelete(cardId) {
    try {
      await api.deleteNLChart(datasetId, cardId, mode)
      onCardDeleted(cardId)
    } catch {
      setState(cardId, 'view')
    }
  }

  async function handleAdd(value, selectedColumns) {
    const result = await api.addNLChart(datasetId, value, selectedColumns, mode)
    onCardAdded(result)
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:grid-flow-row-dense">
      {(cards ?? []).map(card => (
        // Horizontal bar ('row') charts put category labels on the y-axis,
        // where they compete with a fixed-width column — long labels get
        // cramped in a half-width card. Giving 'row' charts the full row
        // is a standard horizontal-bar-chart practice, not specific to any
        // one dataset's label lengths.
        <div key={card.card_id ?? card.chart_title} className={card.chart_type === 'row' ? 'md:col-span-2' : ''}>
          <RenderedChartCard
            card={card}
            fieldMap={fieldMap}
            cardState={cardStates[card.card_id] ?? 'view'}
            onEdit={() => setState(card.card_id, 'editing')}
            onCancel={() => setState(card.card_id, 'view')}
            onSubmitEdit={(value, selectedColumns) => handleSubmitEdit(card.card_id, value, selectedColumns)}
            onRequestDelete={() => setState(card.card_id, 'confirm-delete')}
            onConfirmDelete={() => handleConfirmDelete(card.card_id)}
            editLoading={editLoading === card.card_id}
            editError={editErrors[card.card_id]}
          />
        </div>
      ))}
      <AddChartCard fieldMap={fieldMap} onAdd={handleAdd} />
    </div>
  )
}