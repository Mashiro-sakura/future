<template>
  <view class="page home">
    <!-- 顶栏 -->
    <view class="topbar">
      <view class="brand">
        <text class="title">期现分析</text>
        <text class="session">{{ sessionText }}</text>
      </view>
      <view class="top-actions">
        <button class="ghost-btn" :loading="subscribeLoading" @tap="subscribeDaily">订阅</button>
        <button class="ghost-btn accent" @tap="loadData">刷新</button>
      </view>
    </view>

    <!-- Ticker 行情条 -->
    <scroll-view scroll-x class="ticker" :show-scrollbar="false" enhanced>
      <view
        v-for="item in overview.products"
        :key="item.code"
        class="tick"
        :class="{ active: item.code === state.code }"
        @tap="selectProduct(item.code)"
      >
        <text class="t-code">{{ item.code }}</text>
        <text class="t-price num">{{ money(displayOf(item).price) }}</text>
        <text class="t-chg num" :class="tone(displayOf(item).chg)">{{ pct(displayOf(item).chg) }}</text>
      </view>
    </scroll-view>

    <!-- Hero -->
    <view class="panel hero" v-if="current">
      <view class="hero-head">
        <view class="hero-id">
          <text class="hero-code">{{ current.code }}</text>
          <text class="hero-name">{{ current.name }}</text>
        </view>
        <view class="hero-right">
          <text class="hero-contract">{{ contractText }}</text>
          <text class="live-tag" :class="state.liveOn ? 'on' : 'off'">{{ state.liveOn ? 'LIVE' : '已收盘' }}</text>
        </view>
      </view>
      <view class="hero-price-row">
        <text class="hero-price num" :class="{ flash: priceFlash }">{{ money(displayOf(current).price) }}</text>
        <text class="hero-chg num" :class="tone(displayOf(current).chg)">{{ pct(displayOf(current).chg) }}</text>
      </view>
      <text class="quote-note">{{ quoteNote }}</text>
      <view class="stat-grid">
        <view class="stat">
          <text class="s-label">现货</text>
          <text class="s-value num">{{ money(current.spot_price) }}</text>
          <text class="s-sub num" :class="tone(current.spot_change_pct)">{{ pct(current.spot_change_pct) }}</text>
        </view>
        <view class="stat">
          <text class="s-label">基差</text>
          <text class="s-value num">{{ current.basis_value === null ? '-' : signed(current.basis_value) }}</text>
          <text class="s-sub">{{ basisLabel }}</text>
        </view>
        <view class="stat">
          <text class="s-label">持仓量</text>
          <text class="s-value num">{{ wan(liveOf(current.code)?.open_interest ?? state.trendLast?.open_interest) }}</text>
          <text class="s-sub num" :class="tone(current.open_interest_change_pct)">{{ pct(current.open_interest_change_pct) }}</text>
        </view>
        <view class="stat">
          <text class="s-label">成交量</text>
          <text class="s-value num">{{ wan(liveOf(current.code)?.volume ?? state.trendLast?.volume) }}</text>
          <text class="s-sub">手</text>
        </view>
      </view>
      <view class="pctile" v-if="snapshot && snapshot.percentile !== null && snapshot.percentile !== undefined">
        <view class="pctile-head">
          <text>基差分位（近一年）</text>
          <text class="p-zone">{{ snapshot.zone }} · {{ snapshot.percentile }}%</text>
        </view>
        <view class="pctile-track">
          <view class="pctile-marker" :style="{ left: `calc(${Math.min(Math.max(snapshot.percentile, 0), 100)}% - 2rpx)` }" />
        </view>
        <text class="pctile-note">当前基差 {{ signed(snapshot.basis_value) }}（{{ snapshot.basis_label }}），高于近一年 {{ snapshot.percentile }}% 的交易日（样本 {{ snapshot.sample_days }} 天{{ snapshot.data_stale ? '，数据停更' : '' }}）</text>
      </view>
      <view class="pctile" v-if="volSnap && volSnap.iv_percentile !== null && volSnap.iv_percentile !== undefined">
        <view class="pctile-head">
          <text>波动率分位（近一年）</text>
          <text class="p-zone">{{ volSnap.zone }} · {{ volSnap.iv_percentile }}%</text>
        </view>
        <view class="pctile-track">
          <view class="pctile-marker" :style="{ left: `calc(${Math.min(Math.max(volSnap.iv_percentile, 0), 100)}% - 2rpx)` }" />
        </view>
        <text class="pctile-note">平值隐含波动率 {{ volSnap.atm_iv }}%（标的 {{ volSnap.underlying_month }}），高于近一年 {{ volSnap.iv_percentile }}% 的交易日；20 日历史波动率 {{ volSnap.hv20 === null ? '-' : volSnap.hv20 + '%' }}{{ volSpreadText }}（样本 {{ volSnap.sample_days }} 天）</text>
      </view>
    </view>

    <!-- 品种表 -->
    <view class="panel board">
      <view class="board-row head">
        <text>品种</text>
        <text class="col-r">最新价</text>
        <text class="col-r">涨跌</text>
        <text class="col-r">基差</text>
      </view>
      <view
        v-for="item in overview.products"
        :key="item.code"
        class="board-row"
        :class="{ active: item.code === state.code }"
        @tap="selectProduct(item.code)"
      >
        <view class="b-code">
          <text>{{ item.code }}</text>
          <text class="b-name">{{ item.name }}</text>
        </view>
        <text class="b-price num col-r">{{ money(displayOf(item).price) }}</text>
        <text class="b-chg num col-r" :class="tone(displayOf(item).chg)">{{ pct(displayOf(item).chg) }}</text>
        <view class="b-basis col-r">
          <text class="num">{{ item.basis_value === null ? '现货' : signed(item.basis_value) }}</text>
          <text class="b-zone">{{ basisZoneOf(item) }}</text>
        </view>
      </view>
    </view>

    <!-- 日报入口 + 摘要 -->
    <view class="panel report-entry" v-if="overview.latest_report" @tap="openReport(overview.latest_report.id)">
      <text class="r-title">{{ overview.latest_report.title }}</text>
      <text class="r-link">日报 ›</text>
    </view>
    <view class="panel summary" v-if="overview.latest_report">
      <text class="section-title">行情摘要</text>
      <text class="summary-text">{{ overview.latest_report.market_summary }}</text>
    </view>

    <text class="disclaimer">结构描述，非买卖指令</text>
  </view>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { onHide, onShow, onUnload } from '@dcloudio/uni-app'
import {
  createMiniappSubscription,
  getBasisDetail,
  getMiniappSubscribeConfig,
  getOverview,
  getRealtime,
  getTrend,
  getVolatility
} from '../../utils/api'

const overview = reactive({ latest_report: null, products: [] })
const state = reactive({ code: 'PTA', live: {}, liveOn: false, trendLast: null })
const quoteNote = ref('已收盘 · 显示最近交易日收盘数据')
const snapshot = ref(null)
const volSnap = ref(null)
const volSpreadText = computed(() => {
  const s = volSnap.value?.iv_hv_spread
  return s === null || s === undefined ? '' : `，IV-HV 利差 ${s > 0 ? '+' : ''}${s}`
})
const priceFlash = ref(false)
const subscribeLoading = ref(false)
const subscribeConfig = ref(null)

const sessionText = computed(() => {
  const session = overview.latest_report?.session_name
  const label = session === 'morning' ? '早报' : session === 'evening' ? '晚报' : '日报'
  return `${label} · ${String(overview.latest_report?.report_date || '').slice(5)}`
})

const current = computed(() => overview.products.find((item) => item.code === state.code) || null)
const contractText = computed(() => {
  const live = state.live[state.code]
  const contract = live?.contract_code || current.value?.futures_contract
  return contract ? `主力 ${contract}` : '现货品种'
})
const basisLabel = computed(() => {
  const v = current.value?.basis_value
  if (v === null || v === undefined) return '无基差'
  return v > 10 ? '现货升水' : v < -10 ? '现货贴水' : '平水'
})

function money(value) {
  if (value === null || value === undefined) return '-'
  return Number(value).toLocaleString()
}

function pct(value) {
  if (value === null || value === undefined) return '-'
  return `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(2)}%`
}

function signed(value) {
  if (value === null || value === undefined) return '-'
  return Number(value) > 0 ? `+${value}` : String(value)
}

function tone(value) {
  if (Number(value) > 0) return 'up'
  if (Number(value) < 0) return 'down'
  return 'flat'
}

function wan(value) {
  if (value === null || value === undefined) return '-'
  const n = Number(value)
  return Math.abs(n) >= 100000 ? `${(n / 10000).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}万` : n.toLocaleString()
}

function basisZoneOf(item) {
  if (item.basis_value === null || item.basis_value === undefined) return ''
  return item.basis_value > 10 ? '升水' : item.basis_value < -10 ? '贴水' : '平水'
}

function liveOf(code) {
  return state.live[code] || null
}

// 展示口径：有 live 用 live（基准=昨收），否则回落库内日线
function displayOf(item) {
  const live = state.live[item.code]
  if (live && live.price !== null && live.price !== undefined) {
    return { price: live.price, chg: live.change_pct }
  }
  const price = item.futures_close ?? item.spot_price
  const chg = item.futures_close != null ? item.futures_change_pct : item.spot_change_pct
  return { price, chg }
}

/* ── 盘中准实时（档1：10s 轮询，交易时段才启动） ── */
function isTradingNow() {
  const now = new Date()
  const day = now.getDay()
  if (day === 0 || day === 6) return false
  const hm = now.getHours() * 100 + now.getMinutes()
  return (hm >= 900 && hm <= 1015) || (hm >= 1030 && hm <= 1130) || (hm >= 1330 && hm <= 1500) || (hm >= 2100 && hm <= 2330)
}

let liveTimer = null

async function pollRealtime() {
  const quotes = await getRealtime()
  if (!Array.isArray(quotes)) return
  const before = state.live[state.code]?.price
  state.live = Object.fromEntries(quotes.map((q) => [q.code, q]))
  const now = new Date()
  const hhmmss = [now.getHours(), now.getMinutes(), now.getSeconds()].map((n) => String(n).padStart(2, '0')).join(':')
  quoteNote.value = `盘中快照 · 延迟约10秒 · 更新于 ${hhmmss}`
  const after = state.live[state.code]?.price
  if (before !== after && after !== null && after !== undefined) {
    priceFlash.value = false
    setTimeout(() => {
      priceFlash.value = true
      setTimeout(() => {
        priceFlash.value = false
      }, 700)
    }, 20)
  }
}

function startRealtimeLoop() {
  const on = isTradingNow()
  state.liveOn = on
  quoteNote.value = on ? '盘中快照 · 延迟约10秒 · 等待首次更新' : '已收盘 · 显示最近交易日收盘数据'
  if (on && !liveTimer) {
    pollRealtime()
    liveTimer = setInterval(pollRealtime, 10000)
  }
  if (!on && liveTimer) {
    clearInterval(liveTimer)
    liveTimer = null
  }
}

async function selectProduct(code) {
  state.code = code
  snapshot.value = null
  volSnap.value = null
  state.trendLast = null
  try {
    const [detail, trend, vol] = await Promise.all([getBasisDetail(code), getTrend(code, 5), getVolatility(code)])
    snapshot.value = detail?.snapshot || null
    volSnap.value = vol || null
    state.trendLast = Array.isArray(trend) && trend.length ? trend[trend.length - 1] : null
  } catch (error) {
    snapshot.value = null
    volSnap.value = null
  }
}

async function loadData() {
  const data = await getOverview()
  overview.latest_report = data.latest_report
  overview.products = data.products || []
  if (!overview.products.some((item) => item.code === state.code)) {
    state.code = overview.products[0]?.code || 'PTA'
  }
  await selectProduct(state.code)
  startRealtimeLoop()
}

async function loadSubscribeConfig() {
  try {
    subscribeConfig.value = await getMiniappSubscribeConfig()
  } catch (error) {
    subscribeConfig.value = { enabled: false, message: '订阅消息服务暂不可用' }
  }
}

function getWeixinLoginCode() {
  return new Promise((resolve, reject) => {
    uni.login({
      provider: 'weixin',
      success: (result) => (result.code ? resolve(result.code) : reject(new Error('未获取到微信登录凭证'))),
      fail: reject
    })
  })
}

function requestSubscribe(templateId) {
  return new Promise((resolve, reject) => {
    uni.requestSubscribeMessage({
      tmplIds: [templateId],
      success: resolve,
      fail: reject
    })
  })
}

async function subscribeDaily() {
  // #ifdef MP-WEIXIN
  if (subscribeLoading.value) return
  subscribeLoading.value = true
  try {
    const config = subscribeConfig.value
    if (!config?.enabled || !config.template_id) {
      throw new Error(config?.message || '订阅消息尚未配置')
    }
    const [code, result] = await Promise.all([getWeixinLoginCode(), requestSubscribe(config.template_id)])
    if (result[config.template_id] !== 'accept') {
      uni.showToast({ title: '未授权日报提醒', icon: 'none' })
      return
    }
    const subscription = await createMiniappSubscription({ code, template_id: config.template_id })
    uni.showToast({ title: subscription.message || '订阅成功', icon: 'success' })
  } catch (error) {
    uni.showToast({ title: error.message || '订阅失败，请稍后重试', icon: 'none' })
  } finally {
    subscribeLoading.value = false
  }
  // #endif

  // #ifndef MP-WEIXIN
  uni.showToast({ title: '请在微信小程序中订阅日报提醒', icon: 'none' })
  // #endif
}

function openReport(id) {
  if (!id) return
  uni.navigateTo({ url: `/pages/report/detail?id=${id}` })
}

onMounted(() => {
  loadData()
  loadSubscribeConfig()
})

onShow(() => {
  startRealtimeLoop()
})

onHide(() => {
  if (liveTimer) {
    clearInterval(liveTimer)
    liveTimer = null
  }
})

onUnload(() => {
  if (liveTimer) {
    clearInterval(liveTimer)
    liveTimer = null
  }
})
</script>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.num {
  font-variant-numeric: tabular-nums;
}

.up { color: #f0455c; }
.down { color: #0dbf7e; }
.flat { color: #5d6779; }

/* 顶栏 */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 24rpx;
  border: 1rpx solid #1f2637;
  border-radius: 8rpx;
  background: #0d1220;
}

.brand {
  display: flex;
  align-items: baseline;
  gap: 14rpx;
}

.title {
  color: #e6eaf2;
  font-size: 34rpx;
  font-weight: 700;
  letter-spacing: 2rpx;
}

.session {
  color: #7ea8f0;
  font-size: 20rpx;
}

.top-actions {
  display: flex;
  gap: 12rpx;
}

.ghost-btn {
  width: 96rpx;
  height: 52rpx;
  margin: 0;
  border: 1rpx solid #2a3449;
  border-radius: 6rpx;
  background: transparent;
  color: #a7b0c2;
  font-size: 22rpx;
  line-height: 52rpx;
}

.ghost-btn.accent {
  border-color: #4f8ff7;
  color: #4f8ff7;
}

/* Ticker */
.ticker {
  white-space: nowrap;
  border: 1rpx solid #1f2637;
  border-radius: 8rpx;
  background: #131826;
}

.tick {
  display: inline-flex;
  align-items: baseline;
  padding: 14rpx 24rpx;
  border-right: 1rpx solid #1a2133;
}

.tick.active {
  background: #161c30;
  box-shadow: 0 -3rpx 0 #4f8ff7 inset;
}

.t-code {
  color: #a7b0c2;
  font-size: 21rpx;
  font-weight: 700;
  letter-spacing: 1rpx;
}

.t-price {
  margin-left: 10rpx;
  color: #e6eaf2;
  font-size: 22rpx;
  font-weight: 600;
}

.t-chg {
  margin-left: 10rpx;
  font-size: 21rpx;
}

/* Hero */
.hero {
  padding: 28rpx 28rpx 24rpx;
}

.hero-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.hero-id {
  display: flex;
  align-items: baseline;
  gap: 16rpx;
}

.hero-code {
  color: #e6eaf2;
  font-size: 44rpx;
  font-weight: 800;
  letter-spacing: 2rpx;
}

.hero-name {
  color: #5d6779;
  font-size: 22rpx;
}

.hero-right {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.hero-contract {
  padding: 4rpx 14rpx;
  border: 1rpx solid #1f2637;
  border-radius: 4rpx;
  color: #7ea8f0;
  font-size: 20rpx;
}

.live-tag {
  padding: 4rpx 10rpx;
  border-radius: 4rpx;
  font-size: 17rpx;
  font-weight: 700;
  letter-spacing: 1rpx;
}

.live-tag.on {
  background: rgba(240, 69, 92, 0.15);
  color: #f0455c;
}

.live-tag.off {
  background: #161c30;
  color: #5d6779;
}

.hero-price-row {
  display: flex;
  align-items: flex-end;
  gap: 20rpx;
  margin-top: 16rpx;
}

.hero-price {
  color: #e6eaf2;
  font-size: 88rpx;
  font-weight: 800;
  line-height: 1;
}

.hero-price.flash {
  color: #4f8ff7;
  transition: color 0.7s ease-out;
}

.quote-note {
  display: block;
  margin-top: 10rpx;
  color: #5d6779;
  font-size: 19rpx;
}

.hero-chg {
  margin-bottom: 8rpx;
  padding: 6rpx 14rpx;
  border-radius: 4rpx;
  font-size: 26rpx;
  font-weight: 700;
}

.hero-chg.up { background: rgba(240, 69, 92, 0.14); }
.hero-chg.down { background: rgba(13, 191, 126, 0.12); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rpx;
  margin-top: 28rpx;
  border: 1rpx solid #1a2133;
  border-radius: 6rpx;
  overflow: hidden;
  background: #1a2133;
}

.stat {
  padding: 16rpx 18rpx;
  background: #161c30;
}

.s-label {
  display: block;
  color: #5d6779;
  font-size: 19rpx;
}

.s-value {
  display: block;
  margin-top: 8rpx;
  color: #e6eaf2;
  font-size: 26rpx;
  font-weight: 700;
}

.s-sub {
  display: block;
  margin-top: 4rpx;
  color: #5d6779;
  font-size: 18rpx;
}

/* 基差分位 */
.pctile {
  margin-top: 24rpx;
}

.pctile-head {
  display: flex;
  justify-content: space-between;
  color: #5d6779;
  font-size: 19rpx;
}

.p-zone {
  font-weight: 700;
  color: #a7b0c2;
}

.pctile-track {
  position: relative;
  height: 10rpx;
  margin-top: 10rpx;
  border-radius: 5rpx;
  background: linear-gradient(90deg, #14362b 0%, #1a2130 35%, #1a2130 65%, #3a2030 100%);
}

.pctile-marker {
  position: absolute;
  top: -5rpx;
  width: 3rpx;
  height: 20rpx;
  border-radius: 2rpx;
  background: #4f8ff7;
}

.pctile-note {
  display: block;
  margin-top: 10rpx;
  color: #5d6779;
  font-size: 19rpx;
}

/* 品种表 */
.board {
  overflow: hidden;
}

.board-row {
  display: grid;
  grid-template-columns: 1.05fr 1fr 0.85fr 1.05fr;
  align-items: center;
  padding: 18rpx 22rpx;
  border-top: 1rpx solid #1a2133;
}

.board-row.head {
  padding: 14rpx 22rpx;
  border-top: 0;
  color: #5d6779;
  font-size: 19rpx;
}

.board-row.active {
  background: #161c30;
  box-shadow: 3rpx 0 0 #4f8ff7 inset;
}

.col-r {
  text-align: right;
}

.b-code text {
  color: #e6eaf2;
  font-size: 26rpx;
  font-weight: 700;
}

.b-name {
  display: block;
  color: #5d6779;
  font-size: 18rpx;
  font-weight: 400;
}

.b-price,
.b-chg {
  font-size: 24rpx;
  font-weight: 600;
}

.b-basis text {
  color: #e6eaf2;
  font-size: 24rpx;
  font-weight: 600;
}

.b-zone {
  display: block;
  color: #5d6779;
  font-size: 17rpx;
  font-weight: 400;
}

/* 日报/摘要 */
.report-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 24rpx;
}

.r-title {
  overflow: hidden;
  color: #a7b0c2;
  font-size: 23rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-link {
  flex-shrink: 0;
  color: #4f8ff7;
  font-size: 21rpx;
  font-weight: 700;
}

.summary {
  padding: 22rpx 24rpx;
}

.section-title {
  display: block;
  color: #e6eaf2;
  font-size: 26rpx;
  font-weight: 700;
}

.summary-text {
  display: block;
  margin-top: 14rpx;
  color: #a7b0c2;
  font-size: 23rpx;
  line-height: 1.8;
  white-space: pre-wrap;
}

.disclaimer {
  padding: 4rpx 0 20rpx;
  color: #5d6779;
  font-size: 19rpx;
  text-align: center;
}
</style>
