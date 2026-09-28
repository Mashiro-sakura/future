import { mockBasisDetail, mockBasisOverview, mockOverview, mockReports, mockTrend } from './mock.js'

// API 基地址按端区分（uni-app 条件编译）：
// - H5（本地 dev 走 manifest 代理 / 生产与后端同域部署）：相对路径 ''
// - 微信小程序：必须完整域名。2026-09-28 起用自定义域名，
//   zeabur.app 免费子域国内不可达已弃用
// #ifdef MP-WEIXIN
export const API_BASE = 'https://api.jd6yar.cn'
// #endif
// #ifndef MP-WEIXIN
export const API_BASE = ''
// #endif

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

export async function getPositionRank(code) {
  // 主力持仓排名：无数据（404）或失败返回 null（面板自动隐藏，不用 mock）
  try {
    return await request(`/api/public/position-rank/${code}`)
  } catch (error) {
    console.warn('Position rank unavailable', error)
    return null
  }
}

export async function getSeatRank(code) {
  // 席位白名单快照：无配置（404，如 DCE 品种）或失败返回 null（面板自动隐藏）
  try {
    return await request(`/api/public/seat-rank/${code}`)
  } catch (error) {
    console.warn('Seat rank unavailable', error)
    return null
  }
}
