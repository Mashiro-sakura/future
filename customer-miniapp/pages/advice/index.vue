<template>
  <view class="page advice-page">
    <view class="hero">
      <view>
        <text class="eyebrow">{{ report?.report_date || 'Latest' }}</text>
        <text class="title">采购建议</text>
      </view>
      <button class="refresh" @tap="loadAdvice">刷新</button>
    </view>

    <view class="panel basis-panel">
      <text class="basis-title">分析依据</text>
      <view class="basis-tags">
        <text>价格行为</text>
        <text>基本面</text>
        <text>宏观面</text>
        <text>政策面</text>
      </view>
    </view>

    <view
      v-for="item in report?.recommendations || []"
      :key="item.product_code"
      class="panel advice-card"
      :class="{ active: selectedCode === item.product_code }"
      @tap="selectProduct(item.product_code)"
    >
      <view class="card-head">
        <view>
          <text class="product">{{ item.product_code }}</text>
          <text class="confidence">置信度 {{ item.confidence }}%</text>
        </view>
        <text class="action">{{ item.action }}</text>
      </view>
      <text class="basis">{{ item.basis }}</text>
      <text class="risk">{{ item.risk_note }}</text>
      <button class="detail" @tap.stop="openProduct(item.product_code)">查看趋势</button>
    </view>

    <view class="panel section" v-if="selectedAnalysis">
      <text class="section-title">{{ selectedCode }} 四维分析</text>
      <view class="analysis-section">
        <text class="analysis-title">价格行为</text>
        <text class="section-text">{{ selectedAnalysis.price_behavior || '-' }}</text>
      </view>
      <view class="analysis-section">
        <text class="analysis-title">基本面</text>
        <text class="section-text">{{ selectedAnalysis.fundamentals || '-' }}</text>
      </view>
      <view class="analysis-section">
        <text class="analysis-title">宏观面</text>
        <text class="section-text">{{ selectedAnalysis.macro || '-' }}</text>
      </view>
      <view class="analysis-section">
        <text class="analysis-title">政策面</text>
        <text class="section-text">{{ selectedAnalysis.policy || '-' }}</text>
      </view>
      <view class="analysis-section" v-if="selectedAnalysis.conclusion">
        <text class="analysis-title">结论</text>
        <text class="analysis-conclusion">{{ selectedAnalysis.conclusion }}</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getLatestReport, getOverview } from '../../utils/api'

const report = ref(null)
const productNames = ref({})
const selectedCode = ref('')
const selectedAnalysis = computed(() => {
  const rows = report.value?.product_analyses || []
  return rows.find((item) => item.product_code === selectedCode.value) || null
})

async function loadAdvice() {
  const [latest, overview] = await Promise.all([getLatestReport(), getOverview()])
  report.value = latest
  productNames.value = Object.fromEntries((overview.products || []).map((item) => [item.code, item.name]))
  if (!selectedCode.value || !latest?.recommendations?.some((item) => item.product_code === selectedCode.value)) {
    selectedCode.value = latest?.recommendations?.[0]?.product_code || ''
  }
}

function selectProduct(code) {
  selectedCode.value = code
}

function openProduct(code) {
  const name = productNames.value[code] || code
  uni.navigateTo({ url: `/pages/product/detail?code=${code}&name=${encodeURIComponent(name)}` })
}

onShow(loadAdvice)
</script>

<style scoped>
.advice-page {
  display: flex;
  flex-direction: column;
  gap: 22rpx;
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

.eyebrow {
  display: block;
  color: #7ea8f0;
  font-size: 22rpx;
  font-weight: 700;
}

.title {
  display: block;
  margin-top: 8rpx;
  font-size: 42rpx;
  font-weight: 800;
}

.refresh {
  width: 118rpx;
  height: 60rpx;
  margin: 0;
  border-radius: 8rpx;
  background: #f97316;
  color: #fff;
  font-size: 24rpx;
  line-height: 60rpx;
}

.basis-panel,
.advice-card,
.section {
  padding: 24rpx;
}

.advice-card.active {
  border: 2rpx solid #4f8ff7;
  background: #eff6ff;
}

.basis-title,
.section-title {
  display: block;
  color: #e6eaf2;
  font-size: 30rpx;
  font-weight: 800;
}

.basis-tags {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8rpx;
  margin-top: 16rpx;
}

.basis-tags text {
  padding: 8rpx 6rpx;
  border-radius: 8rpx;
  background: #1a2130;
  color: #a7b0c2;
  font-size: 21rpx;
  text-align: center;
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18rpx;
}

.product {
  display: block;
  color: #e6eaf2;
  font-size: 36rpx;
  font-weight: 800;
}

.confidence {
  display: block;
  margin-top: 6rpx;
  color: #7d879c;
  font-size: 22rpx;
}

.action {
  flex-shrink: 0;
  padding: 10rpx 14rpx;
  border-radius: 8rpx;
  background: #123125;
  color: #0dbf7e;
  font-size: 24rpx;
  font-weight: 700;
}

.basis,
.risk,
.section-text {
  display: block;
  margin-top: 16rpx;
  color: #c3cad9;
  font-size: 26rpx;
  line-height: 1.6;
  white-space: pre-wrap;
}

.analysis-section {
  padding: 18rpx 0;
  border-top: 1rpx solid #1f2637;
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

.risk {
  color: #d9a53f;
}

.analysis-conclusion {
  display: block;
  margin-top: 16rpx;
  color: #f0455c;
  font-size: 28rpx;
  font-weight: 900;
  line-height: 1.6;
  white-space: pre-wrap;
}

.detail {
  width: 150rpx;
  height: 58rpx;
  margin: 18rpx 0 0;
  border-radius: 8rpx;
  background: #4f8ff7;
  color: #fff;
  font-size: 24rpx;
  line-height: 58rpx;
}
</style>
