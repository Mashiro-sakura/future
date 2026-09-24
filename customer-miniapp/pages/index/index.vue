<template>
  <view class="page home">
    <view class="top">
      <view>
        <text class="eyebrow">{{ sessionText }} · {{ todayText }}</text>
        <text class="title">期现分析</text>
      </view>
      <view class="top-actions">
        <button class="ghost-btn" :loading="subscribeLoading" @tap="subscribeDaily">订阅</button>
        <button class="ghost-btn accent" @tap="loadData">刷新</button>
      </view>
    </view>

    <view class="report panel" v-if="overview.latest_report" @tap="openReport(overview.latest_report.id)">
      <view class="report-main">
        <text class="report-title">{{ overview.latest_report.title }}</text>
        <text class="report-date">{{ overview.latest_report.report_date }}</text>
      </view>
      <text class="report-action">查看日报 ›</text>
    </view>

    <view class="grid">
      <view v-for="item in overview.products" :key="item.code" class="product panel" @tap="openProduct(item)">
        <view class="product-head">
          <view class="product-id">
            <text class="code">{{ item.code }}</text>
            <text class="name">{{ item.name }}</text>
          </view>
          <text class="contract">{{ contractText(item) }}</text>
        </view>
        <view class="price-row">
          <view class="price-cell">
            <text class="label">{{ item.futures_contract ? '期货' : '期货不适用' }}</text>
            <text class="value num">{{ money(item.futures_close) }}</text>
            <text class="change num" :class="tone(item.futures_change_pct)">{{ pct(item.futures_change_pct) }}</text>
          </view>
          <view class="price-cell">
            <text class="label">现货</text>
            <text class="value num">{{ money(item.spot_price) }}</text>
            <text class="change num" :class="tone(item.spot_change_pct)">{{ pct(item.spot_change_pct) }}</text>
          </view>
        </view>
        <view class="meta-row">
          <text class="chip">{{ item.futures_contract ? `基差 ${signed(item.basis_value)}` : '无期货基差' }}</text>
          <text class="chip">{{ item.futures_contract ? `持仓 ${pct(item.open_interest_change_pct)}` : '现货跟踪' }}</text>
        </view>
      </view>
    </view>

    <view class="summary panel" v-if="overview.latest_report">
      <text class="section-title">行情摘要</text>
      <text class="summary-text">{{ overview.latest_report.market_summary }}</text>
    </view>

    <text class="disclaimer">结构描述，非买卖指令</text>
  </view>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { createMiniappSubscription, getMiniappSubscribeConfig, getOverview } from '../../utils/api'

const overview = reactive({
  latest_report: null,
  products: []
})
const subscribeLoading = ref(false)
const subscribeConfig = ref(null)

const sessionText = computed(() => {
  const session = overview.latest_report?.session_name
  return session === 'morning' ? '早报' : session === 'evening' ? '晚报' : '日报'
})

const todayText = computed(() => {
  const now = new Date()
  return `${now.getMonth() + 1}/${now.getDate()}`
})

function money(value) {
  if (value === null || value === undefined) return '-'
  return Number(value).toLocaleString()
}

function pct(value) {
  if (value === null || value === undefined) return '-'
  const prefix = Number(value) > 0 ? '+' : ''
  return `${prefix}${Number(value).toFixed(2)}%`
}

function signed(value) {
  if (value === null || value === undefined) return '-'
  return Number(value) > 0 ? `+${value}` : String(value)
}

function tone(value) {
  if (Number(value) > 0) return 'positive'
  if (Number(value) < 0) return 'negative'
  return ''
}

function contractText(item) {
  return item.futures_contract ? `主力 ${item.futures_contract}` : '现货品种'
}

async function loadData() {
  const data = await getOverview()
  overview.latest_report = data.latest_report
  overview.products = data.products || []
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
      success: (result) => result.code ? resolve(result.code) : reject(new Error('未获取到微信登录凭证')),
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

function openProduct(item) {
  uni.navigateTo({
    url: `/pages/product/detail?code=${item.code}&name=${encodeURIComponent(item.name)}`
  })
}

function openReport(id) {
  if (!id) return
  uni.navigateTo({ url: `/pages/report/detail?id=${id}` })
}

onMounted(() => {
  loadData()
  loadSubscribeConfig()
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
  letter-spacing: 0.5rpx;
}

.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 26rpx;
  border: 1rpx solid #1f2637;
  border-radius: 8rpx;
  background: #0d1322;
}

.eyebrow {
  display: block;
  color: #7ea8f0;
  font-size: 22rpx;
}

.title {
  display: block;
  margin-top: 6rpx;
  color: #e6eaf2;
  font-size: 40rpx;
  font-weight: 700;
  letter-spacing: 1rpx;
}

.top-actions {
  display: flex;
  gap: 12rpx;
}

.ghost-btn {
  width: 104rpx;
  height: 56rpx;
  margin: 0;
  border: 1rpx solid #2a3449;
  border-radius: 6rpx;
  background: transparent;
  color: #a7b0c2;
  font-size: 22rpx;
  line-height: 56rpx;
}

.ghost-btn.accent {
  border-color: #4f8ff7;
  color: #4f8ff7;
}

.report {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22rpx 24rpx;
}

.report-main {
  min-width: 0;
}

.report-title {
  display: block;
  max-width: 520rpx;
  overflow: hidden;
  color: #e6eaf2;
  font-size: 28rpx;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.report-date {
  display: block;
  margin-top: 6rpx;
  color: #5d6779;
  font-size: 22rpx;
}

.report-action {
  flex-shrink: 0;
  color: #4f8ff7;
  font-size: 22rpx;
}

.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16rpx;
}

.product {
  padding: 22rpx 24rpx;
}

.product-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16rpx;
  padding-bottom: 16rpx;
  border-bottom: 1rpx solid #1f2637;
}

.product-id {
  display: flex;
  align-items: baseline;
  gap: 14rpx;
}

.code {
  color: #e6eaf2;
  font-size: 34rpx;
  font-weight: 700;
  letter-spacing: 1rpx;
}

.name {
  color: #5d6779;
  font-size: 22rpx;
}

.contract {
  color: #7ea8f0;
  font-size: 21rpx;
  font-variant-numeric: tabular-nums;
}

.price-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18rpx;
  margin-top: 20rpx;
}

.label {
  display: block;
  color: #5d6779;
  font-size: 21rpx;
}

.value {
  display: block;
  margin-top: 6rpx;
  color: #e6eaf2;
  font-size: 36rpx;
  font-weight: 700;
}

.change {
  display: block;
  margin-top: 2rpx;
  color: #7d879c;
  font-size: 22rpx;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-top: 20rpx;
}

.chip {
  padding: 6rpx 14rpx;
  border: 1rpx solid #232b3d;
  border-radius: 4rpx;
  background: #1a2130;
  color: #a7b0c2;
  font-size: 21rpx;
  font-variant-numeric: tabular-nums;
}

.summary {
  padding: 22rpx 24rpx;
}

.section-title {
  display: block;
  color: #e6eaf2;
  font-size: 28rpx;
  font-weight: 600;
}

.summary-text {
  display: block;
  margin-top: 14rpx;
  color: #c3cad9;
  font-size: 25rpx;
  line-height: 1.7;
  white-space: pre-wrap;
}

.disclaimer {
  padding: 8rpx 0 16rpx;
  color: #5d6779;
  font-size: 20rpx;
  text-align: center;
}
</style>
