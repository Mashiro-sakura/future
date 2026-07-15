const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

export function getToken() {
  return localStorage.getItem('future_analysis_token') || ''
}

export function setToken(token) {
  localStorage.setItem('future_analysis_token', token)
}

export function clearToken() {
  localStorage.removeItem('future_analysis_token')
}

async function request(path, options = {}) {
  const headers = {
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers || {})
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `请求失败：${response.status}`)
  }
  return response.json()
}

export function login(username, password) {
  return request('/api/admin/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  })
}

export function syncData(days = 60) {
  return request(`/api/admin/data/sync?days=${days}`, { method: 'POST' })
}

export function generateReport(sessionName) {
  return request(`/api/admin/reports/generate?session_name=${sessionName}`, { method: 'POST' })
}

export function listReports() {
  return request('/api/admin/reports')
}

export function updateReport(id, payload) {
  return request(`/api/admin/reports/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  })
}

export function publishReport(id) {
  return request(`/api/admin/reports/${id}/publish`, { method: 'POST' })
}

export function pushReport(id) {
  return request(`/api/admin/reports/${id}/push`, { method: 'POST' })
}

export function createPolicyEvent(payload) {
  return request('/api/admin/policy-events', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function getLogs() {
  return request('/api/admin/logs')
}

export function getOverview() {
  return request('/api/public/overview')
}

export function getTrend(code, days = 60) {
  return request(`/api/public/products/${code}/trend?days=${days}`)
}

export function importSpot(file) {
  const form = new FormData()
  form.append('file', file)
  return request('/api/admin/import/spot', {
    method: 'POST',
    body: form
  })
}
