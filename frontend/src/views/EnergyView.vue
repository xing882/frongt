<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { Calendar } from '@element-plus/icons-vue'
import AppChart from '@/components/AppChart.vue'
import * as api from '@/api'
import { ElMessage } from 'element-plus'
import { buildDonutRowFromSums, comboBarLineOption, operationCurveOption } from '@/utils/myemsCharts'

const buildings = ref([])
const buildingId = ref('')
const compareType = ref('none')
const timeSpan = ref('hour')
const dateRange = ref(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const records = ref(null)
const loading = ref(false)
/** 避免首屏 loadBuildings 设置 buildingId 时触发重复请求 */
const filtersReady = ref(false)

const periodSummary = ref(null)
const anomaliesKpi = ref(null)
const incidentsSummary = ref(null)
const tsChart = ref(null)

const sortBy = ref('monitor_time')
const sortOrder = ref('asc')

const tableData = computed(() => records.value?.items ?? [])
const columns = computed(() => {
  const row = tableData.value[0]
  if (!row || typeof row !== 'object') return []
  return Object.keys(row)
})

const chartBuildingId = computed(() => {
  if (buildingId.value) return buildingId.value
  const b = buildings.value[0]
  return b?.building_id ?? b?.id ?? ''
})

const tableHeight = computed(() => {
  if (typeof window !== 'undefined' && window.innerWidth < 768) return 320
  return 420
})

const dateError = ref('')

const donutOptions = computed(() =>
  buildDonutRowFromSums(periodSummary.value?.sums, periodSummary.value?.means),
)

const comboOption = computed(() => {
  const labels = tsChart.value?.labels ?? []
  const raw = tsChart.value?.values ?? []
  const values = raw.map((v) => (v == null ? 0 : Number(v)))
  return comboBarLineOption(labels, values)
})

const curveOption = computed(() => {
  const labels = tsChart.value?.labels ?? []
  const raw = tsChart.value?.values ?? []
  const values = raw.map((v) => (v == null ? 0 : Number(v)))
  return operationCurveOption(labels, values)
})

const kpis = computed(() => {
  const sums = periodSummary.value?.sums ?? {}
  const elec = Number(sums.electricity_kwh)
  const water = Number(sums.water_m3)
  const rows = periodSummary.value?.rows ?? 0
  const ar = anomaliesKpi.value?.ratio
  const pct = ar != null ? (Number(ar) * 100).toFixed(2) : '—'
  const trendUp = ar != null && ar > 0.05
  return [
    {
      label: '市电累计',
      value: Number.isFinite(elec) ? elec.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) : '—',
      unit: 'kWh',
      trend: '较异常阈值',
      trendDir: trendUp ? 'up' : 'down',
      trendText: trendUp ? `异常占比 ${pct}%` : `异常占比 ${pct}%`,
    },
    {
      label: '用水累计',
      value: Number.isFinite(water) ? water.toLocaleString('zh-CN', { maximumFractionDigits: 1 }) : '—',
      unit: 'm³',
      trend: '筛选期内',
      trendDir: 'neutral',
      trendText: '合计',
    },
    {
      label: '数据行数',
      value: String(rows),
      unit: '行',
      trend: '时段内',
      trendDir: 'neutral',
      trendText: '小时粒度',
    },
    {
      label: '待处理工单',
      value: String(incidentsSummary.value?.pending ?? '—'),
      unit: '条',
      trend: '运维',
      trendDir: 'neutral',
      trendText: '实时',
    },
  ]
})

function headerCellStyle() {
  return { background: '#fafafa', color: 'rgba(0,0,0,0.75)', fontWeight: 600 }
}

function cellStyle() {
  return { padding: '10px 0' }
}

function validateRange() {
  dateError.value = ''
  if (!dateRange.value || !Array.isArray(dateRange.value) || dateRange.value.length !== 2) {
    return true
  }
  const [a, b] = dateRange.value
  if (a && b && new Date(a).getTime() > new Date(b).getTime()) {
    dateError.value = '开始时间不能晚于结束时间'
    return false
  }
  return true
}

function rangeToParams() {
  if (!dateRange.value || !Array.isArray(dateRange.value) || dateRange.value.length !== 2) {
    return { time_from: undefined, time_to: undefined }
  }
  const [start, end] = dateRange.value
  if (!start || !end) return { time_from: undefined, time_to: undefined }
  return { time_from: start, time_to: end }
}

async function loadBuildings() {
  try {
    const data = await api.getBuildings()
    buildings.value = data.items ?? []
    if (!buildingId.value && buildings.value.length) {
      buildingId.value = buildings.value[0].building_id ?? buildings.value[0].id ?? ''
    }
  } catch (e) {
    ElMessage.error(e.message ?? '加载建筑列表失败')
  }
}

async function loadContext() {
  const { time_from, time_to } = rangeToParams()
  const params = {}
  if (buildingId.value) params.building_id = buildingId.value
  if (time_from) params.time_from = time_from
  if (time_to) params.time_to = time_to

  const [per, ano, inc] = await Promise.all([
    api.getStatsPeriod(params).catch(() => null),
    api.getStatsAnomalies({ ...params, z_threshold: 3 }).catch(() => null),
    api.getIncidentsSummary().catch(() => null),
  ])
  periodSummary.value = per
  anomaliesKpi.value = ano
  incidentsSummary.value = inc

  const bid = chartBuildingId.value
  if (bid) {
    tsChart.value = await api
      .getStatsTimeseries({
        building_id: bid,
        metric: 'electricity_kwh',
        limit: 500,
        ...(time_from ? { time_from } : {}),
        ...(time_to ? { time_to } : {}),
      })
      .catch(() => null)
  } else {
    tsChart.value = null
  }
}

async function loadRecords({ notifySuccess = false } = {}) {
  if (!validateRange()) {
    ElMessage.warning(dateError.value)
    return
  }
  loading.value = true
  try {
    const { time_from, time_to } = rangeToParams()
    const offset = (page.value - 1) * pageSize.value
    const params = {
      limit: pageSize.value,
      offset,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    }
    if (buildingId.value) params.building_id = buildingId.value
    if (time_from) params.time_from = time_from
    if (time_to) params.time_to = time_to

    const data = await api.getEnergyRecords(params)
    records.value = data
    total.value = Number(data.total ?? 0)

    if (notifySuccess) {
      ElMessage.success({
        message: `已加载 ${data.items?.length ?? 0} 条 / 共 ${total.value} 条`,
        duration: 2000,
        showClose: true,
      })
    }
  } catch (e) {
    ElMessage.error(e.message ?? '查询失败')
  } finally {
    loading.value = false
  }
}

async function applyToolbarFilters() {
  if (!validateRange()) {
    ElMessage.warning(dateError.value)
    return
  }
  page.value = 1
  loading.value = true
  try {
    await loadContext()
    await loadRecords({ notifySuccess: false })
  } finally {
    loading.value = false
  }
}

function onSortChange({ prop, order }) {
  if (!prop || !order) {
    sortBy.value = 'monitor_time'
    sortOrder.value = 'asc'
  } else {
    sortBy.value = prop
    sortOrder.value = order === 'descending' ? 'desc' : 'asc'
  }
  page.value = 1
  loadRecords({ notifySuccess: true })
}

function onPageChange() {
  loadRecords({ notifySuccess: false })
}

function onPageSizeChange() {
  page.value = 1
  loadRecords({ notifySuccess: false })
}

onMounted(async () => {
  await loadBuildings()
  await loadContext()
  await loadRecords({ notifySuccess: false })
  filtersReady.value = true
})

watch(
  [buildingId, dateRange],
  async () => {
    if (!filtersReady.value) return
    await applyToolbarFilters()
  },
  { deep: true },
)
</script>

<template>
  <div class="myems-page energy-view">
    <h1 class="myems-page-title">能源监控</h1>
    <p class="myems-page-desc">空间与时间筛选、分项占比、趋势与明细表（布局参考 MyEMS）。</p>

    <div class="myems-toolbar">
      <el-form label-width="72px" class="toolbar-form">
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
              <el-select v-model="compareType" placeholder="无" class="w-full">
                <el-option label="无" value="none" />
                <el-option label="同比(占位)" value="yoy" disabled />
                <el-option label="环比(占位)" value="mom" disabled />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :md="5">
            <el-form-item label="时间粒度">
              <el-select v-model="timeSpan" class="w-full">
                <el-option label="小时" value="hour" />
                <el-option label="日(占位)" value="day" disabled />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="24" :md="8">
            <el-form-item :error="dateError">
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
                @change="validateRange"
              />
            </el-form-item>
          </el-col>
        </el-row>
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
        <span class="section-hint">基于时段汇总 sums</span>
      </div>
      <el-row :gutter="12" class="myems-donut-grid">
        <el-col v-for="(opt, idx) in donutOptions" :key="idx" :xs="24" :sm="12" :md="6">
          <AppChart class="chart-mini" :option="opt" />
        </el-col>
      </el-row>
    </div>

    <div class="myems-section">
      <div class="myems-section-head">
        <span>报告期用电 · 柱线组合</span>
        <span class="section-hint">建筑 {{ chartBuildingId || '—' }}</span>
      </div>
      <AppChart v-if="tsChart?.labels?.length" class="chart-combo" :option="comboOption" />
      <el-empty v-else description="请选择空间或等待时序数据；变更顶部筛选后将自动加载" :image-size="72" />
    </div>

    <div class="myems-section">
      <div class="myems-section-head">
        <span>运行曲线</span>
        <span class="section-hint">市电 kWh/h</span>
      </div>
      <AppChart v-if="tsChart?.labels?.length" class="chart-curve" :option="curveOption" />
      <el-empty v-else description="无时序数据" :image-size="72" />
    </div>

    <div class="myems-section">
      <div class="myems-section-head">
        <span>详细数据</span>
        <span class="section-hint">共 {{ total }} 条</span>
      </div>
      <div class="table-wrap">
        <el-table
          v-loading="loading"
          :data="tableData"
          stripe
          border
          class="data-table"
          :height="tableHeight"
          :header-cell-style="headerCellStyle"
          :cell-style="cellStyle"
          :default-sort="{ prop: 'monitor_time', order: 'ascending' }"
          @sort-change="onSortChange"
        >
          <el-table-column
            v-for="col in columns"
            :key="col"
            :prop="col"
            :label="col"
            :min-width="
              col === 'monitor_time' ? 168 : col.includes('electricity') || col.includes('kwh') ? 130 : 120
            "
            sortable="custom"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <span
                v-if="col === 'electricity_kwh' || (col.includes('kwh') && col !== 'monitor_time')"
                class="num-highlight"
              >
                {{ row[col] }}
              </span>
              <span v-else>{{ row[col] }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="pager-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          :disabled="loading"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.w-full {
  width: 100%;
}

.toolbar-form {
  margin: 0;
}

.label-cal {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.section-hint {
  font-size: 12px;
  font-weight: 400;
  color: rgba(0, 0, 0, 0.35);
}

.chart-combo,
.chart-curve {
  width: 100%;
  min-height: 300px;
  height: 340px;
}

.chart-mini {
  min-height: 230px;
  height: 230px;
}

.table-wrap {
  overflow-x: auto;
}

.data-table {
  --el-table-border-color: #f0f0f0;
}

.num-highlight {
  font-weight: 600;
  color: #096dd9;
  font-variant-numeric: tabular-nums;
}

.pager-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

@media (max-width: 768px) {
  .chart-combo,
  .chart-curve {
    height: 280px;
  }
}
</style>
