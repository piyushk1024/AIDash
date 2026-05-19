// Base URL prefix — all requests go through Vite's proxy to localhost:8000
const BASE = '/api'

// A small helper so we don't repeat fetch boilerplate everywhere.
// It sends a request, checks if it failed, and returns parsed JSON.
// If the server returns an error, it throws with the server's message.
async function request(method, path, body, isFormData = false) {
  const options = { method }

  if (body) {
    if (isFormData) {
      // FormData (file uploads) must NOT have Content-Type set manually —
      // the browser sets it automatically with the correct boundary
      options.body = body
    } else {
      options.headers = { 'Content-Type': 'application/json' }
      options.body = JSON.stringify(body)
    }
  }

  const res = await fetch(`${BASE}${path}`, options)

  if (!res.ok) {
    // Try to pull the error message from FastAPI's standard error shape
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }

  return res.json()
}

// One function per endpoint — mirrors your FastAPI routes exactly
export const api = {
  uploadCsv: async (file, replace = false, forceNew = false) => {
  const form = new FormData()
  form.append('file', file)
  // const url = replace ? '/upload-csv?replace=true' : '/upload-csv'
  const params = replace ? '?replace=true' : forceNew ? '?force_new=true' : ''
  // const res = await fetch(`${BASE}${url}`, { method: 'POST', body: form })
  const res = await fetch(`${BASE}/upload-csv${params}`, { method: 'POST', body: form })
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
}



