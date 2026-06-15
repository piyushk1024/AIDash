import { useState, useEffect, useRef } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { useDasher } from './hooks/useDasher'
import { api } from './lib/api'
import UploadStep from './components/steps/UploadStep'
import SemanticsStep from './components/steps/SemanticsStep'
import PlanStep from './components/steps/PlanStep'
import DashboardStep from './components/steps/DashboardStep'
import AuthPage from './components/AuthPage'
import SharePage from './components/sharepage'

const STEPS = [
  { key: 'upload',    number: '01', label: 'Upload Dataset' },
  { key: 'semantics', number: '02', label: 'Infer Semantics' },
  { key: 'plan',      number: '03', label: 'Generate Plan' },
  { key: 'dashboard', number: '04', label: 'Build Dashboard' },
]

// Inline placeholder — replaced by AuthPage.jsx next step

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route path="/share/:datasetId" element={<SharePage />} />
      <Route path="/*"     element={<DasherApp />} />
    </Routes>
  )
}

function DasherApp() {
  const auth = useAuth()
  const [dark, setDark] = useState(true)
  const [phase, setPhase] = useState('pick')
  const [datasets, setDatasets] = useState([])
  const [picking, setPicking] = useState(true)

  const dasher = useDasher()
  const { status, rehydrate, dashboardResult } = dasher

  const activeStep = STEPS.find(s => status[s.key] !== 'done')?.key ?? 'upload'
  const [expandedSteps, setExpandedSteps] = useState(new Set())

  const dashboardDone = status.dashboard === 'done' && dashboardResult
  const dashboardRef = useRef(null)

  useEffect(() => {
    if (dashboardDone && dashboardRef.current) {
      dashboardRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [dashboardDone])

  useEffect(() => {
    if (!auth.isAuthenticated) return
    api.listDatasets()
      .then(res => setDatasets(res.datasets ?? []))
      .catch(() => setDatasets([]))
      .finally(() => setPicking(false))
  }, [auth.isAuthenticated])

  // Redirect to login if not authenticated — also fires after logout
  if (!auth.isAuthenticated) return <Navigate to="/login" replace />

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
    dasher.reset()
    setPhase('wizard')
  }

  async function handleDeleteDataset(datasetId) {
    await api.deleteDataset(datasetId)
    setDatasets(prev => prev.filter(d => d.dataset_id !== datasetId))
  }

  function handleGoHome() {
    api.listDatasets()
      .then(res => setDatasets(res.datasets ?? []))
      .catch(() => {})
    setPhase('pick')
  }

  const Header = () => (
    <header className="border-b border-neutral-200 dark:border-neutral-800 px-8 py-4 flex items-center justify-between sticky top-0 bg-white dark:bg-neutral-950 z-10">
      <div className="flex items-center gap-3">
        <div className="w-5 h-5 bg-amber-400 rounded-sm rotate-45 shrink-0" />
        <span className="font-mono text-sm tracking-widest uppercase text-neutral-500 dark:text-neutral-400">
          Dasher
        </span>
      </div>
      <div className="flex items-center gap-4">
        {phase === 'wizard' && (
          <button
            onClick={handleGoHome}
            className="flex items-center gap-1.5 font-mono text-xs text-neutral-400 hover:text-amber-400 transition-colors tracking-wider uppercase group"
          >
            <span className="group-hover:-translate-x-0.5 transition-transform duration-150">←</span>
            <span>Home</span>
          </button>
        )}
        <span className="font-mono text-xs text-neutral-500 dark:text-neutral-400">
          {auth.user?.username}
        </span>
        <button
          onClick={auth.logout}
          className="font-mono text-xs text-neutral-500 hover:text-amber-400 transition-colors tracking-wider uppercase"
        >
          Sign out
        </button>
        <button
          onClick={() => setDark(d => !d)}
          className="w-8 h-8 flex items-center justify-center rounded border border-neutral-200 dark:border-neutral-800 hover:border-amber-400 dark:hover:border-amber-400 transition-colors"
          title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          <span className="text-neutral-400 text-xs">{dark ? '☀' : '☾'}</span>
        </button>
      </div>
    </header>
  )

  if (phase === 'pick') {
    return (
      <div className={dark ? 'dark' : ''}>
        <div className="min-h-screen bg-white dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 transition-colors duration-300">
          <Header />
          <div className="max-w-xl mx-auto px-8 py-16">
            <h1 className="font-mono text-xs tracking-widest uppercase text-neutral-400 mb-1">
              AI-Enabled Dashboarding
            </h1>
            <p className="font-mono text-2xl text-neutral-900 dark:text-neutral-100 mb-10">
              Continue a dataset or start fresh
            </p>
            {picking ? (
              <p className="font-mono text-xs text-neutral-500 animate-pulse">Loading datasets...</p>
            ) : (
              <div className="flex flex-col gap-2">
                {datasets.length === 0 && (
                  <p className="font-mono text-xs text-neutral-600 mb-2">No datasets yet.</p>
                )}
                {datasets.map(ds => (
                  <div key={ds.dataset_id} className="flex items-center gap-2">
                    <button
                      onClick={() => handlePickDataset(ds.dataset_id)}
                      className="flex-1 text-left px-4 py-3 rounded border border-neutral-200 dark:border-neutral-800 hover:border-amber-400 dark:hover:border-amber-400 hover:bg-amber-400/5 font-mono text-sm transition-all duration-150"
                    >
                      <span className="text-neutral-900 dark:text-neutral-100">{ds.original_filename}</span>
                      <span className="ml-3 text-xs text-neutral-400">{ds.dataset_id.slice(0, 8)}</span>
                    </button>
                    <button
                      onClick={() => handleDeleteDataset(ds.dataset_id)}
                      title="Delete dataset"
                      className="w-9 h-9 flex items-center justify-center rounded border border-transparent hover:border-red-500/40 hover:text-red-400 font-mono text-xs text-neutral-500 transition-all duration-150"
                    >
                      ✕
                    </button>
                  </div>
                ))}
                <button
                  onClick={handleStartFresh}
                  className="mt-4 text-left px-4 py-3 rounded border border-dashed border-neutral-300 dark:border-neutral-700 hover:border-amber-400 dark:hover:border-amber-400 hover:bg-amber-400/5 font-mono text-sm text-neutral-400 hover:text-amber-400 transition-all duration-150"
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

  return (
    <div className={dark ? 'dark' : ''}>
      <div className="min-h-screen bg-white dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 transition-colors duration-300">
        <Header />
        <div className="max-w-5xl mx-auto px-8 py-10 flex gap-16">
          <nav className="flex flex-col gap-6 pt-1 shrink-0 w-36">
            {STEPS.map(step => {
              const isDone   = status[step.key] === 'done'
              const isActive = step.key === activeStep
              const isLocked = !isDone && !isActive
              return (
                <button
                  key={step.key}
                  disabled={!isDone}
                  onClick={() => isDone && toggleExpanded(step.key)}
                  title={isDone ? 'Click to expand / collapse' : undefined}
                  className={`flex items-center gap-3 text-left transition-opacity duration-150 ${isDone ? 'cursor-pointer' : 'cursor-default'} ${isLocked ? 'opacity-40' : ''}`}
                >
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 font-mono text-xs transition-all duration-300 ${isDone ? 'bg-amber-400 text-neutral-950' : ''} ${isActive ? 'border-2 border-amber-400 text-amber-400' : ''} ${isLocked ? 'border border-neutral-300 dark:border-neutral-700 text-neutral-400' : ''}`}>
                    {isDone ? '✓' : step.number}
                  </div>
                  <span className={`font-mono text-xs tracking-wider uppercase leading-tight ${isActive ? 'text-neutral-900 dark:text-neutral-100' : ''} ${isDone ? 'text-neutral-400 dark:text-neutral-500' : ''} ${isLocked ? 'text-neutral-300 dark:text-neutral-700' : ''}`}>
                    {step.label}
                  </span>
                </button>
              )
            })}
          </nav>
          <main className="flex-1 min-w-0 space-y-1">
            <UploadStep    dasher={dasher} isActive={activeStep === 'upload'}    isExpanded={expandedSteps.has('upload')}    onToggle={() => toggleExpanded('upload')} />
            <SemanticsStep dasher={dasher} isActive={activeStep === 'semantics'} isExpanded={expandedSteps.has('semantics')} onToggle={() => toggleExpanded('semantics')} />
            <PlanStep      dasher={dasher} isActive={activeStep === 'plan'}      isExpanded={expandedSteps.has('plan')}      onToggle={() => toggleExpanded('plan')} />
            <DashboardStep dasher={dasher} isActive={activeStep === 'dashboard'} isExpanded={expandedSteps.has('dashboard')} onToggle={() => toggleExpanded('dashboard')} />
          </main>
        </div>
      </div>
    </div>
  )
}