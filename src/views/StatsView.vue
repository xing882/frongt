<script setup>
import { computed, onMounted, ref } from 'vue'
import AppChart from '@/components/AppChart.vue'
import * as api from '@/api'
import { apiUrl } from '@/api/client'
import { ElMessage } from 'element-plus'

const buildings = ref([])
const buildingId = ref('')
const timeFrom = ref('')
const timeTo = ref('')
const activeTab = ref('period')

const periodData = ref(null)
const anomalies = ref(null)
const cop = ref(null)
const timeseries = ref(null)
const metrics = ref(null)

const metric = ref('electricity_kwh')
const tsLimit = ref(800)

const loading = ref(false)

const periodKeys = computed(() => {
  const sums = periodData.value?.sums
  if (!sums || typeof sums !== 'object') return []
  return Object.keys(sums)
})

const lineOption = computed(() => {
  const labels = timeseries.value?.labels ?? []
  const values = timeseries.value?.values ?? []
  const name = timeseries.value?.metric ?? 'metric'
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 56, right: 24, top: 32, bottom: 48 },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 25 } },
    yAxis: { type: 'value', name: timeseries.value?.unit_hint ?? '' },
    series: [{ type: 'line', name, data: values, smooth: true, showSymbol: false }],
  }
})

async function loadBuildings() {
  const data = await api.getBuildings()
  buildings.value = data.items ?? []
  if (!buildingId.value && buildings.value.length) {
    buildingId.value = buildings.value[0].building_id ?? buildings.value[0].id ?? ''
  }
}

async function loadPeriod() {
  loading.value = true
  try {
    const params = {}
    if (buildingId.value) params.building_id = buildingId.value
    if (timeFrom.value) params.time_from = timeFrom.value
    if (timeTo.value) params.time_to = timeTo.value
    periodData.value = await api.getStatsPeriod(params)
  } catch (e) {
    ElMessage.error(e.message ?? '时段统计失败')
  } finally {
    loading.value = false
  }
}

async function loadAnomalies() {
  loading.value = true
  try {
    const params = { z_threshold: 3 }
    if (buildingId.value) params.building_id = buildingId.value
    if (timeFrom.value) params.time_from = timeFrom.value
    if (timeTo.value) params.time_to = timeTo.value
    anomalies.value = await api.getStatsAnomalies(params)
  } catch (e) {
    ElMessage.error(e.message ?? '异常检测失败')
  } finally {
    loading.value = false
  }
}

async function loadCop() {
  loading.value = true
  try {
    const params = {}
    if (buildingId.value) params.building_id = buildingId.value
    if (timeFrom.value) params.time_from = timeFrom.value
    if (timeTo.value) params.time_to = timeTo.value
    cop.value = await api.getStatsCopProxy(params)
  } catch (e) {
    ElMessage.error(e.message ?? 'COP 演示失败')
  } finally {
    loading.value = false
  }
}

async function loadTimeseries() {
  if (!buildingId.value) {
    ElMessage.warning('请先选择建筑')
    return
  }
  loading.value = true
  try {
    const params = {
      building_id: buildingId.value,
      metric: metric.value,
      limit: tsLimit.value,
    }
    if (timeFrom.value) params.time_from = timeFrom.value
    if (timeTo.value) params.time_to = timeTo.value
    timeseries.value = await api.getStatsTimeseries(params)
  } catch (e) {
    ElMessage.error(e.message ?? '时序加载失败')
  } finally {
    loading.value = false
  }
}

async function loadMetrics() {
  try {
    metrics.value = await api.getMetricsCatalog()
  } catch {
    metrics.value = null
  }
}

function exportCsv() {
  const q = new URLSearchParams()
  if (buildingId.value) q.set('building_id', buildingId.value)
  if (timeFrom.value) q.set('time_from', timeFrom.value)
  if (timeTo.value) q.set('time_to', timeTo.value)
  const qs = q.toString()
  const url = apiUrl(`/api/stats/export/csv${qs ? `?${qs}` : ''}`)
  window.open(url, '_blank')
}

onMounted(async () => {
  try {
    await loadBuildings()
    await loadMetrics()
    await loadPeriod()
  } catch (e) {
    ElMessage.error(e.message ?? '初始化失败')
  }
})
</script>

<template>
  <el-card shadow="never" class="page-card">
    <template #header>
      <div class="card-head">
        <span>统计分析</span>
        <el-button type="success" plain @click="exportCsv">导出 CSV</el-button>
      </div>
    </template>

    <el-form :inline="true" class="filter-form">
      <el-form-item label="建筑">
        <el-select v-model="buildingId" placeholder="选择建筑" style="width: 260px">
          <el-option
            v-for="b in buildings"
            :key="JSON.stringify(b)"
            :label="b.building_id ?? b.name ?? String(b)"
            :value="b.building_id ?? b.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="开始">
        <el-input v-model="timeFrom" placeholder="YYYY-MM-DD HH:MM:SS" clearable style="width: 200px" />
      </el-form-item>
      <el-form-item label="结束">
        <el-input v-model="timeTo" placeholder="YYYY-MM-DD HH:MM:SS" clearable style="width: 200px" />
      </el-form-item>
    </el-form>

    <el-tabs v-model="activeTab" @tab-change="(name) => {
      if (name === 'period') loadPeriod()
      else if (name === 'anomalies') loadAnomalies()
      else if (name === 'cop') loadCop()
      else if (name === 'series') loadTimeseries()
    }">
      <el-tab-pane label="时段汇总" name="period">
        <div v-loading="loading">
          <el-descriptions v-if="periodData" :column="2" border>
            <el-descriptions-item label="时间范围">
              {{ periodData.time_range?.min }} — {{ periodData.time_range?.max }}
            </el-descriptions-item>
            <el-descriptions-item label="行数">{{ periodData.rows }}</el-descriptions-item>
          </el-descriptions>
          <el-table
            v-if="periodKeys.length"
            :data="periodKeys.map((k) => ({ key: k, sum: periodData.sums[k], mean: periodData.means[k] }))"
            stripe
            class="mt"
          >
            <el-table-column prop="key" label="字段" />
            <el-table-column prop="sum" label="合计" />
            <el-table-column prop="mean" label="均值" />
          </el-table>
          <el-button class="mt" type="primary" @click="loadPeriod">刷新</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="用电异常(z-score)" name="anomalies">
        <div v-loading="loading">
          <el-descriptions v-if="anomalies" :column="2" border>
            <el-descriptions-item label="总小时数">{{ anomalies.total_hours }}</el-descriptions-item>
            <el-descriptions-item label="异常小时">{{ anomalies.anomaly_hours }}</el-descriptions-item>
            <el-descriptions-item label="占比">{{ anomalies.ratio }}</el-descriptions-item>
            <el-descriptions-item label="阈值 z">{{ anomalies.z_threshold }}</el-descriptions-item>
          </el-descriptions>
          <el-table v-if="anomalies?.samples?.length" :data="anomalies.samples" stripe class="mt" max-height="400">
            <el-table-column
              v-for="k in Object.keys(anomalies.samples[0])"
              :key="k"
              :prop="k"
              :label="k"
              min-width="120"
            />
          </el-table>
          <el-button class="mt" type="primary" @click="loadAnomalies">刷新</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="COP 演示" name="cop">
        <div v-loading="loading">
          <el-alert
            v-if="cop?.note || cop?.description"
            :title="cop?.note || cop?.description"
            type="info"
            show-icon
            class="mb"
          />
          <el-descriptions v-if="cop" :column="1" border>
            <el-descriptions-item label="有效小时">{{ cop.valid_hours }}</el-descriptions-item>
            <el-descriptions-item label="均值(冷量/电)">{{ cop.mean_chilled_over_elec }}</el-descriptions-item>
            <el-descriptions-item label="中位数">{{ cop.median_chilled_over_elec }}</el-descriptions-item>
          </el-descriptions>
          <el-button class="mt" type="primary" @click="loadCop">刷新</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="时序图表" name="series">
        <el-form :inline="true">
          <el-form-item label="指标">
            <el-select v-model="metric" style="width: 220px">
              <el-option
                v-for="m in metrics?.items ?? []"
                :key="m.metric"
                :label="`${m.label} (${m.metric})`"
                :value="m.metric"
              />
              <el-option v-if="!metrics?.items?.length" label="electricity_kwh" value="electricity_kwh" />
            </el-select>
          </el-form-item>
          <el-form-item label="点数">
            <el-input-number v-model="tsLimit" :min="50" :max="10000" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="loadTimeseries">加载曲线</el-button>
          </el-form-item>
        </el-form>
        <AppChart v-if="timeseries?.labels?.length" :option="lineOption" />
        <el-empty v-else description="选择建筑后点击加载曲线" />
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<style scoped>
.page-card {
  border-radius: 10px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.filter-form {
  margin-bottom: 8px;
}

.mt {
  margin-top: 12px;
}

.mb {
  margin-bottom: 12px;
}
</style>
