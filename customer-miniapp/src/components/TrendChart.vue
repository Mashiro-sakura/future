<template>
  <view class="chart-wrap">
    <view class="chart-head">
      <view>
        <text class="chart-title">{{ title }}</text>
        <text class="chart-subtitle">{{ subtitle }}</text>
      </view>
      <view class="legend">
        <view v-if="hasFuturesSeries" class="legend-item"><text class="dot futures"></text><text>期货</text></view>
        <view class="legend-item"><text class="dot spot"></text><text>现货</text></view>
      </view>
    </view>
    <canvas
      class="chart"
      canvas-id="trendCanvas"
      id="trendCanvas"
      type="2d"
      @touchstart="handleTouch"
      @touchmove="handleTouch"
    />
    <view v-if="activePoint" class="tooltip">
      <text>{{ activePoint.trade_date }}</text>
      <text>{{ activePoint.futures_contract ? `主力 ${activePoint.futures_contract}` : '现货品种' }}</text>
      <text v-if="hasFuturesSeries">期货 {{ displayValue(activePoint.futures_close) }}</text>
      <text>现货 {{ displayValue(activePoint.spot_price) }}</text>
      <text>持仓 {{ displayValue(activePoint.open_interest) }}</text>
    </view>
  </view>
</template>

<script setup>
import { computed, nextTick, onMounted, watch, ref } from 'vue'

const props = defineProps({
  title: { type: String, default: '价格趋势' },
  points: { type: Array, default: () => [] }
})

const activePoint = ref(null)
const canvasSize = { width: 335, height: 210 }

const subtitle = computed(() => {
  if (!props.points.length) return '暂无数据'
  const first = props.points[0]?.trade_date
  const last = props.points[props.points.length - 1]?.trade_date
  return `${first} 至 ${last}`
})

const hasFuturesSeries = computed(() =>
  props.points.some((item) => item.futures_close !== null && item.futures_close !== undefined)
)

function displayValue(value) {
  if (value === null || value === undefined) return '-'
  return Number(value).toLocaleString()
}

function normalize(value, min, max, height) {
  if (max === min) return height / 2
  return height - ((value - min) / (max - min)) * height
}

function drawLine(ctx, points, key, color, area) {
  const values = points.map((item) => Number(item[key])).filter(Number.isFinite)
  if (values.length < 2) return
  const min = Math.min(...values)
  const max = Math.max(...values)
  const innerW = area.w
  const innerH = area.h
  ctx.beginPath()
  points.forEach((item, index) => {
    const x = area.x + (index / Math.max(points.length - 1, 1)) * innerW
    const y = area.y + normalize(Number(item[key]), min, max, innerH)
    if (index === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.strokeStyle = color
  ctx.lineWidth = 2.5
  ctx.stroke()
}

function drawChart() {
  const points = props.points.slice(-40)
  const ctx = uni.createCanvasContext('trendCanvas')
  const area = { x: 34, y: 18, w: canvasSize.width - 52, h: canvasSize.height - 46 }
  ctx.clearRect(0, 0, canvasSize.width, canvasSize.height)
  ctx.setFillStyle('#ffffff')
  ctx.fillRect(0, 0, canvasSize.width, canvasSize.height)

  ctx.setStrokeStyle('#e5e7eb')
  ctx.setLineWidth(1)
  for (let i = 0; i <= 4; i += 1) {
    const y = area.y + (area.h / 4) * i
    ctx.beginPath()
    ctx.moveTo(area.x, y)
    ctx.lineTo(area.x + area.w, y)
    ctx.stroke()
  }

  if (!points.length) {
    ctx.setFillStyle('#94a3b8')
    ctx.setFontSize(14)
    ctx.fillText('暂无趋势数据', 120, 105)
    ctx.draw()
    return
  }

  drawLine(ctx, points, 'futures_close', '#2563eb', area)
  drawLine(ctx, points, 'spot_price', '#f97316', area)

  const first = points[0]
  const last = points[points.length - 1]
  ctx.setFillStyle('#64748b')
  ctx.setFontSize(10)
  ctx.fillText(String(first.trade_date).slice(5), area.x, canvasSize.height - 12)
  ctx.fillText(String(last.trade_date).slice(5), canvasSize.width - 64, canvasSize.height - 12)
  ctx.draw()
}

function handleTouch(event) {
  const touches = event.touches || []
  if (!touches.length || !props.points.length) return
  const x = touches[0].x
  const index = Math.round(((x - 34) / (canvasSize.width - 52)) * (props.points.length - 1))
  activePoint.value = props.points[Math.max(0, Math.min(props.points.length - 1, index))]
}

watch(
  () => props.points,
  () => {
    activePoint.value = null
    nextTick(drawChart)
  },
  { deep: true }
)

onMounted(() => nextTick(drawChart))
</script>

<style scoped>
.chart-wrap {
  padding: 24rpx;
  border: 1rpx solid #e5e7eb;
  border-radius: 12rpx;
  background: #fff;
}

.chart-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16rpx;
}

.chart-title {
  display: block;
  font-size: 30rpx;
  font-weight: 700;
  color: #111827;
}

.chart-subtitle {
  display: block;
  margin-top: 4rpx;
  font-size: 22rpx;
  color: #64748b;
}

.legend {
  display: flex;
  gap: 14rpx;
  font-size: 22rpx;
  color: #475569;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6rpx;
}

.dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
}

.futures {
  background: #2563eb;
}

.spot {
  background: #f97316;
}

.chart {
  width: 670rpx;
  height: 420rpx;
}

.tooltip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8rpx;
  margin-top: 14rpx;
  padding: 14rpx 16rpx;
  border-radius: 10rpx;
  background: #f8fafc;
  color: #334155;
  font-size: 22rpx;
}
</style>
