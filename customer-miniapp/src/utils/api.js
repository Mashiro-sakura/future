import { mockBasisDetail, mockBasisOverview, mockOverview, mockReports, mockTrend } from './mock.js'

export const API_BASE = ''

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

export async function getBasisOverview() {
  try {
    return await request('/api/public/basis')
  } catch (error) {
    console.warn('Using mock basis overview', error)
    return mockBasisOverview
  }
}

export async function getBasisDetail(code, days = 30) {
  try {
    return await request(`/api/public/basis/${code}?days=${days}`)
  } catch (error) {
    console.warn('Using mock basis detail', error)
    return mockBasisDetail
  }
}

export async function getRealtime() {
  // 盘中准实时快照：失败返回 null（调用方静默跳过本次 tick，不用 mock 干扰判断）
  try {
    return await request('/api/public/realtime')
  } catch (error) {
    console.warn('Realtime unavailable', error)
    return null
  }
}

export async function getVolatility(code) {
  // 期权波动率快照：无期权数据（404）或失败返回 null（区块自动隐藏，不用 mock）
  try {
    return await request(`/api/public/volatility/${code}`)
  } catch (error) {
    console.warn('Volatility unavailable', error)
    return null
  }
}

export async function getVolumeProfile(code) {
  // 成交分布：无数据（404）或失败返回 null（面板自动隐藏，不用 mock）
  try {
    return await request(`/api/public/volume-profile/${code}`)
  } catch (error) {
    console.warn('Volume profile unavailable', error)
    return null
  }
}
