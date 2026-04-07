<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { Calendar } from '@element-plus/icons-vue'
import AppChart from '@/components/AppChart.vue'
import * as api from '@/api'
import { apiUrl } from '@/api/client'
import { ElMessage } from 'element-plus'
import { buildDonutRowFromSums, comboBarLineOption, operationCurveOption } from '@/utils/myemsCharts'
import { buildPeriodTableRows, formatIsoRange } from '@/utils/statsDisplay'

const buildings = ref([])
const buildingId = ref('')
const compareType = ref('none')
const dateRange = ref(null)
const loading = ref(false)
/** 避免首屏 loadBuildings 设置 buildingId 时触发重复请求 */
const toolbarReady = ref(false)

const periodData = ref(null)
const anomalies = ref(null)
const cop = ref(null)
const timeseries = ref(null)
const metrics = ref(null)
const metric = ref('electricity_kwh')
const tsLimit = ref(600)

const activeTab = ref('period')

const chartBuildingId = computed(() => {
  if (buildingId.value) return buildingId.value
  const b = buildings.value[0]
  return b?.building_id ?? b?.id ?? ''
})

const donutOptions = computed(() => buildDonutRowFromSums(periodData.value?.sums, periodData.value?.means))

const comboOption = computed(() => {
  const labels = timeseries.value?.labels ?? []
  const raw = timeseries.value?.values ?? []
  const values = raw.map((v) => (v == null ? 0 : Number(v)))
  return comboBarLineOption(labels, values)
})

const curveOption = computed(() => {
  const labels = timeseries.value?.labels ?? []
  const raw = timeseries.value?.values ?? []
  const values = raw.map((v) => (v == null ? 0 : Number(v)))
  return operationCurveOption(labels, values)
})

const kpis = computed(() => {
  const sums = periodData.value?.sums ?? {}
  const elec = Number(sums.electricity_kwh)
  const ar = anomalies.value?.ratio
  const arN = ar != null ? Number(ar) : null
  const pct = arN != null ? (arN * 100).toFixed(2) : '—'
  const copv = cop.value?.mean_chilled_over_elec
  return [
    {
      label: '市电累计',
      value: Number.isFinite(elec) ? elec.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) : '—',
      unit: 'kWh',
      trend: '筛选期',
      trendDir: 'neutral',
      trendText: '合计',
    },
    {
      label: '异常用电占比',
      value: pct,
      unit: '%',
      trend: 'z-score',
      trendDir: arN != null && arN > 0.1 ? 'up' : 'down',
      trendText: '演示检测',
    },
    {
      label: '冷/电 比值(演示)',
      value: copv != null ? String(copv) : '—',
      unit: '',
      trend: 'COP 相关',
      trendDir: 'neutral',
      trendText: '小时级',
    },
    {
      label: '时段行数',
      value: String(periodData.value?.rows ?? '—'),
      unit: '行',
      trend: '数据',
      trendDir: 'neutral',
      trendText: '小时粒度',
    },
  ]
})

const periodTableRows = computed(() =>
  buildPeriodTableRows(periodData.value?.sums, periodData.value?.means),
)

const periodTimeRangeText = computed(() =>
  formatIsoRange(periodData.value?.time_range?.min, periodData.value?.time_range?.max),
)

const anomalyRatioPct = computed(() => {
  const r = anomalies.value?.ratio
  if (r == null || Number.isNaN(Number(r))) return '—'
  return `${(Number(r) * 100).toFixed(2)}%`
})

const copDisplay = computed(() => {
  const c = cop.value
  if (!c) return null
  const fmt = (x) =>
    x != null && Number.isFinite(Number(x)) ? Number(x).toLocaleString('zh-CN', { maximumFractionDigits: 4 }) : '—'
  return {
    valid_hours: c.valid_hours,
    mean: fmt(c.mean_chilled_over_elec),
    median: fmt(c.median_chilled_over_elec),
  }
})

function formatAnomalyElecCell(v) {
  if (v === '' || v == null) return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

function rangeToParams() {
  if (!dateRange.value || !Array.isArray(dateRange.value) || dateRange.value.length !== 2) {
    return { time_from: undefined, time_to: undefined }
  }
  const [a, b] = dateRange.value
  if (!a || !b) return { time_from: undefined, time_to: undefined }
  return { time_from: a, time_to: b }
}

function filterParams() {
  const { time_from, time_to } = rangeToParams()
  const params = {}
  if (buildingId.value) params.building_id = buildingId.value
  if (time_from) params.time_from = time_from
  if (time_to) params.time_to = time_to
  return params
}

async function loadBuildings() {
  const data = await api.getBuildings()
  buildings.value = data.items ?? []
  if (!buildingId.value && buildings.value.length) {
    buildingId.value = buildings.value[0].building_id ?? buildings.value[0].id ?? ''
  }
}

async function loadMetrics() {
  try {
    metrics.value = await api.getMetricsCatalog()
  } catch {
    metrics.value = null
  }
}

async function loadAllPanels() {
  const p = filterParams()
  loading.value = true
  try {
    const [per, ano, cp, ts] = await Promise.all([
      api.getStatsPeriod(p).catch(() => null),
      api.getStatsAnomalies({ ...p, z_threshold: 3 }).catch(() => null),
      api.getStatsCopProxy(p).catch(() => null),
      chartBuildingId.value
        ? api
            .getStatsTimeseries({
              building_id: chartBuildingId.value,
              metric: metric.value,
              limit: tsLimit.value,
              ...(p.time_from ? { time_from: p.time_from } : {}),
              ...(p.time_to ? { time_to: p.time_to } : {}),
            })
            .catch(() => null)
        : Promise.resolve(null),
    ])
    periodData.value = per
    anomalies.value = ano
    cop.value = cp
    timeseries.value = ts
  } catch (e) {
    ElMessage.error(e.message ?? '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadTimeseriesOnly() {
  if (!chartBuildingId.value) {
    ElMessage.warning('请选择建筑')
    return
  }
  loading.value = true
  try {
    const p = filterParams()
    timeseries.value = await api.getStatsTimeseries({
      building_id: chartBuildingId.value,
      metric: metric.value,
      limit: tsLimit.value,
      ...(p.time_from ? { time_from: p.time_from } : {}),
      ...(p.time_to ? { time_to: p.time_to } : {}),
    })
  } catch (e) {
    ElMessage.error(e.message ?? '时序加载失败')
  } finally {
    loading.value = false
  }
}

function exportCsv() {
  const p = filterParams()
  const q = new URLSearchParams()
  if (p.building_id) q.set('building_id', p.building_id)
  if (p.time_from) q.set('time_from', p.time_from)
  if (p.time_to) q.set('time_to', p.time_to)
  const url = apiUrl(`/api/stats/export/csv${q.toString() ? `?${q.toString()}` : ''}`)
  window.open(url, '_blank')
}

onMounted(async () => {
  await loadBuildings()
  await loadMetrics()
  await loadAllPanels()
  toolbarReady.value = true
})

watch(
  [buildingId, dateRange],
  async () => {
    if (!toolbarReady.value) return
    await loadAllPanels()
  },
  { deep: true },
)
</script>

<template>
  <div class="myems-page stats-view">
    <h1 class="myems-page-title">数据分析</h1>
    <p class="myems-page-desc">时段汇总、异常、COP 与指标时序；布局与能源监控页一致。</p>

    <div class="myems-toolbar">
      <el-form label-width="72px">
        <el-row :gutter="[12, 10]">
          <el-col :xs="24" :sm="12" :md="6">
            <el-form-item label="空间">
              <el-select v-model="buildingId" clearable placeholder="全部建筑" class="w-full" filterable>
                <el-option
                  v-for="b in buildings"
                  :key="JSON.stringify(b)"
                  :label="b.building_id ?? b.name ?? String(b)"
                  :value="b.building_id ?? b.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :md="5">
            <el-form-item label="比较类型">
              <el-select v-model="compareType" class="w-full">
                <el-option label="无" value="none" />
                <el-option label="同比(占位)" value="yoy" disabled />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="24" :md="13">
            <el-form-item>
              <template #label>
                <span class="label-cal"><el-icon><Calendar /></el-icon> 统计期</span>
              </template>
              <el-date-picker
                v-model="dateRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="开始"
                end-placeholder="结束"
                format="YYYY-MM-DD HH:mm"
                value-format="YYYY-MM-DD HH:mm:ss"
                class="w-full"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <div class="toolbar-actions">
          <el-button @click="exportCsv">导出 CSV</el-button>
        </div>
      </el-form>
    </div>

    <el-row :gutter="12" class="myems-kpi-row">
      <el-col v-for="(k, i) in kpis" :key="i" :xs="24" :sm="12" :md="6">
        <div class="myems-kpi-card">
          <div class="myems-kpi-label">{{ k.label }}</div>
          <div>
            <span class="myems-kpi-value">{{ k.value }}</span>
            <span class="myems-kpi-unit">{{ k.unit }}</span>
          </div>
          <div
            class="myems-kpi-trend"
            :class="{
              'myems-kpi-trend--up': k.trendDir === 'up',
              'myems-kpi-trend--down': k.trendDir === 'down',
            }"
          >
            {{ k.trend }} · {{ k.trendText }}
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="myems-section">
      <div class="myems-section-head">
        <span>分项占比</span>
      </div>
      <el-row :gutter="12" class="myems-donut-grid">
        <el-col v-for="(opt, idx) in donutOptions" :key="idx" :xs="24" :sm="12" :md="6">
          <AppChart class="chart-mini" :option="opt" />
        </el-col>
      </el-row>
    </div>

    <div class="myems-section">
      <div class="myems-section-head">
        <span>报告期趋势 · 柱线组合</span>
        <span class="section-hint">{{ metric }} · {{ chartBuildingId || '—' }}</span>
      </div>
      <AppChart v-if="timeseries?.labels?.length" class="chart-combo" :option="comboOption" />
      <el-empty v-else description="选择空间并等待时序加载" :image-size="72" />
    </div>

    <div class="myems-section">
      <div class="myems-section-head">
        <span>运行曲线</span>
      </div>
      <AppChart v-if="timeseries?.labels?.length" class="chart-curve" :option="curveOption" />
      <el-empty v-else description="无时序" :image-size="72" />
    </div>

    <div class="myems-section">
      <div class="myems-section-head">
        <span>指标与明细</span>
      </div>
      <el-tabs v-model="activeTab" type="card" class="analysis-tabs">
        <el-tab-pane label="时段汇总" name="period">
          <div v-loading="loading" class="detail-tab">
            <template v-if="periodData && periodData.rows > 0">
              <el-descriptions :column="3" border size="small" class="detail-desc mb">
                <el-descriptions-item label="时间范围" :span="2">
                  <span class="detail-mono">{{ periodTimeRangeText }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="数据行数">
                  <el-tag size="small" type="info" effect="plain">{{ periodData.rows }} 行</el-tag>
                </el-descriptions-item>
                <el-descriptions-item v-if="periodData.buildings?.length" label="涉及建筑" :span="3">
                  <span class="detail-buildings">{{ periodData.buildings.join('、') }}</span>
                </el-descriptions-item>
              </el-descriptions>
              <el-table
                v-if="periodTableRows.length"
                :data="periodTableRows"
                stripe
                border
                size="small"
                class="detail-table"
                max-height="440"
                empty-text="无汇总字段"
              >
                <el-table-column prop="label" label="指标" min-width="120" fixed="left" />
                <el-table-column prop="unit" label="单位" width="72" align="center" />
                <el-table-column prop="sumFmt" label="合计" min-width="120" align="right">
                  <template #header>
                    <span>合计</span>
                    <span class="col-hint">累加</span>
                  </template>
                </el-table-column>
                <el-table-column prop="meanFmt" label="均值" min-width="120" align="right">
                  <template #header>
                    <span>均值</span>
                    <span class="col-hint">小时</span>
                  </template>
                </el-table-column>
              </el-table>
              <p class="detail-footnote">
                气温、湿度类指标「合计」无业务含义时显示为 —，请以均值为准。
              </p>
            </template>
            <el-empty v-else description="变更顶部空间或统计期后将自动加载" :image-size="80" />
          </div>
        </el-tab-pane>
        <el-tab-pane label="用电异常" name="anomalies">
          <div v-loading="loading" class="detail-tab">
            <el-alert
              v-if="anomalies?.note"
              :title="anomalies.note"
              type="warning"
              show-icon
              :closable="false"
              class="mb"
            />
            <template v-if="anomalies && anomalies.total_hours > 0">
              <el-descriptions :column="2" border size="small" class="detail-desc mb">
                <el-descriptions-item label="统计小时数">{{ anomalies.total_hours }}</el-descriptions-item>
                <el-descriptions-item label="异常小时数">
                  <el-tag :type="anomalies.anomaly_hours > 0 ? 'warning' : 'success'" size="small" effect="light">
                    {{ anomalies.anomaly_hours }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="异常占比">
                  <span class="detail-em">{{ anomalyRatioPct }}</span>
                  <span class="detail-sub">（相对全部小时）</span>
                </el-descriptions-item>
                <el-descriptions-item label="z 阈值">{{ anomalies.z_threshold }}</el-descriptions-item>
              </el-descriptions>
              <div v-if="anomalies.samples?.length" class="detail-table-wrap">
                <div class="detail-table-title">异常样本（最多 50 条）</div>
                <el-table :data="anomalies.samples" stripe border size="small" class="detail-table" max-height="400">
                  <el-table-column prop="building_id" label="建筑" min-width="200" show-overflow-tooltip />
                  <el-table-column prop="monitor_time" label="监测时间" min-width="168" />
                  <el-table-column label="市电 (kWh)" min-width="110" align="right">
                    <template #default="{ row }">
                      {{ formatAnomalyElecCell(row.electricity_kwh) }}
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <el-empty v-else description="当前阈值下未检出异常小时" :image-size="72" />
            </template>
            <el-empty v-else-if="!loading" description="无异常分析数据" :image-size="80" />
          </div>
        </el-tab-pane>
        <el-tab-pane label="COP 演示" name="cop">
          <div v-loading="loading" class="detail-tab">
            <el-alert
              v-if="cop?.description"
              :title="cop.description"
              type="info"
              show-icon
              :closable="false"
              class="mb"
            />
            <template v-if="cop && cop.valid_hours > 0 && copDisplay">
              <el-descriptions :column="1" border size="small" class="detail-desc">
                <el-descriptions-item label="有效小时数">{{ copDisplay.valid_hours }}</el-descriptions-item>
                <el-descriptions-item label="冷量/市电 · 均值">
                  <span class="detail-mono">{{ copDisplay.mean }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="冷量/市电 · 中位数">
                  <span class="detail-mono">{{ copDisplay.median }}</span>
                </el-descriptions-item>
              </el-descriptions>
            </template>
            <el-alert v-else-if="cop?.note" :title="cop.note" type="warning" show-icon :closable="false" />
            <el-empty v-else-if="!loading" description="暂无 COP 分析结果" :image-size="80" />
          </div>
        </el-tab-pane>
        <el-tab-pane label="时序参数" name="series">
          <div class="detail-tab series-tab-pane">
            <el-form :inline="true" class="series-form">
              <el-form-item label="指标">
                <el-select v-model="metric" style="width: 240px" @change="loadTimeseriesOnly">
                  <el-option
                    v-for="m in metrics?.items ?? []"
                    :key="m.metric"
                    :label="`${m.label} (${m.metric})`"
                    :value="m.metric"
                  />
                  <template v-if="!metrics?.items?.length">
                    <el-option label="市电用电 (electricity_kwh)" value="electricity_kwh" />
                    <el-option label="空气温度 (air_temperature_c)" value="air_temperature_c" />
                    <el-option label="相对湿度 (relative_humidity_pct)" value="relative_humidity_pct" />
                  </template>
                </el-select>
              </el-form-item>
              <el-form-item label="点数">
                <el-input-number v-model="tsLimit" :min="50" :max="10000" @change="loadTimeseriesOnly" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="loading" @click="loadTimeseriesOnly">刷新曲线</el-button>
              </el-form-item>
            </el-form>
            <p class="series-hint">
              上方「柱线组合 / 运行曲线」使用此处指标与点数；修改指标或点数后请点「刷新曲线」。空间与统计期在顶部变更后将自动更新各面板。
            </p>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<style scoped>
.w-full {
  width: 100%;
}

.label-cal {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.toolbar-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}

.section-hint {
  font-size: 12px;
  font-weight: 400;
  color: rgba(0, 0, 0, 0.35);
}

.chart-mini {
  min-height: 230px;
  height: 230px;
}

.chart-combo,
.chart-curve {
  width: 100%;
  min-height: 300px;
  height: 340px;
}

.mb {
  margin-bottom: 12px;
}

.analysis-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.series-form {
  margin-bottom: 8px;
}

.detail-tab {
  min-height: 120px;
}

.detail-desc :deep(.el-descriptions__label) {
  width: 108px;
  font-weight: 500;
}

.detail-mono {
  font-variant-numeric: tabular-nums;
  word-break: break-all;
}

.detail-buildings {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.5;
}

.detail-table :deep(.el-table__header th) {
  background: #fafafa;
}

.col-hint {
  display: block;
  font-size: 11px;
  font-weight: 400;
  color: rgba(0, 0, 0, 0.38);
  line-height: 1.2;
  margin-top: 2px;
}

.detail-footnote {
  margin: 10px 0 0;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.42);
  line-height: 1.5;
}

.detail-em {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.detail-sub {
  margin-left: 6px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.42);
}

.detail-table-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.75);
  margin-bottom: 8px;
}

.detail-table-wrap {
  margin-top: 4px;
}

.series-tab-pane .series-hint {
  margin: 0;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  line-height: 1.5;
}
</style>
