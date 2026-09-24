<template>
  <view class="page basis">
    <view class="top">
      <view>
        <text class="eyebrow">期现视角</text>
        <text class="title">基差结构</text>
      </view>
      <button class="refresh" @tap="loadData">刷新</button>
    </view>

    <view class="explain panel">
      <text class="explain-text">基差 = 现货价（华东） − 期货主力收盘价。正值 = 现货升水，负值 = 现货贴水。分位表示当前基差在过去样本中的位置——只描述结构，不构成买卖指令。</text>
    </view>

    <view class="stale-banner" v-if="staleText">
      <text>{{ staleText }}</text>
    </view>

    <view class="grid">
      <view v-for="item in basisList" :key="item.code" class="product panel" @tap="toggle(item.code)">
        <view class="product-head">
          <view>
            <text class="code">{{ item.code }}</text>
            <text class="name">{{ item.name }}</text>
            <text class="contract">{{ item.futures_contract ? `主力 ${item.futures_contract}` : '' }}</text>
          </view>
          <view class="basis-main">
            <text class="basis-value" :class="tone(item.basis_value)">{{ signed(item.basis_value) }}</text>
            <text class="basis-label">{{ item.basis_label }}</text>
          </view>
        </view>

        <view class="pct-wrap" v-if="item.percentile !== null && item.percentile !== undefined">
          <view class="pct-bar">
            <view class="zone z-low"></view>
            <view class="zone z-mid"></view>
            <view class="zone z-high"></view>
            <view class="marker" :style="{ left: item.percentile + '%' }"></view>
          </view>
          <view class="pct-meta">
            <text>低 20%</text>
            <text class="pct-now">{{ item.percentile }}% · {{ item.zone }}</text>
            <text>80% 高</text>
          </view>
        </view>
        <view class="pct-empty" v-else>
          <text>样本不足（{{ item.sample_days }} 日），暂不给出分位</text>
        </view>

        <view class="foot-row">
          <text>样本 {{ item.sample_days }} 个交易日</text>
          <text>截至 {{ item.trade_date }}</text>
          <text v-if="item.data_stale" class="stale-tag">数据已停更 {{ item.days_since_last }} 天</text>
        </view>

        <view class="history" v-if="expanded === item.code">
          <view class="history-title">
            <text>近 {{ (historyMap[item.code] || []).length }} 日基差</text>
          </view>
          <view class="history-row head">
            <text>日期</text>
            <text>期货</text>
            <text>现货</text>
            <text>基差</text>
          </view>
          <view v-for="row in historyMap[item.code]" :key="row.trade_date" class="history-row">
            <text>{{ row.trade_date }}</text>
            <text>{{ money(row.futures_close) }}</text>
            <text>{{ money(row.spot_price) }}</text>
            <text :class="tone(row.basis_value)">{{ signed(row.basis_value) }}</text>
          </view>
        </view>
      </view>
    </view>

    <view class="footer-note">
      <text>分位按实际样本计算，样本量如实标注。基差只回答"此刻在结构中的位置"，方向判断与买卖决策永远在人。</text>
    </view>
  </view>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getBasisDetail, getBasisOverview } from '../../utils/api'

const basisList = ref([])
const expanded = ref('')
const historyMap = reactive({})

const staleText = computed(() => {
  const staleItems = basisList.value.filter((item) => item.data_stale)
  if (!staleItems.length) return ''
  const worst = staleItems.reduce((a, b) => (a.days_since_last > b.days_since_last ? a : b))
  return `数据截至 ${worst.trade_date}（距今 ${worst.days_since_last} 天，同步停更期间）——以下数字仅供形态演示，不作决策依据`
})

function money(value) {
  if (value === null || value === undefined) return '-'
  return Number(value).toLocaleString()
}

function signed(value) {
  if (value === null || value === undefined) return '-'
  return Number(value) > 0 ? `+${Number(value).toFixed(1)}` : Number(value).toFixed(1)
}

function tone(value) {
  if (Number(value) > 0) return 'positive'
  if (Number(value) < 0) return 'negative'
  return ''
}

async function loadData() {
  const data = await getBasisOverview()
  basisList.value = data || []
}

async function toggle(code) {
  if (expanded.value === code) {
    expanded.value = ''
    return
  }
  expanded.value = code
  if (!historyMap[code]) {
    const detail = await getBasisDetail(code, 30)
    const rows = (detail.history || []).filter((row) => row.basis_value !== null).slice(-10).reverse()
    historyMap[code] = rows
  }
}

onMounted(loadData)
</script>

<style scoped>
.page.basis {
  min-height: 100vh;
  padding: 24rpx;
  background: #0f172a;
}

.top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.eyebrow {
  display: block;
  font-size: 22rpx;
  color: #93c5fd;
}

.title {
  display: block;
  font-size: 40rpx;
  font-weight: 700;
  color: #fff;
}

.refresh {
  font-size: 24rpx;
  color: #fff;
  background: #2563eb;
  border-radius: 12rpx;
  padding: 10rpx 28rpx;
  line-height: 1.6;
}

.panel {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
}

.explain {
  margin-bottom: 20rpx;
}

.explain-text {
  font-size: 24rpx;
  color: #475569;
  line-height: 1.7;
}

.stale-banner {
  background: #fef3c7;
  color: #92400e;
  border-radius: 12rpx;
  padding: 16rpx 24rpx;
  margin-bottom: 20rpx;
  font-size: 23rpx;
  line-height: 1.6;
}

.grid {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.product-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.code {
  font-size: 32rpx;
  font-weight: 700;
  color: #111827;
  margin-right: 12rpx;
}

.name {
  font-size: 24rpx;
  color: #64748b;
  margin-right: 12rpx;
}

.contract {
  font-size: 22rpx;
  color: #2563eb;
}

.basis-main {
  text-align: right;
}

.basis-value {
  display: block;
  font-size: 40rpx;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.basis-value.positive { color: #dc2626; }
.basis-value.negative { color: #16a34a; }

.basis-label {
  font-size: 22rpx;
  color: #64748b;
}

.pct-wrap {
  margin-top: 24rpx;
}

.pct-bar {
  position: relative;
  height: 26rpx;
  border-radius: 8rpx;
  overflow: hidden;
  display: flex;
}

.zone { height: 100%; }
.z-low { width: 20%; background: #dbeafe; }
.z-mid { width: 60%; background: #f1f5f9; }
.z-high { width: 20%; background: #dcfce7; }

.marker {
  position: absolute;
  top: -4rpx;
  width: 6rpx;
  height: 34rpx;
  background: #dc2626;
  transform: translateX(-50%);
}

.pct-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 10rpx;
  font-size: 21rpx;
  color: #94a3b8;
}

.pct-now {
  color: #111827;
  font-weight: 700;
}

.pct-empty {
  margin-top: 24rpx;
  font-size: 22rpx;
  color: #94a3b8;
  background: #f8fafc;
  border-radius: 8rpx;
  padding: 14rpx 20rpx;
}

.foot-row {
  display: flex;
  gap: 24rpx;
  margin-top: 16rpx;
  font-size: 21rpx;
  color: #94a3b8;
  flex-wrap: wrap;
}

.stale-tag {
  color: #b45309;
  background: #fef3c7;
  border-radius: 6rpx;
  padding: 0 12rpx;
}

.history {
  margin-top: 20rpx;
  border-top: 1rpx solid #e2e8f0;
  padding-top: 16rpx;
}

.history-title {
  font-size: 23rpx;
  color: #2563eb;
  margin-bottom: 10rpx;
}

.history-row {
  display: flex;
  justify-content: space-between;
  font-size: 22rpx;
  color: #334155;
  padding: 6rpx 0;
  font-variant-numeric: tabular-nums;
}

.history-row.head {
  color: #94a3b8;
}

.history-row .positive { color: #dc2626; }
.history-row .negative { color: #16a34a; }

.footer-note {
  margin-top: 24rpx;
  font-size: 21rpx;
  color: #64748b;
  line-height: 1.7;
  padding: 0 8rpx 40rpx;
}
</style>
