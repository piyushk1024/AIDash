const BASE = '/api'
const TOKEN_KEY = 'dasher_token'
import { setQuotaState } from './quotaStore'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

function handleUnauthorized() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem('dasher_user')
  window.location.href = '/login'
}

async function request(method, path, body, isFormData = false) {
  const headers = {}

  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  if (body && !isFormData) {
    headers['Content-Type'] = 'application/json'
  }

  const options = { method, headers }
  if (body) options.body = isFormData ? body : JSON.stringify(body)

  const res = await fetch(`${BASE}${path}`, options)

  if (res.status === 401) { handleUnauthorized(); return }

  const remaining = res.headers.get('X-Quota-Remaining')
  const limit = res.headers.get('X-Quota-Limit')
  if (remaining !== null && limit !== null) {
    setQuotaState({ remaining: Number(remaining), limit: Number(limit), unlimited: false })
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }

  return res.json()
}

export const api = {
  uploadCsv: async (file, replace = false, forceNew = false) => {
    const form = new FormData()
    form.append('file', file)
    const params = replace ? '?replace=true' : forceNew ? '?force_new=true' : ''

    const headers = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`

    const res = await fetch(`${BASE}/upload-csv${params}`, {
      method: 'POST',
      headers,
      body: form,
    })

    if (res.status === 401) { handleUnauthorized(); return }
    if (res.status === 409) {
      const err = await res.json()
      return { conflict: true, existing_dataset_id: err.detail.existing_dataset_id }
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'Request failed')
    }
    return res.json()
  },

  // force lets the caller re-run inference even when a cached result with
  // the same business_hint exists (Step 9 re-run UI). Route also re-runs
  // automatically on its own if business_hint differs from the cached one.
  inferSemantics: (datasetId, businessHint, force = false) =>
    request('POST', `/infer-dataset-semantics/${datasetId}${force ? '?force=true' : ''}`, {
      business_hint: businessHint ?? null
    }),

  generatePlan: (datasetId) =>
    request('POST', `/generate-dashboard-plan/${datasetId}`),

  // Builds charts from the cached pipeline plan. Replaces the old
  // createDashboard call, which hit a Metabase-era route that no longer
  // exists post-swap.
  buildDashboard: (datasetId) =>
    request('POST', `/datasets/${datasetId}/dashboard/build`),

  profileCsv: (datasetId) =>
    request('GET', `/profile-csv/${datasetId}`),

  listDatasets: () =>
    request('GET', '/datasets'),

  getDatasetState: (datasetId) =>
    request('GET', `/datasets/${datasetId}/state`),

  deleteDataset: (datasetId) =>
    request('DELETE', `/datasets/${datasetId}`),

  askInsight: (datasetId, prompt) =>
    request('POST', `/datasets/${datasetId}/insights`, { prompt }),

  getInsights: (datasetId) =>
    request('GET', `/datasets/${datasetId}/insights`),

  deleteInsight: (datasetId, insightId) =>
    request('DELETE', `/datasets/${datasetId}/insights/${insightId}`),

  // mode targets which dashboard ("pipeline" or "agent") the chart is
  // added to/edited on. Defaults to "pipeline" to match the backend's
  // own default, but must be passed explicitly for agent-mode dashboards.
  addNLChart: (datasetId, prompt, selectedColumns, mode = 'pipeline') =>
    request('POST', `/datasets/${datasetId}/dashboard/charts`, {
      prompt,
      selected_columns: selectedColumns,
      mode,
    }),

  editNLChart: (datasetId, cardId, prompt, selectedColumns, mode = 'pipeline') =>
    request('PUT', `/datasets/${datasetId}/dashboard/charts/${cardId}`, {
      prompt,
      selected_columns: selectedColumns,
      mode,
    }),

  // mode is a query param here (route reads it via FastAPI's default
  // query-param binding), not a body field like add/edit.
  deleteNLChart: (datasetId, cardId, mode = 'pipeline') =>
    request('DELETE', `/datasets/${datasetId}/dashboard/charts/${cardId}?mode=${mode}`),

  login: async (username, password) => {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Login failed')
  }
  return res.json()
  },

  register: async (username, password) => {
    const res = await fetch(`${BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'Registration failed')
    }
    return res.json()
  },

  publishDashboard: (datasetId, mode = 'pipeline') =>
    request('POST', `/datasets/${datasetId}/publish`, { mode }),

  getPublicDashboard: (datasetId) =>
    request('GET', `/datasets/${datasetId}/public`),

  // nudge re-enters the agent loop using the existing agent-mode dashboard
  // as context instead of starting fresh. Sync (non-streaming) path.
  runAgent: (datasetId, goal, nudge = false) =>
    request('POST', `/datasets/${datasetId}/dashboard/agent`, {
      ...(goal ? { goal } : {}),
      nudge,
    }),

  // Streaming path. Returns the URL only — useEventStream owns the fetch
  // and POSTs whatever body the caller passes (e.g. { goal, nudge }).
  agentStreamUrl: (datasetId) =>
    `${BASE}/datasets/${datasetId}/dashboard/agent/stream`,
    launchStreamUrl: () => `${BASE}/datasets/launch/stream`,

  // PDF export (agent-mode only). Backend renders the report from
  // already-captured chart images (Plotly.toImage() per card, done
  // client-side) plus the stored rationale/title — it re-executes no
  // queries itself. Response is a binary PDF, not JSON, so this bypasses
  // the generic `request` helper and returns a Blob for the caller to
  // download (e.g. via URL.createObjectURL).
  getAgentReport: async (datasetId, charts) => {
    const headers = { 'Content-Type': 'application/json' }
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`

    const res = await fetch(`${BASE}/datasets/${datasetId}/report`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ charts }),
    })

    if (res.status === 401) { handleUnauthorized(); return }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'Report generation failed')
    }
    return res.blob()
  },
  submitFeedback: (type, message, datasetId = null) =>
  request('POST', '/feedback', { type, message, dataset_id: datasetId }),

  getAdminStats: () =>
    request('GET', '/admin/stats'),

  getAdminFeedback: () =>
    request('GET', '/admin/feedback'),
  getQuotaStatus: () => request('GET', '/me/quota'),
}