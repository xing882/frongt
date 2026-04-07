<script setup>
import { computed, onMounted, ref } from 'vue'
import AppChart from '@/components/AppChart.vue'
import * as api from '@/api'
import { ElMessage } from 'element-plus'

const health = ref(null)
const incidentSum = ref(null)
const buildings = ref([])
const benchmark = ref(null)
const loading = ref(true)

const buildingCount = computed(() => buildings.value?.items?.length ?? 0)

const benchChartOption = computed(() => {
  const labels = benchmark.value?.chart?.labels ?? []
  const scores = benchmark.value?.chart?.scores ?? []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 24, top: 32, bottom: 40 },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '分', max: 100 },
    series: [{ type: 'bar', data: scores, itemStyle: { color: '#0ea5e9' } }],
  }
})

async function load() {
  loading.value = true
  try {
    const [h, s, b, bench] = await Promise.all([
      api.getHealth().catch(() => null),
      api.getIncidentsSummary().catch(() => null),
      api.getBuildings().catch(() => ({ items: [] })),
      api.getBenchmarkScoreboard({ top_n: 8 }).catch(() => null),
    ])
    health.value = h
    incidentSum.value = s
    buildings.value = b
    benchmark.value = bench
  } catch (e) {
    ElMessage.error(e.message ?? '加载失败，请确认后端已启动')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-dashboard">
    <el-row :gutter="16">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="kpi-card">
          <div class="kpi-label">服务状态</div>
          <div class="kpi-value ok">{{ health?.status === 'ok' ? '正常' : '—' }}</div>
          <div class="kpi-hint">GET /health</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="kpi-card">
          <div class="kpi-label">待处理工单</div>
          <div class="kpi-value warn">{{ incidentSum?.pending ?? '—' }}</div>
          <div class="kpi-hint">open + in_progress</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="kpi-card">
          <div class="kpi-label">建筑数量</div>
          <div class="kpi-value">{{ buildingCount }}</div>
          <div class="kpi-hint">metadata 建筑列表</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="kpi-card">
          <div class="kpi-label">工单总数</div>
          <div class="kpi-value">{{ incidentSum?.total ?? '—' }}</div>
          <div class="kpi-hint">/api/incidents/summary</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="chart-card" shadow="never">
      <template #header>
        <span>建筑对标排行（演示综合分）</span>
      </template>
      <AppChart v-if="benchmark?.chart" :option="benchChartOption" />
      <el-empty v-else description="暂无对标数据或接口不可用" />
    </el-card>
  </div>
</template>

<style scoped>
.page-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.kpi-card {
  border-radius: 10px;
}

.kpi-label {
  color: #64748b;
  font-size: 13px;
}

.kpi-value {
  margin-top: 8px;
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
}

.kpi-value.ok {
  color: #16a34a;
}

.kpi-value.warn {
  color: #d97706;
}

.kpi-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #94a3b8;
}

.chart-card {
  border-radius: 10px;
}
</style>
