<template>
  <view class="page product-detail">
    <view class="hero">
      <view>
        <text class="code">{{ code }}</text>
        <text class="name">{{ name }}</text>
        <text class="contract">{{ contractText }}</text>
      </view>
      <button class="back" @tap="goBack">返回</button>
    </view>

    <TrendChart :title="chartTitle" :points="trend" />

    <view class="panel metrics" v-if="latest">
      <view class="metric">
        <text class="metric-label">期货价格</text>
        <text class="metric-value">{{ money(latest.futures_close) }}</text>
      </view>
      <view class="metric">
        <text class="metric-label">现货价格</text>
        <text class="metric-value">{{ money(latest.spot_price) }}</text>
      </view>
      <view class="metric">
        <text class="metric-label">持仓量</text>
        <text class="metric-value">{{ money(latest.open_interest) }}</text>
      </view>
      <view class="metric">
        <text class="metric-label">成交量</text>
        <text class="metric-value">{{ money(latest.volume) }}</text>
      </view>
    </view>

    <view class="panel analysis" v-if="analysis">
      <text class="section-title">{{ code }} 四维分析</text>
      <view class="analysis-section">
        <text class="analysis-title">价格行为</text>
        <text class="analysis-text">{{ analysis.price_behavior || '-' }}</text>
      </view>
      <view class="analysis-section">
        <text class="analysis-title">基本面</text>
        <text class="analysis-text">{{ analysis.fundamentals || '-' }}</text>
      </view>
      <view class="analysis-section">
        <text class="analysis-title">宏观面</text>
        <text class="analysis-text">{{ analysis.macro || '-' }}</text>
      </view>
      <view class="analysis-section">
        <text class="analysis-title">政策面</text>
        <text class="analysis-text">{{ analysis.policy || '-' }}</text>
      </view>
      <view class="analysis-section" v-if="analysis.conclusion">
        <text class="analysis-title">结论</text>
        <text class="analysis-conclusion">{{ analysis.conclusion }}</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import TrendChart from '../../components/TrendChart.vue'
import { getLatestReport, getTrend } from '../../utils/api'

const code = ref('PTA')
const name = ref('PTA')
const trend = ref([])
const report = ref(null)

const latest = computed(() => trend.value[trend.value.length - 1] || null)
const hasFutures = computed(() => Boolean(latest.value?.futures_contract))
const contractText = computed(() => (hasFutures.value ? `主力合约 ${latest.value.futures_contract}` : '现货品种'))
const chartTitle = computed(() => (hasFutures.value ? `${code.value} 主力合约期现价格` : `${code.value} 现货价格趋势`))
const analysis = computed(() => {
  const rows = report.value?.product_analyses || []
  return rows.find((item) => item.product_code === code.value) || null
})

function money(value) {
  if (value === null || value === undefined) return '-'
  return Number(value).toLocaleString()
}

function goBack() {
  uni.navigateBack()
}

onLoad(async (query) => {
  code.value = query.code || 'PTA'
  name.value = decodeURIComponent(query.name || code.value)
  const [trendData, latestReport] = await Promise.all([getTrend(code.value, 60), getLatestReport()])
  trend.value = trendData
  report.value = latestReport
})
</script>

<style scoped>
.product-detail {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 30rpx 26rpx;
  border-radius: 0 0 24rpx 24rpx;
  background: #0f172a;
  color: #fff;
}

.code {
  display: block;
  font-size: 44rpx;
  font-weight: 800;
}

.name {
  display: block;
  margin-top: 8rpx;
  color: #cbd5e1;
  font-size: 24rpx;
}

.contract {
  display: block;
  margin-top: 8rpx;
  color: #93c5fd;
  font-size: 24rpx;
  font-weight: 700;
}

.back {
  width: 110rpx;
  height: 58rpx;
  margin: 0;
  border-radius: 8rpx;
  background: #2563eb;
  color: #fff;
  font-size: 24rpx;
  line-height: 58rpx;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18rpx;
  padding: 24rpx;
}

.metric {
  min-height: 116rpx;
  padding: 18rpx;
  border-radius: 10rpx;
  background: #f8fafc;
}

.metric-label {
  display: block;
  color: #64748b;
  font-size: 22rpx;
}

.metric-value {
  display: block;
  margin-top: 10rpx;
  color: #111827;
  font-size: 34rpx;
  font-weight: 800;
}

.analysis {
  padding: 24rpx;
}

.section-title {
  display: block;
  color: #111827;
  font-size: 30rpx;
  font-weight: 800;
}

.analysis-section {
  padding: 18rpx 0;
  border-top: 1rpx solid #e5e7eb;
}

.analysis-section:first-of-type {
  margin-top: 12rpx;
  border-top: 0;
}

.analysis-title {
  display: block;
  color: #1d4ed8;
  font-size: 26rpx;
  font-weight: 800;
}

.analysis-text {
  display: block;
  margin-top: 10rpx;
  color: #334155;
  font-size: 26rpx;
  line-height: 1.6;
  white-space: pre-wrap;
}

.analysis-conclusion {
  display: block;
  margin-top: 10rpx;
  color: #dc2626;
  font-size: 28rpx;
  font-weight: 900;
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
