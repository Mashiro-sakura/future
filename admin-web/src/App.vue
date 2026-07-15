<template>
  <div v-if="!authed" class="login-page">
    <section class="login-panel">
      <div>
        <p class="eyebrow">Future Analysis</p>
        <h1>期现分析后台</h1>
      </div>
      <el-form :model="loginForm" label-position="top" @submit.prevent>
        <el-form-item label="账号">
          <el-input v-model="loginForm.username" size="large" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="loginForm.password"
            size="large"
            show-password
            type="password"
            autocomplete="current-password"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-button :loading="loading.login" size="large" type="primary" @click="handleLogin">登录</el-button>
        <p class="hint">默认账号：admin / admin123</p>
      </el-form>
    </section>
  </div>

  <div v-else class="shell">
    <aside class="sidebar">
      <div>
        <p class="eyebrow">多品种期现分析</p>
        <h1>期现分析后台</h1>
      </div>
      <nav>
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          <component :is="tab.icon" />
          <span>{{ tab.label }}</span>
        </button>
      </nav>
      <button class="logout" @click="logout">
        <SwitchButton />
        <span>退出登录</span>
      </button>
    </aside>

    <main class="content">
      <header class="toolbar">
        <div>
          <p class="eyebrow">每个工作日 08:30 / 17:30 自动生成并推送</p>
          <h2>{{ currentTitle }}</h2>
        </div>
        <div class="actions">
          <el-button :icon="Refresh" :loading="loading.sync" @click="handleSync">同步行情</el-button>
          <el-button :icon="DocumentAdd" :loading="loading.generate" type="primary" @click="handleGenerate"
            >生成日报</el-button
          >
        </div>
      </header>

      <section v-if="activeTab === 'dashboard'" class="view">
        <div class="cards">
          <article v-for="item in overview.products" :key="item.code" class="metric-card">
            <div class="card-head">
              <div>
                <h3>{{ item.code }}</h3>
                <p>{{ item.name }}</p>
                <p class="main-contract">{{ contractLabel(item) }}</p>
              </div>
              <el-tag effect="light" type="success">{{ item.recommendation || '待生成' }}</el-tag>
            </div>
            <div class="numbers">
              <div>
                <span>{{ item.futures_contract ? '期货' : '期货不适用' }}</span>
                <strong>{{ money(item.futures_close) }}</strong>
                <em :class="tone(item.futures_change_pct)">{{ pct(item.futures_change_pct) }}</em>
              </div>
              <div>
                <span>现货</span>
                <strong>{{ money(item.spot_price) }}</strong>
                <em :class="tone(item.spot_change_pct)">{{ pct(item.spot_change_pct) }}</em>
              </div>
              <div>
                <span>{{ item.futures_contract ? '基差' : '无期货基差' }}</span>
                <strong>{{ signed(item.basis_value) }}</strong>
                <em>{{ item.futures_contract ? `持仓 ${pct(item.open_interest_change_pct)}` : '现货跟踪' }}</em>
              </div>
            </div>
          </article>
        </div>
        <section class="panel">
          <div class="panel-head">
            <h3>趋势图</h3>
            <el-segmented v-model="chartCode" :options="chartOptions" @change="loadTrend" />
          </div>
          <div ref="chartRef" class="chart"></div>
        </section>
      </section>

      <section v-if="activeTab === 'reports'" class="view reports-layout">
        <section class="panel report-list">
          <div class="panel-head">
            <h3>日报列表</h3>
            <el-radio-group v-model="sessionName" size="small">
              <el-radio-button label="morning">早报</el-radio-button>
              <el-radio-button label="evening">晚报</el-radio-button>
            </el-radio-group>
          </div>
          <el-table :data="reports" height="560" @row-click="selectReport">
            <el-table-column prop="report_date" label="日期" width="120" />
            <el-table-column prop="session_name" label="场次" width="90">
              <template #default="{ row }">{{ row.session_name === 'morning' ? '早报' : '晚报' }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column prop="title" label="标题" min-width="240" />
          </el-table>
        </section>

        <section class="panel editor" v-if="selectedReport">
          <div class="panel-head">
            <h3>编辑日报</h3>
            <div>
              <el-button :icon="Check" :loading="loading.save" @click="handleSave">保存</el-button>
              <el-button :icon="Upload" :loading="loading.publish" type="success" @click="handlePublish">发布</el-button>
              <el-button :icon="Promotion" :loading="loading.push" type="warning" @click="handlePush">推送</el-button>
            </div>
          </div>
          <el-form label-position="top">
            <el-form-item label="标题">
              <el-input v-model="selectedReport.title" />
            </el-form-item>
            <el-form-item label="行情摘要">
              <el-input v-model="selectedReport.market_summary" type="textarea" :rows="7" />
            </el-form-item>
            <el-form-item label="价格行为分析">
              <el-input v-model="selectedReport.price_behavior_analysis" type="textarea" :rows="4" />
            </el-form-item>
            <el-form-item label="基本面分析">
              <el-input v-model="selectedReport.fundamentals_analysis" type="textarea" :rows="4" />
            </el-form-item>
            <el-form-item label="宏观面分析">
              <el-input v-model="selectedReport.macro_analysis" type="textarea" :rows="4" />
            </el-form-item>
            <el-form-item label="政策面分析">
              <el-input v-model="selectedReport.policy_analysis" type="textarea" :rows="4" />
            </el-form-item>
          </el-form>
          <div class="recommendation-editor">
            <article v-for="item in selectedReport.recommendations" :key="item.product_code" class="edit-card">
              <div class="edit-card-head">
                <strong>{{ item.product_code }}</strong>
                <el-select v-model="item.action" class="action-select">
                  <el-option v-for="action in actions" :key="action" :label="action" :value="action" />
                </el-select>
              </div>
              <el-input v-model="item.basis" type="textarea" :rows="2" />
              <el-input v-model="item.risk_note" class="risk-input" type="textarea" :rows="2" />
              <div class="confidence-line">
                <span>置信度</span>
                <el-slider v-model="item.confidence" :min="0" :max="100" />
              </div>
            </article>
          </div>
        </section>
      </section>

      <section v-if="activeTab === 'policy'" class="view">
        <section class="panel import-panel">
          <div class="panel-head">
            <h3>突发政策/产业事件</h3>
          </div>
          <el-form :model="policyForm" label-position="top">
            <el-form-item label="影响品种">
              <el-select v-model="policyForm.product_codes" multiple clearable placeholder="不选则推送全部品种">
                <el-option v-for="item in overview.products" :key="item.code" :label="`${item.code} ${item.name}`" :value="item.code" />
              </el-select>
            </el-form-item>
            <el-form-item label="事件类型">
              <el-select v-model="policyForm.category">
                <el-option label="供需突发" value="供需突发" />
                <el-option label="重大事件" value="重大事件" />
                <el-option label="安全生产" value="安全生产" />
                <el-option label="环保" value="环保" />
                <el-option label="检修" value="检修" />
              </el-select>
            </el-form-item>
            <el-form-item label="标题">
              <el-input v-model="policyForm.title" placeholder="例如：某主产区装置集中停车影响短期供应" />
            </el-form-item>
            <el-form-item label="事件内容">
              <el-input
                v-model="policyForm.content"
                type="textarea"
                :rows="5"
                placeholder="描述事件、影响范围、供应/需求变化、需要跟踪的库存和开工率信号"
              />
            </el-form-item>
            <el-form-item label="影响级别">
              <el-select v-model="policyForm.impact_level">
                <el-option label="重大关注" value="重大关注" />
                <el-option label="偏多关注" value="偏多关注" />
                <el-option label="偏空关注" value="偏空关注" />
                <el-option label="关注" value="关注" />
              </el-select>
            </el-form-item>
            <el-form-item label="来源">
              <el-input v-model="policyForm.source" placeholder="manual / 官方公告 / 行业消息" />
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="policyForm.push_now">立即生成突发快讯并推送企业微信</el-checkbox>
            </el-form-item>
            <el-button :icon="Warning" :loading="loading.policy" type="danger" @click="handlePolicyEvent">保存事件</el-button>
          </el-form>
        </section>
      </section>

      <section v-if="activeTab === 'import'" class="view">
        <section class="panel import-panel">
          <div class="panel-head">
            <h3>现货价格导入</h3>
          </div>
          <el-upload :auto-upload="false" :limit="1" accept=".csv" :on-change="handleFileChange">
            <el-button :icon="UploadFilled" type="primary">选择 CSV 文件</el-button>
          </el-upload>
          <pre class="sample">product_code,trade_date,price,region
PTA,2026-07-09,5910,华东
PVC,2026-07-09,5580,华东</pre>
        </section>
      </section>

      <section v-if="activeTab === 'logs'" class="view logs-layout">
        <section class="panel">
          <div class="panel-head">
            <h3>同步日志</h3>
          </div>
          <el-table :data="logs.sync_logs" height="560">
            <el-table-column prop="started_at" label="开始时间" width="180" />
            <el-table-column prop="product_code" label="品种" width="90" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column prop="message" label="信息" />
          </el-table>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h3>推送日志</h3>
          </div>
          <el-table :data="logs.push_logs" height="560">
            <el-table-column prop="sent_at" label="时间" width="180" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column prop="message" label="信息" />
          </el-table>
        </section>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import {
  Check,
  DataLine,
  Document,
  DocumentAdd,
  Files,
  Promotion,
  Refresh,
  SwitchButton,
  Upload,
  UploadFilled,
  Warning
} from '@element-plus/icons-vue'
import {
  clearToken,
  createPolicyEvent,
  generateReport,
  getLogs,
  getOverview,
  getToken,
  getTrend,
  importSpot,
  listReports,
  login,
  publishReport,
  pushReport,
  setToken,
  syncData,
  updateReport
} from './api'

const tabs = [
  { key: 'dashboard', label: '数据看板', icon: DataLine },
  { key: 'reports', label: '日报审核', icon: Document },
  { key: 'policy', label: '政策事件', icon: Warning },
  { key: 'import', label: '现货导入', icon: UploadFilled },
  { key: 'logs', label: '运行日志', icon: Files }
]
const actions = ['积极采购', '小单补库', '观望等待', '逢低采购', '套保关注']
const activeTab = ref('dashboard')
const authed = ref(Boolean(getToken()))
const sessionName = ref('evening')
const chartCode = ref('PTA')
const chartRef = ref(null)
let chart = null

const loginForm = reactive({ username: 'admin', password: 'admin123' })
const loading = reactive({
  login: false,
  sync: false,
  generate: false,
  save: false,
  publish: false,
  push: false,
  policy: false
})
const overview = reactive({ latest_report: null, products: [] })
const reports = ref([])
const selectedReport = ref(null)
const logs = reactive({ sync_logs: [], push_logs: [] })
const policyForm = reactive({
  product_codes: [],
  category: '供需突发',
  title: '',
  content: '',
  impact_level: '重大关注',
  source: 'manual',
  url: '',
  push_now: true,
  session_name: 'urgent'
})

const currentTitle = computed(() => tabs.find((item) => item.key === activeTab.value)?.label || '数据看板')
const chartOptions = computed(() => overview.products.map((item) => ({ label: item.code, value: item.code })))

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
  if (Number(value) > 0) return 'positive'
  if (Number(value) < 0) return 'negative'
  return ''
}

function contractLabel(item) {
  return item.futures_contract ? `主力合约 ${item.futures_contract}` : '现货品种'
}

async function handleLogin() {
  loading.login = true
  try {
    const data = await login(loginForm.username, loginForm.password)
    setToken(data.access_token)
    authed.value = true
    await bootstrap()
    ElMessage.success('登录成功')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.login = false
  }
}

function logout() {
  clearToken()
  authed.value = false
}

async function loadOverview() {
  const data = await getOverview()
  overview.latest_report = data.latest_report
  overview.products = data.products || []
  if (!overview.products.some((item) => item.code === chartCode.value)) {
    chartCode.value = overview.products[0]?.code || 'PTA'
  }
}

async function loadTrend() {
  if (!chartRef.value || !chartCode.value) return
  const points = await getTrend(chartCode.value, 60)
  const hasFutures = points.some((item) => item.futures_close !== null && item.futures_close !== undefined)
  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption(
    {
      color: ['#2563eb', '#f97316', '#0f766e'],
      tooltip: { trigger: 'axis' },
      legend: { top: 0, data: hasFutures ? ['期货收盘', '现货价格', '持仓量'] : ['现货价格'] },
      grid: { top: 48, right: 32, left: 56, bottom: 36 },
      xAxis: { type: 'category', data: points.map((item) => item.trade_date) },
      yAxis: [
        { type: 'value', name: '价格' },
        { type: 'value', name: '持仓', splitLine: { show: false } }
      ],
      series: [
        ...(hasFutures
          ? [{ name: '期货收盘', type: 'line', smooth: true, data: points.map((item) => item.futures_close) }]
          : []),
        { name: '现货价格', type: 'line', smooth: true, data: points.map((item) => item.spot_price) },
        ...(hasFutures
          ? [{ name: '持仓量', type: 'bar', yAxisIndex: 1, opacity: 0.28, data: points.map((item) => item.open_interest) }]
          : [])
      ]
    },
    true
  )
}

async function refreshReports() {
  reports.value = await listReports()
  selectedReport.value = reports.value[0] ? structuredClone(reports.value[0]) : null
}

async function refreshLogs() {
  const data = await getLogs()
  logs.sync_logs = data.sync_logs || []
  logs.push_logs = data.push_logs || []
}

async function bootstrap() {
  await Promise.all([loadOverview(), refreshReports(), refreshLogs()])
  await nextTick()
  await loadTrend()
}

async function handleSync() {
  loading.sync = true
  try {
    const data = await syncData()
    ElMessage.success(data.message || '同步完成')
    await bootstrap()
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.sync = false
  }
}

async function handleGenerate() {
  loading.generate = true
  try {
    const report = await generateReport(sessionName.value)
    selectedReport.value = structuredClone(report)
    await refreshReports()
    activeTab.value = 'reports'
    ElMessage.success('日报初稿已生成')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.generate = false
  }
}

function selectReport(row) {
  selectedReport.value = structuredClone(row)
}

async function handleSave() {
  if (!selectedReport.value) return
  loading.save = true
  try {
    const payload = {
      title: selectedReport.value.title,
      market_summary: selectedReport.value.market_summary,
      price_behavior_analysis: selectedReport.value.price_behavior_analysis,
      fundamentals_analysis: selectedReport.value.fundamentals_analysis,
      macro_analysis: selectedReport.value.macro_analysis,
      policy_analysis: selectedReport.value.policy_analysis,
      recommendations: selectedReport.value.recommendations
    }
    selectedReport.value = await updateReport(selectedReport.value.id, payload)
    await refreshReports()
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.save = false
  }
}

async function handlePublish() {
  if (!selectedReport.value) return
  loading.publish = true
  try {
    selectedReport.value = await publishReport(selectedReport.value.id)
    await Promise.all([loadOverview(), refreshReports()])
    ElMessage.success('已发布到客户面')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.publish = false
  }
}

async function handlePush() {
  if (!selectedReport.value) return
  loading.push = true
  try {
    const data = await pushReport(selectedReport.value.id)
    await Promise.all([refreshReports(), refreshLogs()])
    ElMessage.success(data.message)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.push = false
  }
}

async function handlePolicyEvent() {
  if (!policyForm.title.trim() || !policyForm.content.trim()) {
    ElMessage.error('请填写事件标题和内容')
    return
  }
  loading.policy = true
  try {
    const data = await createPolicyEvent({ ...policyForm })
    policyForm.title = ''
    policyForm.content = ''
    await Promise.all([loadOverview(), refreshReports(), refreshLogs()])
    ElMessage.success(data.message)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.policy = false
  }
}

async function handleFileChange(uploadFile) {
  if (!uploadFile.raw) return
  try {
    const data = await importSpot(uploadFile.raw)
    ElMessage.success(data.message)
    await bootstrap()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

watch(activeTab, async (value) => {
  if (value === 'dashboard') {
    await nextTick()
    await loadTrend()
  }
  if (value === 'logs') await refreshLogs()
})

watch(chartCode, loadTrend)

window.addEventListener('resize', () => chart?.resize())

onMounted(async () => {
  if (authed.value) {
    try {
      await bootstrap()
    } catch (error) {
      clearToken()
      authed.value = false
    }
  }
})
</script>
