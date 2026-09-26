<template>
  <view class="page report-detail">
    <view class="hero">
      <view>
        <text class="session">{{ sessionText }}</text>
        <text class="title">{{ report?.title || '分析日报' }}</text>
      </view>
    </view>

    <view class="panel block">
      <text class="block-title">{{ selectedCode || '-' }} 四维分析</text>
      <view class="product-tabs">
        <text
          v-for="item in report?.recommendations || []"
          :key="item.product_code"
          :class="{ active: selectedCode === item.product_code }"
          @tap="selectProduct(item.product_code)"
        >
          {{ item.product_code }}
        </text>
      </view>
      <view class="analysis-section">
        <text class="analysis-title">价格行为</text>
        <text class="summary">{{ selectedAnalysis?.price_behavior || '-' }}</text>
      </view>
      <view class="analysis-section">
        <text class="analysis-title">基本面</text>
        <text class="summary">{{ selectedAnalysis?.fundamentals || '-' }}</text>
      </view>
      <view class="analysis-section">
        <text class="analysis-title">宏观面</text>
        <text class="summary">{{ selectedAnalysis?.macro || '-' }}</text>
      </view>
      <view class="analysis-section">
        <text class="analysis-title">政策面</text>
        <text class="summary">{{ selectedAnalysis?.policy || '-' }}</text>
      </view>
      <view class="analysis-section" v-if="selectedAnalysis?.conclusion">
        <text class="analysis-title">结论</text>
        <text class="analysis-conclusion">{{ selectedAnalysis.conclusion }}</text>
      </view>
    </view>

    <view class="panel block">
      <text class="block-title">采购建议</text>
      <view
        v-for="item in report?.recommendations || []"
        :key="item.product_code"
        class="advice-row"
        :class="{ active: selectedCode === item.product_code }"
        @tap="selectProduct(item.product_code)"
      >
        <view class="advice-head">
          <text class="product">{{ item.product_code }}</text>
          <text class="action">{{ item.action }}</text>
        </view>
        <text class="basis">{{ item.basis }}</text>
        <text class="risk">{{ item.risk_note }}</text>
        <view class="confidence">
          <view class="bar"><view class="bar-fill" :style="{ width: `${item.confidence}%` }"></view></view>
          <text>{{ item.confidence }}%</text>
        </view>
      </view>
    </view>

    <view class="panel block">
      <text class="block-title">行情摘要</text>
      <text class="summary">{{ report?.market_summary || '暂无摘要' }}</text>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getLatestReport, getReport } from '../../utils/api'

const report = ref(null)
const selectedCode = ref('')

const sessionText = computed(() => {
  const session = report.value?.session_name
  return session === 'morning' ? '早报' : session === 'evening' ? '晚报' : '日报'
})
const selectedAnalysis = computed(() => {
  const rows = report.value?.product_analyses || []
  return rows.find((item) => item.product_code === selectedCode.value) || null
})

function selectProduct(code) {
  selectedCode.value = code
}

onLoad(async (query) => {
  report.value = query.id ? await getReport(query.id) : await getLatestReport()
  selectedCode.value = report.value?.recommendations?.[0]?.product_code || ''
})
</script>

<style scoped>
.report-detail {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.hero {
  padding: 30rpx 26rpx;
  border-radius: 0 0 24rpx 24rpx;
  background: #0f172a;
  color: #fff;
}

.session {
  display: block;
  color: #7ea8f0;
  font-size: 24rpx;
}

.title {
  display: block;
  margin-top: 8rpx;
  font-size: 36rpx;
  font-weight: 800;
  line-height: 1.35;
}

.block {
  padding: 24rpx;
}

.block-title {
  display: block;
  margin-bottom: 18rpx;
  color: #e6eaf2;
  font-size: 30rpx;
  font-weight: 800;
}

.product-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-bottom: 16rpx;
}

.product-tabs text {
  padding: 8rpx 12rpx;
  border-radius: 8rpx;
  background: #1a2130;
  color: #a7b0c2;
  font-size: 22rpx;
  font-weight: 700;
}

.product-tabs text.active {
  background: #4f8ff7;
  color: #fff;
}

.analysis-section {
  padding: 18rpx 0;
  border-top: 1rpx solid #1f2637;
}

.analysis-section:first-of-type {
  border-top: 0;
}

.analysis-title {
  display: block;
  color: #4f8ff7;
  font-size: 26rpx;
  font-weight: 800;
}

.advice-row {
  padding: 20rpx 0;
  border-top: 1rpx solid #1f2637;
}

.advice-row.active {
  padding-right: 12rpx;
  padding-left: 12rpx;
  border-radius: 8rpx;
  background: #1c2b4a;
}

.advice-row:first-of-type {
  border-top: 0;
}

.advice-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.product {
  color: #e6eaf2;
  font-size: 32rpx;
  font-weight: 800;
}

.action {
  padding: 8rpx 12rpx;
  border-radius: 8rpx;
  background: #1c2b4a;
  color: #4f8ff7;
  font-size: 24rpx;
}

.basis {
  display: block;
  margin-top: 14rpx;
  color: #c3cad9;
  font-size: 26rpx;
  line-height: 1.55;
}

.risk {
  display: block;
  margin-top: 8rpx;
  color: #d9a53f;
  font-size: 24rpx;
  line-height: 1.5;
}

.confidence {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-top: 16rpx;
  color: #7d879c;
  font-size: 22rpx;
}

.bar {
  flex: 1;
  height: 12rpx;
  overflow: hidden;
  border-radius: 8rpx;
  background: #1f2637;
}

.bar-fill {
  height: 100%;
  border-radius: 8rpx;
  background: #f97316;
}

.summary {
  display: block;
  color: #c3cad9;
  font-size: 26rpx;
  line-height: 1.65;
  white-space: pre-wrap;
}

.analysis-conclusion {
  display: block;
  margin-top: 10rpx;
  color: #f0455c;
  font-size: 28rpx;
  font-weight: 900;
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
