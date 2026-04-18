<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Lightning,
  Sunny,
  Odometer,
  Histogram,
  RefreshRight,
  DataLine,
  Cpu,
  Reading,
  Monitor,
  Setting,
  InfoFilled,
  WarningFilled,
  TrendCharts,
} from '@element-plus/icons-vue'
import AppChart from '@/components/AppChart.vue'
import AnimatedNumber from '@/components/AnimatedNumber.vue'
import * as api from '@/api'
import { usePolling } from '@/composables/usePolling'
import { ElMessage } from 'element-plus'

const router = useRouter()

const loading = ref(true)
const lastUpdated = ref(null)
const health = ref(null)
const incidentSum = ref(null)
const buildings = ref({ items: [] })
const benchmark = ref(null)
const period = ref(null)
const anomalies = ref(null)
const timeseries = ref(null)
/** 与饼图联动：当前折线指标 */
const selectedMetric = ref('electricity_kwh')

const REFRESH_MS = 30_000

const PIE_NAME_TO_METRIC = {
  市电: 'electricity_kwh',
  光伏: 'solar_kwh',
  冷量当量: 'chilledwater_kwh_eq',
  热水: 'hotwater_kwh',
}

const METRIC_TO_PIE_NAME = {
  electricity_kwh: '市电',
  solar_kwh: '光伏',
  chilledwater_kwh_eq: '冷量当量',
  hotwater_kwh: '热水',
}

const METRIC_LABEL_SHORT = {
  electricity_kwh: '市电',
  solar_kwh: '光伏',
  chilledwater_kwh_eq: '冷量当量',
  hotwater_kwh: '热水',
  water_m3: '用水',
}

/** 赛题能力导航：与路由、后端能力对齐 */
const MODULE_NAV = [
  {
    key: 'data',
    title: '（1）数据层',
    desc: '能耗数据集与元数据、字典；路径可配，支持缓存重载与知识库索引。',
    links: [
      { path: '/energy', label: '能源监控', icon: Lightning },
      { path: '/admin', label: '系统管理 · 数据与索引', icon: Setting },
    ],
  },
  {
    key: 'stats',
    title: '（2）查询与统计',
    desc: '按建筑、时间、指标查询；时段汇总、COP 演示、异常分析；图表与报表导出。',
    links: [
      { path: '/stats', label: '统计分析', icon: Histogram },
      { path: '/benchmark', label: '能效对标', icon: DataLine },
      { path: '/screen', label: '数据大屏', icon: Monitor },
    ],
  },
  {
    key: 'ops',
    title: '（3）智慧运维',
    desc: '领域知识库 + RAG/LLM 问答；孪生视觉、运营指标与工单闭环。',
    links: [
      { path: '/knowledge', label: '智能问答', icon: Reading },
      { path: '/operations', label: '运营与预测', icon: Odometer },
      { path: '/incidents', label: '告警与工单', icon: WarningFilled },
      { path: '/twin', label: '孪生与视觉', icon: Sunny },
    ],
  },
  {
    key: 'sys',
    title: '（4）系统集成',
    desc: 'MCP 工具清单、OpenAPI、健康检查；前后端一体化演示。',
    links: [
      { path: '/admin', label: '系统管理 · MCP', icon: Cpu },
    ],
  },
]

function goPath(p) {
  router.push(p)
}

/** 去掉「（1）」类序号，用于能力矩阵标题 */
function navTitleShort(title) {
  return String(title).replace(/（\d）\s*/, '').trim()
}

const metricMeta = {
  electricity_kwh: { label: '市电用电', unit: 'kWh', short: '电' },
  solar_kwh: { label: '光伏发电', unit: 'kWh', short: '光' },
  water_m3: { label: '用水量', unit: 'm³', short: '水' },
  hotwater_kwh: { label: '热水能耗', unit: 'kWh', short: '热' },
  chilledwater_kwh_eq: { label: '冷量当量', unit: 'kWh', short: '冷' },
}

const buildingIdForSeries = computed(() => {
  const items = buildings.value?.items ?? []
  if (!items.length) return ''
  const b = items[0]
  return b.building_id ?? b.id ?? ''
})

const anomalyPct = computed(() => {
  const r = anomalies.value?.ratio
  if (r == null || Number.isNaN(r)) return null
  return (r * 100).toFixed(2)
})

const anomalySerious = computed(() => {
  const r = anomalies.value?.ratio ?? 0
  return r > 0.1
})

const anomalyWarn = computed(() => {
  const r = anomalies.value?.ratio ?? 0
  return r > 0.05 && r <= 0.1
})

const pendingIncidents = computed(() => incidentSum.value?.pending ?? 0)

const energyKpis = computed(() => {
  const sums = period.value?.sums ?? {}
  const keys = ['electricity_kwh', 'solar_kwh', 'water_m3', 'chilledwater_kwh_eq', 'hotwater_kwh']
  return keys
    .filter((k) => sums[k] != null && !Number.isNaN(Number(sums[k])))
    .map((k) => ({
      key: k,
      ...metricMeta[k],
      value: Number(sums[k]),
    }))
})

function fmtNum(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(n)
}

/** 系统状态 + 能源累计合并为单一 KPI 阵列（含色带 / 数字动画） */
const coreKpis = computed(() => {
  const rows = []
  const ok = health.value?.status === 'ok'
  rows.push({
    key: 'health',
    label: '数据服务',
    display: ok ? '正常' : '离线',
    unit: '',
    tag: ok ? '运行中' : '异常',
    tagClass: ok ? 'is-ok' : 'is-danger',
    stripClass: ok ? '' : 'dash-kpi-card--strip-danger',
    animValue: null,
    animDigits: 0,
  })
  const pend = pendingIncidents.value
  rows.push({
    key: 'pending',
    label: '待处理工单',
    display: String(pend),
    unit: '条',
    tag: pend > 0 ? '待办' : '已清零',
    tagClass: pend > 0 ? 'is-warn' : 'is-muted',
    stripClass: pend > 0 ? 'dash-kpi-card--strip-warn' : '',
    animValue: pend,
    animDigits: 0,
  })
  const nBuild = buildings.value?.items?.length ?? 0
  rows.push({
    key: 'buildings',
    label: '监测建筑',
    display: String(nBuild),
    unit: '栋',
    tag: '监测中',
    tagClass: 'is-info',
    stripClass: '',
    animValue: nBuild,
    animDigits: 0,
  })
  const ap = anomalyPct.value
  const apNum = ap != null ? Number(ap) : null
  rows.push({
    key: 'anomaly',
    label: '异常用电占比',
    display: ap != null ? ap : '—',
    unit: ap != null ? '%' : '',
    tag: anomalySerious.value ? '偏高' : anomalyWarn.value ? '关注' : '正常',
    tagClass: anomalySerious.value ? 'is-danger' : anomalyWarn.value ? 'is-warn' : 'is-ok',
    stripClass: anomalySerious.value
      ? 'dash-kpi-card--strip-danger'
      : anomalyWarn.value
        ? 'dash-kpi-card--strip-warn'
        : '',
    animValue: apNum,
    animDigits: 2,
  })
  for (const row of energyKpis.value) {
    rows.push({
      key: `e-${row.key}`,
      label: row.label,
      display: fmtNum(row.value),
      unit: row.unit,
      tag: '全库累计',
      tagClass: 'is-info',
      stripClass: '',
      animValue: row.value,
      animDigits: 2,
    })
  }
  return rows
})

const pieOption = computed(() => {
  const sums = period.value?.sums ?? {}
  const parts = [
    { name: '市电', value: Number(sums.electricity_kwh) || 0 },
    { name: '光伏', value: Number(sums.solar_kwh) || 0 },
    { name: '冷量当量', value: Number(sums.chilledwater_kwh_eq) || 0 },
    { name: '热水', value: Number(sums.hotwater_kwh) || 0 },
  ].filter((p) => p.value > 0)
  if (parts.length === 0) return null
  const sel = METRIC_TO_PIE_NAME[selectedMetric.value] ?? '市电'
  return {
    color: ['#1890ff', '#52c41a', '#69c0ff', '#95de64'],
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { color: '#595959', fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '46%'],
        avoidLabelOverlap: true,
        selectedMode: 'single',
        selectedOffset: 6,
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: { color: '#595959', fontSize: 11 },
        data: parts.map((p) => ({
          ...p,
          selected: p.name === sel,
        })),
      },
    ],
  }
})

const lineChartHeading = computed(() => {
  const m = selectedMetric.value
  const lab = metricMeta[m]?.label ?? METRIC_LABEL_SHORT[m] ?? '市电用电'
  return `${lab}趋势`
})

const lineOption = computed(() => {
  const labels = timeseries.value?.labels ?? []
  const values = timeseries.value?.values ?? []
  const unit = timeseries.value?.unit_hint ?? 'kWh'
  if (!labels.length) return null
  const nums = values
    .map((v) => (v == null || Number.isNaN(Number(v)) ? null : Number(v)))
    .filter((v) => v != null)
  const mean = nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null
  return {
    color: ['#1890ff'],
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 20, top: 36, bottom: 28 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: '#d9d9d9' } },
      axisLabel: { color: '#8c8c8c', fontSize: 10, rotate: labels.length > 40 ? 35 : 0 },
    },
    yAxis: {
      type: 'value',
      name: unit,
      nameTextStyle: { color: '#8c8c8c', fontSize: 11 },
      axisLine: { show: false },
      axisLabel: { color: '#8c8c8c' },
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
    },
    series: [
      {
        type: 'line',
        data: values,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#1890ff' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(24, 144, 255, 0.28)' },
              { offset: 1, color: 'rgba(24, 144, 255, 0)' },
            ],
          },
        },
        markLine:
          mean != null
            ? {
                silent: true,
                symbol: 'none',
                label: { show: true, formatter: '时段均值', color: '#8c8c8c', fontSize: 11 },
                lineStyle: { type: 'dashed', color: '#faad14', width: 1 },
                data: [{ yAxis: mean }],
              }
            : undefined,
      },
    ],
  }
})

const barBenchmarkOption = computed(() => {
  const labels = benchmark.value?.chart?.labels ?? []
  const scores = benchmark.value?.chart?.scores ?? []
  if (!labels.length) return null
  return {
    color: ['#1890ff'],
    tooltip: { trigger: 'axis' },
    grid: { left: 44, right: 16, top: 24, bottom: labels.length > 6 ? 48 : 32 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { rotate: 28, fontSize: 10, color: '#8c8c8c' },
      axisLine: { lineStyle: { color: '#d9d9d9' } },
    },
    yAxis: {
      type: 'value',
      max: 100,
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
      axisLabel: { color: '#8c8c8c' },
    },
    series: [{ type: 'bar', data: scores, barMaxWidth: 28, itemStyle: { borderRadius: [4, 4, 0, 0] } }],
  }
})

async function loadTimeseriesForBuilding() {
  const bid = buildingIdForSeries.value
  if (!bid) return
  timeseries.value = await api
    .getStatsTimeseries({
      building_id: bid,
      metric: selectedMetric.value,
      limit: 400,
    })
    .catch(() => null)
}

function onPieChartClick(params) {
  const m = PIE_NAME_TO_METRIC[params?.name]
  if (!m) return
  selectedMetric.value = m
  loadTimeseriesForBuilding()
}

async function loadData(showToastError = true, silent = false) {
  if (!silent) loading.value = true
  try {
    const [h, inc, b, bench, per, ano] = await Promise.all([
      api.getHealth().catch(() => null),
      api.getIncidentsSummary().catch(() => null),
      api.getBuildings().catch(() => ({ items: [] })),
      api.getBenchmarkScoreboard({ top_n: 8 }).catch(() => null),
      api.getStatsPeriod({}).catch(() => null),
      api.getStatsAnomalies({ z_threshold: 3 }).catch(() => null),
    ])
    health.value = h
    incidentSum.value = inc
    buildings.value = b
    benchmark.value = bench
    period.value = per
    anomalies.value = ano

    await loadTimeseriesForBuilding()

    lastUpdated.value = new Date()
  } catch (e) {
    if (showToastError) ElMessage.error(e.message ?? '加载失败，请确认后端已启动')
  } finally {
    if (!silent) loading.value = false
  }
}

function goIncidents() {
  router.push('/incidents')
}

function goStats() {
  router.push('/stats')
}

function goBenchmark() {
  router.push('/benchmark')
}

onMounted(() => loadData())
usePolling(() => loadData(false, true), REFRESH_MS)
</script>

<template>
  <div class="dash-container">
    <div v-if="loading" class="dash-skeleton-wrap" aria-busy="true">
      <el-skeleton animated>
        <template #template>
          <el-skeleton-item variant="h3" style="width: 220px; margin-bottom: 16px" />
          <div class="sk-nav">
            <el-skeleton-item v-for="i in 4" :key="i" variant="rect" class="sk-nav-cell" />
          </div>
          <el-skeleton-item variant="text" style="width: 100px; margin: 16px 0 12px" />
          <div class="sk-kpis">
            <el-skeleton-item v-for="j in 8" :key="j" variant="rect" class="sk-kpi-cell" />
          </div>
          <div class="sk-charts">
            <el-skeleton-item variant="rect" class="sk-chart-main" />
            <el-skeleton-item variant="rect" class="sk-chart-side" />
          </div>
        </template>
      </el-skeleton>
    </div>

    <template v-else>
    <div v-if="anomalySerious || anomalyWarn || pendingIncidents > 0" class="alert-stack">
      <el-alert
        v-if="anomalySerious || anomalyWarn"
        :title="`用电异常监测：异常时段占比 ${anomalyPct ?? '—'}%`"
        :type="anomalySerious ? 'error' : 'warning'"
        show-icon
        :closable="false"
        class="alert-item"
        @click="goStats"
      >
        <template #default>
          <span class="alert-link">建议查看「统计分析」中的异常明细。</span>
        </template>
      </el-alert>
      <el-alert
        v-if="pendingIncidents > 0"
        :title="`运维：当前有 ${pendingIncidents} 条待处理工单`"
        type="warning"
        show-icon
        :closable="false"
        class="alert-item"
        @click="goIncidents"
      >
        <template #default>
          <span class="alert-link">点击进入工单列表处理。</span>
        </template>
      </el-alert>
    </div>

    <header class="dash-header-mini">
      <div class="dash-title-group">
        <h1 class="ems-page-title">能源管理看板</h1>
        <el-tag size="small" effect="plain" type="info">赛题 A08</el-tag>
        <el-tooltip placement="bottom-start" :show-after="200">
          <template #content>
            <div class="dash-about-tip">
              <p>
                赛题 A08 建筑能源智能管理：数据层、查询统计、智慧运维与系统集成统一入口。本页每
                {{ REFRESH_MS / 1000 }} 秒自动刷新核心指标。
              </p>
              <p v-for="block in MODULE_NAV" :key="'tip-' + block.key">
                <strong>{{ navTitleShort(block.title) }}</strong>
                ：{{ block.desc }}
              </p>
            </div>
          </template>
          <el-button
            class="dash-about-btn"
            :icon="InfoFilled"
            circle
            text
            type="primary"
            aria-label="关于系统"
          />
        </el-tooltip>
      </div>
      <div class="dash-action-group">
        <span v-if="lastUpdated" class="dash-update-time">
          更新于 {{ lastUpdated.toLocaleTimeString('zh-CN') }}
        </span>
        <el-tooltip content="刷新数据" placement="bottom">
          <el-button type="primary" :icon="RefreshRight" circle aria-label="刷新" @click="loadData()" />
        </el-tooltip>
      </div>
    </header>

    <el-row :gutter="16" class="nav-matrix">
      <el-col v-for="(block, idx) in MODULE_NAV" :key="block.key" :xs="24" :sm="12" :lg="6">
        <el-tooltip :content="block.desc" placement="top" :show-after="400" :max-width="360">
          <div class="nav-tile">
            <div class="nav-tile-header">
              <span class="nav-id">{{ String(idx + 1).padStart(2, '0') }}</span>
              <span class="nav-title">{{ navTitleShort(block.title) }}</span>
            </div>
            <div class="nav-links">
              <el-button
                v-for="ln in block.links"
                :key="ln.path + ln.label"
                link
                type="primary"
                class="nav-btn"
                @click="goPath(ln.path)"
              >
                <el-icon class="nav-btn-ico"><component :is="ln.icon" /></el-icon>
                {{ ln.label }}
              </el-button>
            </div>
          </div>
        </el-tooltip>
      </el-col>
    </el-row>

    <h2 class="dash-kpi-section-title">核心指标</h2>
    <el-row :gutter="[12, 12]" class="dash-kpi-grid">
      <el-col v-for="k in coreKpis" :key="k.key" :xs="12" :sm="12" :md="8" :lg="6">
        <div class="dash-kpi-card" :class="k.stripClass">
          <div class="dash-kpi-label">{{ k.label }}</div>
          <div class="dash-kpi-value-row">
            <span v-if="typeof k.animValue === 'number' && !Number.isNaN(k.animValue)" class="dash-kpi-num">
              <AnimatedNumber
                :key="`${k.key}-${lastUpdated?.getTime() ?? 0}`"
                :value="k.animValue"
                :digits="k.animDigits ?? 0"
              />
            </span>
            <span v-else class="dash-kpi-num">{{ k.display }}</span>
            <span v-if="k.unit" class="dash-kpi-unit">{{ k.unit }}</span>
          </div>
          <div class="dash-kpi-footer">
            <span class="dash-kpi-status" :class="k.tagClass">{{ k.tag }}</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="[12, 12]" class="dash-chart-row">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" class="ems-card chart-card">
          <template #header>
            <div class="card-h">
              <span>{{ lineChartHeading }}</span>
              <span class="card-h-sub">{{ buildingIdForSeries || '无建筑' }} · 点击饼图可切换指标</span>
            </div>
          </template>
          <AppChart v-if="lineOption" class="chart-h" :option="lineOption" />
          <el-empty v-else description="暂无趋势数据" :image-size="72">
            <template #image>
              <el-icon class="empty-ico" :size="52"><DataLine /></el-icon>
            </template>
            <el-button type="primary" @click="loadData()">重新加载</el-button>
          </el-empty>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="ems-card chart-card">
          <template #header>
            <div class="card-h">
              <span>能源构成（累计）</span>
              <span class="card-h-sub">饼图 · 点击扇区联动趋势</span>
            </div>
          </template>
          <AppChart
            v-if="pieOption"
            class="chart-h chart-h--pie"
            :option="pieOption"
            enable-click
            @chart-click="onPieChartClick"
          />
          <el-empty v-else description="无可拆分能源数据" :image-size="72">
            <template #image>
              <el-icon class="empty-ico" :size="52"><Histogram /></el-icon>
            </template>
            <el-button type="primary" link @click="goPath('/energy')">前往能源监控</el-button>
          </el-empty>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="ems-card chart-card dash-benchmark-card">
      <template #header>
        <div class="card-h card-h--between">
          <div>
            <span>建筑能效对标 TOP8</span>
            <span class="card-h-sub">柱状</span>
          </div>
          <el-button type="primary" link class="link-btn" @click="goBenchmark">详情</el-button>
        </div>
      </template>
      <AppChart v-if="barBenchmarkOption" class="chart-h chart-h--bar" :option="barBenchmarkOption" />
      <el-empty v-else description="暂无对标数据" :image-size="72">
        <template #image>
          <el-icon class="empty-ico" :size="52"><TrendCharts /></el-icon>
        </template>
        <el-button type="primary" link @click="goBenchmark">前往能效对标</el-button>
      </el-empty>
    </el-card>
    </template>
  </div>
</template>

<style scoped>
.alert-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: var(--ems-space-md, 16px);
}

.alert-item {
  cursor: pointer;
}

.alert-link {
  font-size: 13px;
  opacity: 0.85;
}

.dash-about-btn {
  flex-shrink: 0;
}

.nav-btn-ico {
  margin-right: 6px;
  font-size: 15px;
}

.dash-benchmark-card {
  margin-top: var(--ems-space-sm, 8px);
}

.chart-card :deep(.el-card__header) {
  padding: 12px 16px;
  border-bottom: 1px solid var(--ems-border-light, #e5e6eb);
}

.chart-card :deep(.el-card__body) {
  padding: 12px 16px 16px;
}

.card-h {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--ems-text-primary, rgba(0, 0, 0, 0.85));
}

.card-h--between {
  justify-content: space-between;
  align-items: center;
}

.card-h-sub {
  font-size: 12px;
  font-weight: 400;
  color: rgba(0, 0, 0, 0.35);
}

.link-btn {
  min-height: 36px;
  padding: 0 8px;
}

.chart-h {
  width: 100%;
  min-height: 260px;
  height: clamp(220px, 32vw, 320px);
}

.chart-h--pie {
  min-height: 280px;
}

.chart-h--bar {
  min-height: 240px;
}

@media (max-width: 768px) {
  .chart-h {
    min-height: 220px;
  }
}

.dash-skeleton-wrap {
  padding: 4px 0 24px;
}

.sk-nav {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.sk-nav-cell {
  height: 120px;
  border-radius: 8px;
}

.sk-kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.sk-kpi-cell {
  height: 88px;
  border-radius: 8px;
}

.sk-charts {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 12px;
  margin-top: 12px;
}

.sk-chart-main {
  height: 300px;
  border-radius: 8px;
}

.sk-chart-side {
  height: 300px;
  border-radius: 8px;
}

@media (max-width: 992px) {
  .sk-nav,
  .sk-kpis {
    grid-template-columns: repeat(2, 1fr);
  }
  .sk-charts {
    grid-template-columns: 1fr;
  }
}

.empty-ico {
  color: var(--ems-text-placeholder);
  opacity: 0.85;
}
</style>
