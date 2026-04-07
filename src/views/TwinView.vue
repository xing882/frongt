<script setup>
import { computed, onMounted, ref } from 'vue'
import AppChart from '@/components/AppChart.vue'
import * as api from '@/api'
import { apiUrl } from '@/api/client'
import { ElMessage } from 'element-plus'

const scene = ref(null)
const indicators = ref(null)
const suggestions = ref(null)
const forecast = ref(null)
const buildingId = ref('')
const buildings = ref([])
const loading = ref(false)

const forecastOption = computed(() => {
  const labels = forecast.value?.labels ?? forecast.value?.times ?? []
  const values = forecast.value?.values ?? forecast.value?.forecast ?? []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 24, top: 28, bottom: 36 },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value' },
    series: [{ type: 'line', data: values, smooth: true, areaStyle: { opacity: 0.08 } }],
  }
})

async function loadAll() {
  loading.value = true
  try {
    const [t, o, s, f] = await Promise.all([
      api.getV2TwinScene().catch(() => null),
      api.getV2OpsIndicators().catch(() => null),
      api.getV2OpsSuggestions().catch(() => null),
      api
        .getV2ForecastEnergy({
          building_id: buildingId.value || undefined,
          horizon_hours: 48,
        })
        .catch(() => null),
    ])
    scene.value = t
    indicators.value = o
    suggestions.value = s
    forecast.value = f
  } catch (e) {
    ElMessage.error(e.message ?? '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadBuildings() {
  const data = await api.getBuildings().catch(() => ({ items: [] }))
  buildings.value = data.items ?? []
  if (!buildingId.value && buildings.value.length) {
    buildingId.value = buildings.value[0].building_id ?? buildings.value[0].id ?? ''
  }
}

function openReport(kind, format) {
  const q = new URLSearchParams({ file_format: format })
  if (buildingId.value) q.set('building_id', buildingId.value)
  window.open(apiUrl(`/api/v2/reports/${kind}?${q.toString()}`), '_blank')
}

onMounted(async () => {
  await loadBuildings()
  await loadAll()
})
</script>

<template>
  <div v-loading="loading" class="page-twin">
    <el-card shadow="never" class="mb">
      <template #header>
        <div class="head">
          <span>数字孪生 · 运营（V2）</span>
          <div>
            <el-select v-model="buildingId" placeholder="建筑" style="width: 220px" @change="loadAll">
              <el-option
                v-for="b in buildings"
                :key="JSON.stringify(b)"
                :label="b.building_id ?? String(b)"
                :value="b.building_id ?? b.id"
              />
            </el-select>
            <el-button type="primary" @click="loadAll">刷新</el-button>
            <el-button @click="openReport('operations', 'pdf')">运营报告 PDF</el-button>
            <el-button @click="openReport('esg', 'word')">ESG 报告 Word</el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="16">
        <el-col :span="12">
          <h4 class="block-title">场景</h4>
          <pre v-if="scene" class="json-preview">{{ JSON.stringify(scene, null, 2) }}</pre>
          <el-empty v-else description="暂无场景数据" />
        </el-col>
        <el-col :span="12">
          <h4 class="block-title">运营指标</h4>
          <pre v-if="indicators" class="json-preview">{{ JSON.stringify(indicators, null, 2) }}</pre>
          <el-empty v-else description="暂无指标" />
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="never" class="mb">
      <template #header>优化建议</template>
      <el-table v-if="suggestions?.items?.length" :data="suggestions.items" stripe>
        <el-table-column
          v-for="k in Object.keys(suggestions.items[0])"
          :key="k"
          :prop="k"
          :label="k"
          min-width="120"
        />
      </el-table>
      <pre v-else-if="suggestions" class="json-preview">{{ JSON.stringify(suggestions, null, 2) }}</pre>
      <el-empty v-else description="暂无建议" />
    </el-card>

    <el-card shadow="never">
      <template #header>能耗预测（演示）</template>
      <AppChart v-if="forecast && (forecast.labels?.length || forecast.times?.length)" :option="forecastOption" />
      <pre v-else-if="forecast" class="json-preview">{{ JSON.stringify(forecast, null, 2) }}</pre>
      <el-empty v-else description="暂无预测数据" />
    </el-card>
  </div>
</template>

<style scoped>
.page-twin {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.block-title {
  margin: 0 0 8px;
  font-size: 14px;
  color: #334155;
}

.json-preview {
  margin: 0;
  max-height: 320px;
  overflow: auto;
  font-size: 12px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
}

.mb {
  margin-bottom: 0;
}
</style>
