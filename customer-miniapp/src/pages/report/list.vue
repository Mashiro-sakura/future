<template>
  <view class="page reports-page">
    <view class="hero">
      <view>
        <text class="eyebrow">Published Reports</text>
        <text class="title">分析日报</text>
      </view>
      <button class="refresh" @tap="loadReports">刷新</button>
    </view>

    <view v-if="!reports.length" class="panel empty">
      <text>暂无已发布日报</text>
    </view>

    <view v-for="item in reports" :key="item.id" class="panel report-card" @tap="openReport(item.id)">
      <view class="report-head">
        <view class="main">
          <text class="report-title">{{ item.title }}</text>
          <text class="report-meta">{{ item.report_date }} · {{ sessionText(item.session_name) }}</text>
        </view>
        <text class="status">{{ item.status === 'pushed' ? '已推送' : '已发布' }}</text>
      </view>
      <view class="analysis-grid">
        <text>价格行为</text>
        <text>基本面</text>
        <text>宏观面</text>
        <text>政策面</text>
      </view>
      <text class="summary">{{ item.market_summary }}</text>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getReports } from '../../utils/api'

const reports = ref([])

function sessionText(session) {
  return session === 'morning' ? '早报' : session === 'evening' ? '晚报' : '日报'
}

async function loadReports() {
  reports.value = await getReports(30)
}

function openReport(id) {
  uni.navigateTo({ url: `/pages/report/detail?id=${id}` })
}

onShow(loadReports)
</script>

<style scoped>
.reports-page {
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
  background: #4f8ff7;
  color: #fff;
  font-size: 24rpx;
  line-height: 60rpx;
}

.empty {
  padding: 40rpx 24rpx;
  color: #7d879c;
  font-size: 26rpx;
  text-align: center;
}

.report-card {
  padding: 24rpx;
}

.report-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18rpx;
}

.main {
  min-width: 0;
}

.report-title {
  display: block;
  color: #e6eaf2;
  font-size: 30rpx;
  font-weight: 800;
  line-height: 1.35;
}

.report-meta {
  display: block;
  margin-top: 8rpx;
  color: #7d879c;
  font-size: 23rpx;
}

.status {
  flex-shrink: 0;
  padding: 8rpx 12rpx;
  border-radius: 8rpx;
  background: #123125;
  color: #0dbf7e;
  font-size: 22rpx;
}

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8rpx;
  margin-top: 18rpx;
}

.analysis-grid text {
  padding: 8rpx 6rpx;
  border-radius: 8rpx;
  background: #1c2b4a;
  color: #4f8ff7;
  font-size: 21rpx;
  text-align: center;
}

.summary {
  display: -webkit-box;
  margin-top: 18rpx;
  overflow: hidden;
  color: #c3cad9;
  font-size: 25rpx;
  line-height: 1.55;
  white-space: pre-wrap;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}
</style>

