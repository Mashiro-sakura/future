<template>
  <view class="page home">
    <view class="top">
      <view>
        <text class="eyebrow">{{ sessionText }}</text>
        <text class="title">期现采购建议</text>
      </view>
      <view class="top-actions">
        <button class="subscribe" :loading="subscribeLoading" @tap="subscribeDaily">订阅日报</button>
        <button class="refresh" @tap="loadData">刷新</button>
      </view>
    </view>

    <view class="report panel" v-if="overview.latest_report" @tap="openReport(overview.latest_report.id)">
      <view class="report-main">
        <text class="report-title">{{ overview.latest_report.title }}</text>
        <text class="report-date">{{ overview.latest_report.report_date }}</text>
      </view>
      <text class="report-action">查看日报</text>
    </view>

    <view class="grid">
      <view v-for="item in overview.products" :key="item.code" class="product panel" @tap="openProduct(item)">
        <view class="product-head">
          <view>
            <text class="code">{{ item.code }}</text>
            <text class="name">{{ item.name }}</text>
            <text class="contract">{{ contractText(item) }}</text>
          </view>
          <text class="advice">{{ item.recommendation || '待更新' }}</text>
        </view>
        <view class="price-row">
          <view>
            <text class="label">{{ item.futures_contract ? '期货' : '期货不适用' }}</text>
            <text class="value">{{ money(item.futures_close) }}</text>
            <text class="change" :class="tone(item.futures_change_pct)">{{ pct(item.futures_change_pct) }}</text>
          </view>
          <view>
            <text class="label">现货</text>
            <text class="value">{{ money(item.spot_price) }}</text>
            <text class="change" :class="tone(item.spot_change_pct)">{{ pct(item.spot_change_pct) }}</text>
          </view>
        </view>
        <view class="basis-row">
          <text>{{ item.futures_contract ? `基差 ${signed(item.basis_value)}` : '无期货基差' }}</text>
          <text>{{ item.futures_contract ? `持仓 ${pct(item.open_interest_change_pct)}` : '现货跟踪' }}</text>
          <text>置信度 {{ item.confidence || '-' }}%</text>
        </view>
      </view>
    </view>

    <view class="summary panel" v-if="overview.latest_report">
      <text class="section-title">行情摘要</text>
      <text class="summary-text">{{ overview.latest_report.market_summary }}</text>
    </view>
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
  return item.futures_contract ? `主力合约 ${item.futures_contract}` : '现货品种'
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
  gap: 24rpx;
}

.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 150rpx;
  padding: 28rpx 26rpx;
  border-radius: 0 0 24rpx 24rpx;
  background: #0f172a;
  color: #fff;
}

.eyebrow {
  display: block;
  color: #93c5fd;
  font-size: 24rpx;
}

.title {
  display: block;
  margin-top: 8rpx;
  font-size: 44rpx;
  font-weight: 800;
  letter-spacing: 0;
}

.top-actions {
  display: flex;
  gap: 12rpx;
}

.subscribe,
.refresh {
  width: 118rpx;
  height: 60rpx;
  margin: 0;
  border-radius: 8rpx;
  color: #fff;
  font-size: 24rpx;
  line-height: 60rpx;
}

.subscribe {
  background: #2563eb;
}

.refresh {
  background: #f97316;
}

.report {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx;
}

.report-main {
  min-width: 0;
}

.report-title {
  display: block;
  max-width: 500rpx;
  overflow: hidden;
  color: #111827;
  font-size: 30rpx;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.report-date {
  display: block;
  margin-top: 8rpx;
  color: #64748b;
  font-size: 24rpx;
}

.report-action {
  flex-shrink: 0;
  color: #2563eb;
  font-size: 24rpx;
}

.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20rpx;
}

.product {
  padding: 24rpx;
}

.product-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
}

.code {
  display: block;
  color: #111827;
  font-size: 36rpx;
  font-weight: 800;
}

.name {
  display: block;
  margin-top: 4rpx;
  color: #64748b;
  font-size: 23rpx;
}

.contract {
  display: block;
  margin-top: 6rpx;
  color: #2563eb;
  font-size: 22rpx;
  font-weight: 700;
}

.advice {
  min-width: 128rpx;
  padding: 10rpx 14rpx;
  border-radius: 8rpx;
  background: #ecfdf5;
  color: #047857;
  font-size: 24rpx;
  text-align: center;
}

.price-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18rpx;
  margin-top: 28rpx;
}

.label {
  display: block;
  color: #64748b;
  font-size: 22rpx;
}

.value {
  display: block;
  margin-top: 8rpx;
  color: #111827;
  font-size: 34rpx;
  font-weight: 700;
}

.change {
  display: block;
  margin-top: 4rpx;
  color: #64748b;
  font-size: 22rpx;
}

.basis-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-top: 24rpx;
  color: #475569;
  font-size: 22rpx;
}

.basis-row text {
  padding: 8rpx 12rpx;
  border-radius: 8rpx;
  background: #f1f5f9;
}

.summary {
  padding: 24rpx;
}

.section-title {
  display: block;
  color: #111827;
  font-size: 30rpx;
  font-weight: 700;
}

.summary-text {
  display: block;
  margin-top: 16rpx;
  color: #334155;
  font-size: 26rpx;
  line-height: 1.65;
  white-space: pre-wrap;
}
</style>
