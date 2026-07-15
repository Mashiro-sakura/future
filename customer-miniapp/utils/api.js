import { mockOverview, mockReports, mockTrend } from './mock'

export const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

function request(path, options = {}) {
  const { method = 'GET', data } = options
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE}${path}`,
      method,
      data,
      header: data ? { 'content-type': 'application/json' } : undefined,
      timeout: 8000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          reject(new Error(res.data?.detail || `HTTP ${res.statusCode}`))
        }
      },
      fail: reject
    })
  })
}

export async function getOverview() {
  try {
    return await request('/api/public/overview')
  } catch (error) {
    console.warn('Using mock overview', error)
    return mockOverview
  }
}

export async function getTrend(code, days = 60) {
  try {
    return await request(`/api/public/products/${code}/trend?days=${days}`)
  } catch (error) {
    console.warn('Using mock trend', error)
    return mockTrend(code)
  }
}

export async function getLatestReport() {
  try {
    return await request('/api/public/reports/latest')
  } catch (error) {
    console.warn('Using mock report', error)
    return mockOverview.latest_report
  }
}

export async function getReports(limit = 20) {
  try {
    return await request(`/api/public/reports?limit=${limit}`)
  } catch (error) {
    console.warn('Using mock reports', error)
    return mockReports
  }
}

export async function getReport(id) {
  try {
    return await request(`/api/public/reports/${id}`)
  } catch (error) {
    console.warn('Using mock report detail', error)
    return mockOverview.latest_report
  }
}

export function getMiniappSubscribeConfig() {
  return request('/api/public/wechat/subscribe-config')
}

export function createMiniappSubscription(payload) {
  return request('/api/public/wechat/subscriptions', { method: 'POST', data: payload })
}
