import { useState } from 'react'
import { api } from '../lib/api'

// Each step has a status. This drives what the UI shows.
// idle    → not started yet
// loading → request in flight
// done    → completed successfully  
// error   → something went wrong

const initialStatus = {
  upload: 'idle',
  semantics: 'idle',
  plan: 'idle',
  dashboard: 'idle',
}

export function useDasher() {
  // Core pipeline data — gets filled in step by step
  const [datasetId, setDatasetId] = useState(null)
  const [uploadResult, setUploadResult] = useState(null)
  const [semantics, setSemantics] = useState(null)
  const [plan, setPlan] = useState(null)
  const [dashboardResult, setDashboardResult] = useState(null)

  // Per-step status and error messages
  const [status, setStatus] = useState(initialStatus)
  const [errors, setErrors] = useState({})

  // Helper — update one step's status without touching the others.
  // The ...prev spread means "keep everything else the same"
  const setStepStatus = (step, value) =>
    setStatus(prev => ({ ...prev, [step]: value }))

  const setStepError = (step, message) =>
    setErrors(prev => ({ ...prev, [step]: message }))

  // ── Step 1: Upload ──────────────────────────────────────────
  async function upload(file, businessHint) {
    setStepStatus('upload', 'loading')
    setStepError('upload', null)
    try {
      const result = await api.uploadCsv(file)
      setUploadResult(result)
      setDatasetId(result.dataset_id)
      setStepStatus('upload', 'done')
    } catch (e) {
      setStepStatus('upload', 'error')
      setStepError('upload', e.message)
    }
  }

  // ── Step 2: Semantics ───────────────────────────────────────
  async function inferSemantics(businessHint) {
    if (!datasetId) return
    setStepStatus('semantics', 'loading')
    setStepError('semantics', null)
    try {
      const result = await api.inferSemantics(datasetId, businessHint)
      setSemantics(result)
      setStepStatus('semantics', 'done')
    } catch (e) {
      setStepStatus('semantics', 'error')
      setStepError('semantics', e.message)
    }
  }

  // ── Step 3: Dashboard Plan ──────────────────────────────────
  async function generatePlan() {
    if (!datasetId) return
    setStepStatus('plan', 'loading')
    setStepError('plan', null)
    try {
      const result = await api.generatePlan(datasetId)
      setPlan(result)
      setStepStatus('plan', 'done')
    } catch (e) {
      setStepStatus('plan', 'error')
      setStepError('plan', e.message)
    }
  }

  // ── Step 4: Create Metabase Dashboard ──────────────────────
  async function createDashboard() {
    if (!datasetId) return
    setStepStatus('dashboard', 'loading')
    setStepError('dashboard', null)
    try {
      const result = await api.createDashboard(datasetId)
      setDashboardResult(result)
      setStepStatus('dashboard', 'done')
    } catch (e) {
      setStepStatus('dashboard', 'error')
      setStepError('dashboard', e.message)
    }
  }

  // Get prior states of datasets
  async function rehydrate(id) {
  try {
    const state = await api.getDatasetState(id)
    const { upload_result, semantics: sem, plan: pl, dashboard_result } = state

    setDatasetId(id)
    setUploadResult(upload_result)
    setSemantics(sem)
    setPlan(pl)
    setDashboardResult(dashboard_result)

    setStatus({
      upload:    upload_result    ? 'done' : 'idle',
      semantics: sem              ? 'done' : 'idle',
      plan:      pl               ? 'done' : 'idle',
      dashboard: dashboard_result ? 'done' : 'idle',
    })
  } catch (e) {
    // If state fetch fails, just start fresh — don't block the user
    console.error('Rehydrate failed:', e.message)
  }
}

  // Everything a component might need, returned as one object
  return {
    // Data
    datasetId,
    uploadResult,
    semantics,
    plan,
    dashboardResult,
    // Status per step
    status,
    errors,
    // Actions
    upload,
    inferSemantics,
    generatePlan,
    createDashboard,
    rehydrate
  }
}