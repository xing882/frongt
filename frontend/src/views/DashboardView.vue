<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Lightning,
  Sunny,
  Odometer,
  Histogram,
  CircleCheck,
  WarningFilled,
  OfficeBuilding,
  RefreshRight,
  TrendCharts,
} from '@element-plus/icons-vue'
import AppChart from '@/components/AppChart.vue'
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

const REFRESH_MS = 30_000

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

const pieOption = computed(() => {
  const sums = period.value?.sums ?? {}
  const parts = [
    { name: '市电', value: Number(sums.electricity_kwh) || 0 },
    { name: '光伏', value: Number(sums.solar_kwh) || 0 },
    { name: '冷量当量', value: Number(sums.chilledwater_kwh_eq) || 0 },
    { name: '热水', value: Number(sums.hotwater_kwh) || 0 },
  ].filter((p) => p.value > 0)
  if (parts.length === 0) return null
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
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: { color: '#595959', fontSize: 11 },
        data: parts,
      },
    ],
  }
})

const lineOption = computed(() => {
  const labels = timeseries.value?.labels ?? []
  const values = timeseries.value?.values ?? []
  const unit = timeseries.value?.unit_hint ?? 'kWh'
  if (!labels.length) return null
  return {
    color: ['#1890ff'],
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 20, top: 28, bottom: 28 },
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
        lineStyle: { width: 2 },
        areaStyle: { color: 'rgba(24,144,255,0.08)' },
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
      metric: 'electricity_kwh',
      limit: 400,
    })
    .catch(() => null)
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
  <div class="dash" v-loading="loading">
    <!-- 告警：异常用电 / 待办工单 -->
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

    <div class="dash-head">
      <div>
        <h1 class="dash-title">能源仪表盘</h1>
        <p class="dash-desc">
          实时汇总能耗与对标数据；每 {{ REFRESH_MS / 1000 }} 秒自动刷新。图表为简洁样式，突出数值与趋势。
        </p>
      </div>
      <div class="dash-actions">
        <span v-if="lastUpdated" class="update-time">
          更新于 {{ lastUpdated.toLocaleTimeString('zh-CN') }}
        </span>
        <el-button class="ems-btn-min" type="primary" :icon="RefreshRight" @click="loadData()">
          刷新
        </el-button>
      </div>
    </div>

    <!-- 系统状态 -->
    <el-row :gutter="[12, 12]" class="section">
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <div class="kpi kpi--ok">
          <div class="kpi-icon" aria-hidden="true">
            <el-icon><CircleCheck /></el-icon>
          </div>
          <div class="kpi-main">
            <div class="kpi-label">数据服务</div>
            <div class="kpi-val">{{ health?.status === 'ok' ? '正常' : '离线' }}</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <div class="kpi" :class="pendingIncidents > 0 ? 'kpi--danger-soft' : 'kpi--neutral'">
          <div class="kpi-icon kpi-icon--warn" aria-hidden="true">
            <el-icon><WarningFilled /></el-icon>
          </div>
          <div class="kpi-main">
            <div class="kpi-label">待处理工单</div>
            <div class="kpi-val" :class="{ 'text-warn': pendingIncidents > 0 }">{{ pendingIncidents }}</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <div class="kpi kpi--neutral">
          <div class="kpi-icon kpi-icon--blue" aria-hidden="true">
            <el-icon><OfficeBuilding /></el-icon>
          </div>
          <div class="kpi-main">
            <div class="kpi-label">监测建筑</div>
            <div class="kpi-val">{{ buildings?.items?.length ?? 0 }}</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <div class="kpi" :class="anomalySerious ? 'kpi--danger-soft' : anomalyWarn ? 'kpi--warn-soft' : 'kpi--neutral'">
          <div class="kpi-icon kpi-icon--muted" aria-hidden="true">
            <el-icon><TrendCharts /></el-icon>
          </div>
          <div class="kpi-main">
            <div class="kpi-label">异常用电占比</div>
            <div
              class="kpi-val"
              :class="{ 'text-danger': anomalySerious, 'text-warn': anomalyWarn }"
            >
              {{ anomalyPct != null ? `${anomalyPct}%` : '—' }}
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 能源累计（电 / 水 / 气类指标由数据集字段决定） -->
    <h2 class="section-title">能源累计（全库时段）</h2>
    <el-row :gutter="[12, 12]" class="section">
      <el-col
        v-for="row in energyKpis"
        :key="row.key"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="energyKpis.length > 4 ? 6 : 8"
      >
        <div class="kpi kpi--energy">
          <div class="kpi-icon kpi-icon--energy" aria-hidden="true">
            <el-icon v-if="row.key === 'electricity_kwh'"><Lightning /></el-icon>
            <el-icon v-else-if="row.key === 'solar_kwh'"><Sunny /></el-icon>
            <el-icon v-else-if="row.key === 'water_m3'"><Odometer /></el-icon>
            <el-icon v-else-if="row.key === 'chilledwater_kwh_eq'"><Histogram /></el-icon>
            <el-icon v-else><Histogram /></el-icon>
          </div>
          <div class="kpi-main">
            <div class="kpi-label">{{ row.label }}</div>
            <div class="kpi-val kpi-val--num">{{ fmtNum(row.value) }}</div>
            <div class="kpi-unit">{{ row.unit }}</div>
          </div>
        </div>
      </el-col>
      <el-col v-if="!energyKpis.length" :span="24">
        <el-empty description="暂无累计能耗字段或数据为空" :image-size="80" />
      </el-col>
    </el-row>

    <!-- 图表：趋势 + 构成 -->
    <el-row :gutter="[12, 12]" class="section chart-row">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="ems-card chart-card">
          <template #header>
            <div class="card-h">
              <span>市电用电趋势</span>
              <span class="card-h-sub">{{ buildingIdForSeries || '无建筑' }} · 折线</span>
            </div>
          </template>
          <AppChart v-if="lineOption" class="chart-h" :option="lineOption" />
          <el-empty v-else description="暂无趋势数据" :image-size="72" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="ems-card chart-card">
          <template #header>
            <div class="card-h">
              <span>能源构成（累计）</span>
              <span class="card-h-sub">饼图</span>
            </div>
          </template>
          <AppChart v-if="pieOption" class="chart-h chart-h--pie" :option="pieOption" />
          <el-empty v-else description="无可拆分能源数据" :image-size="72" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 对标柱状 -->
    <el-card shadow="never" class="ems-card section chart-card">
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
      <el-empty v-else description="暂无对标数据" :image-size="72" />
    </el-card>
  </div>
</template>

<style scoped>
.dash {
  max-width: 1600px;
  margin: 0 auto;
}

.alert-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}

.alert-item {
  cursor: pointer;
}

.alert-link {
  font-size: 13px;
  opacity: 0.85;
}

.dash-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.dash-title {
  margin: 0;
  font-size: clamp(18px, 2.8vw, 22px);
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
}

.dash-desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.45);
  max-width: 52rem;
  line-height: 1.5;
}

.dash-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.update-time {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

.section {
  margin-bottom: 8px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.75);
  margin: 8px 0 12px;
}

.kpi {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid var(--ems-border, #e8e8e8);
  border-radius: var(--ems-card-radius, 6px);
  box-shadow: var(--ems-shadow);
  min-height: 88px;
}

.kpi--ok {
  border-left: 3px solid var(--ems-green, #52c41a);
  background: var(--ems-green-soft, #f6ffed);
}

.kpi--neutral {
  background: #fff;
}

.kpi--energy {
  border-left: 3px solid var(--ems-blue, #1890ff);
  background: linear-gradient(180deg, #fafcff 0%, #fff 100%);
}

.kpi--danger-soft {
  border-left: 3px solid var(--ems-danger, #ff4d4f);
  background: var(--ems-danger-soft, #fff2f0);
}

.kpi--warn-soft {
  border-left: 3px solid var(--ems-warning, #faad14);
  background: var(--ems-warning-soft, #fffbe6);
}

.kpi-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 20px;
  color: #fff;
  background: #8c8c8c;
}

.kpi-icon--blue {
  background: var(--ems-blue, #1890ff);
}

.kpi-icon--warn {
  background: var(--ems-warning, #faad14);
}

.kpi-icon--muted {
  background: #bfbfbf;
}

.kpi-icon--energy {
  background: #69c0ff;
}

.kpi-main {
  flex: 1;
  min-width: 0;
}

.kpi-label {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.45);
  line-height: 1.3;
}

.kpi-val {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
  line-height: 1.2;
}

.kpi-val--num {
  font-variant-numeric: tabular-nums;
}

.kpi-unit {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.35);
  margin-top: 2px;
}

.text-warn {
  color: #d48806 !important;
}

.text-danger {
  color: #cf1322 !important;
}

.chart-row {
  margin-top: 8px;
}

.chart-card :deep(.el-card__header) {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
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
  color: rgba(0, 0, 0, 0.85);
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
  .dash-actions {
    width: 100%;
  }

  .dash-actions .ems-btn-min {
    width: 100%;
  }

  .kpi-val {
    font-size: 20px;
  }

  .chart-h {
    min-height: 220px;
  }
}
</style>
