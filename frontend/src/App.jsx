import { useState, useEffect } from 'react'
import { useDasher } from './hooks/useDasher'
import { api } from './lib/api'
import UploadStep from './components/steps/UploadStep'
import SemanticsStep from './components/steps/SemanticsStep'
import PlanStep from './components/steps/PlanStep'
import DashboardStep from './components/steps/DashboardStep'

const STEPS = [
  { key: 'upload',    number: '01', label: 'Upload Dataset' },
  { key: 'semantics', number: '02', label: 'Infer Semantics' },
  { key: 'plan',      number: '03', label: 'Generate Plan' },
  { key: 'dashboard', number: '04', label: 'Build Dashboard' },
]

export default function App() {
  const [dark, setDark] = useState(true)
  const [phase, setPhase] = useState('pick')       // 'pick' | 'wizard'
  const [datasets, setDatasets] = useState([])
  const [picking, setPicking] = useState(true)     // loading state for the picker

  const dasher = useDasher()
  const { status, rehydrate } = dasher

  const activeStep = STEPS.find(s => status[s.key] !== 'done')?.key ?? 'upload'
  const [expandedSteps, setExpandedSteps] = useState(new Set())

  // Fetch existing datasets on mount
  useEffect(() => {
    api.listDatasets()
      .then(res => setDatasets(res.datasets ?? []))
      .catch(() => setDatasets([]))
      .finally(() => setPicking(false))
  }, [])

  function toggleExpanded(key) {
    setExpandedSteps(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  async function handlePickDataset(datasetId) {
    setPicking(true)
    await rehydrate(datasetId)
    setPicking(false)
    setPhase('wizard')
  }

  function handleStartFresh() {
    setPhase('wizard')
  }

  async function handleDeleteDataset(datasetId) {
  await api.deleteDataset(datasetId)
  setDatasets(prev => prev.filter(d => d.dataset_id !== datasetId))
}

  // ── Picker screen ───────────────────────────────────────────
  if (phase === 'pick') {
    return (
      <div className={dark ? 'dark' : ''}>
        <div className="min-h-screen bg-white dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 transition-colors duration-300">
          <header className="border-b border-neutral-200 dark:border-neutral-800 px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-6 h-6 bg-amber-400 rounded-sm rotate-45" />
              <span className="font-mono text-sm tracking-widest uppercase text-neutral-500 dark:text-neutral-400">
                Dasher
              </span>
            </div>
            <button
              onClick={() => setDark(d => !d)}
              className="font-mono text-xs text-neutral-400 hover:text-amber-400 transition-colors tracking-wider uppercase"
            >
              {dark ? '[ light ]' : '[ dark ]'}
            </button>
          </header>

          <div className="max-w-xl mx-auto px-8 py-16">
            <p className="font-mono text-xs tracking-widest uppercase text-neutral-400 mb-8">
              Continue a dataset or start fresh
            </p>

            {picking ? (
              <p className="font-mono text-xs text-neutral-500">Loading...</p>
            ) : (
              <div className="flex flex-col gap-2">
                {datasets.map(ds => (
                  <div key={ds.dataset_id} className="flex items-center gap-2">
                    <button
                      onClick={() => handlePickDataset(ds.dataset_id)}
                      className="flex-1 text-left px-4 py-3 border border-neutral-200 dark:border-neutral-800 
                                hover:border-amber-400 dark:hover:border-amber-400
                                font-mono text-sm transition-colors"
                    >
                      {ds.original_filename}
                      <span className="ml-3 text-xs text-neutral-400">{ds.dataset_id.slice(0, 8)}</span>
                    </button>
                    <button
                      onClick={() => handleDeleteDataset(ds.dataset_id)}
                      className="px-3 py-3 font-mono text-xs text-neutral-500 hover:text-red-400 transition-colors"
                    >
                      [ x ]
                    </button>
                  </div>
                ))}


                <button
                  onClick={handleStartFresh}
                  className="mt-4 text-left px-4 py-3 border border-dashed border-neutral-300 dark:border-neutral-700
                             hover:border-amber-400 dark:hover:border-amber-400
                             font-mono text-sm text-neutral-400 hover:text-amber-400 transition-colors"
                >
                  + Start fresh
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ── Wizard screen (unchanged) ───────────────────────────────
  return (
    <div className={dark ? 'dark' : ''}>
      <div className="min-h-screen bg-white dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 transition-colors duration-300">

        <header className="border-b border-neutral-200 dark:border-neutral-800 px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 bg-amber-400 rounded-sm rotate-45" />
            <span className="font-mono text-sm tracking-widest uppercase text-neutral-500 dark:text-neutral-400">
              Dasher
            </span>
          </div>
          <div className="flex items-center gap-6">
            <button
              onClick={() => setPhase('pick')}
              className="font-mono text-xs text-neutral-400 hover:text-amber-400 transition-colors tracking-wider uppercase"
            >
              [ datasets ]
            </button>
            <button
              onClick={() => setDark(d => !d)}
              className="font-mono text-xs text-neutral-400 hover:text-amber-400 transition-colors tracking-wider uppercase"
            >
              {dark ? '[ light ]' : '[ dark ]'}
            </button>
          </div>
        </header>

        <div className="flex max-w-5xl mx-auto px-8 py-12 gap-16">
          <nav className="flex flex-col gap-8 pt-1 shrink-0">
            {STEPS.map(step => {
              const isDone   = status[step.key] === 'done'
              const isActive = step.key === activeStep
              const isLocked = !isDone && !isActive
              return (
                <div key={step.key} className="flex items-center gap-3">
                  <div className={`
                    w-8 h-8 rounded-full flex items-center justify-center
                    font-mono text-xs transition-all duration-300
                    ${isDone   ? 'bg-amber-400 text-neutral-950' : ''}
                    ${isActive ? 'border-2 border-amber-400 text-amber-400' : ''}
                    ${isLocked ? 'border border-neutral-300 dark:border-neutral-700 text-neutral-400' : ''}
                  `}>
                    {isDone ? '✓' : step.number}
                  </div>
                  <span className={`
                    font-mono text-xs tracking-wider uppercase transition-colors duration-300
                    ${isActive ? 'text-neutral-900 dark:text-neutral-100' : ''}
                    ${isDone   ? 'text-neutral-400 dark:text-neutral-500' : ''}
                    ${isLocked ? 'text-neutral-300 dark:text-neutral-700' : ''}
                  `}>
                    {step.label}
                  </span>
                </div>
              )
            })}
          </nav>

          <main className="flex-1 min-w-0 space-y-1">
            <UploadStep      dasher={dasher} isActive={activeStep === 'upload'}    isExpanded={expandedSteps.has('upload')}    onToggle={() => toggleExpanded('upload')} />
            <SemanticsStep   dasher={dasher} isActive={activeStep === 'semantics'} isExpanded={expandedSteps.has('semantics')} onToggle={() => toggleExpanded('semantics')} />
            <PlanStep        dasher={dasher} isActive={activeStep === 'plan'}      isExpanded={expandedSteps.has('plan')}      onToggle={() => toggleExpanded('plan')} />
            <DashboardStep   dasher={dasher} isActive={activeStep === 'dashboard'} isExpanded={expandedSteps.has('dashboard')} onToggle={() => toggleExpanded('dashboard')} />
          </main>
        </div>
      </div>
    </div>
  )
}