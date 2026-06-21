const BASE = '/api'
const TOKEN_KEY = 'dasher_token'

function getToken() {
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

  inferSemantics: (datasetId, businessHint) =>
    request('POST', `/infer-dataset-semantics/${datasetId}`, {
      business_hint: businessHint ?? null
    }),

  generatePlan: (datasetId) =>
    request('POST', `/generate-dashboard-plan/${datasetId}`),

  createDashboard: (datasetId) =>
    request('POST', `/create-metabase-dashboard/${datasetId}`),

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

  addNLChart: (datasetId, prompt, selectedColumns) =>
    request('POST', `/datasets/${datasetId}/dashboard/charts`, {
      prompt,
      selected_columns: selectedColumns,
    }),

  editNLChart: (datasetId, cardId, prompt, selectedColumns) =>
    request('PUT', `/datasets/${datasetId}/dashboard/charts/${cardId}`, {
      prompt,
      selected_columns: selectedColumns,
    }),

  deleteNLChart: (datasetId, cardId) =>
    request('DELETE', `/datasets/${datasetId}/dashboard/charts/${cardId}`),

  login: (username, password) =>
    request('POST', '/auth/login', { username, password }),

  register: (username, password) =>
    request('POST', '/auth/register', { username, password }),
  
  publishDashboard: (datasetId) =>
  request('POST', `/datasets/${datasetId}/publish`),

  getPublicDashboard: (datasetId) =>
    request('GET', `/datasets/${datasetId}/public`),

  runAgent: (datasetId, goal) =>
  request('POST', `/datasets/${datasetId}/dashboard/agent`, goal ? { goal } : {}),
  
}