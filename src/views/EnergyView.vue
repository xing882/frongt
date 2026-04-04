<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import * as api from '@/api'
import { ElMessage } from 'element-plus'

const buildings = ref([])
const buildingId = ref('')
const timeFrom = ref('')
const timeTo = ref('')
const limit = ref(200)
const records = ref(null)
const loading = ref(false)

const tableData = computed(() => records.value?.items ?? [])
const columns = computed(() => {
  const row = tableData.value[0]
  if (!row || typeof row !== 'object') return []
  return Object.keys(row)
})

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

async function loadRecords() {
  loading.value = true
  try {
    const params = { limit: limit.value }
    if (buildingId.value) params.building_id = buildingId.value
    if (timeFrom.value) params.time_from = timeFrom.value
    if (timeTo.value) params.time_to = timeTo.value
    records.value = await api.getEnergyRecords(params)
  } catch (e) {
    ElMessage.error(e.message ?? '查询失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadBuildings()
  await loadRecords()
})

watch(buildingId, () => {
  loadRecords()
})
</script>

<template>
  <el-card shadow="never" class="page-card">
    <template #header>
      <span>小时级能耗明细</span>
    </template>

    <el-form :inline="true" class="filter-form">
      <el-form-item label="建筑">
        <el-select v-model="buildingId" clearable placeholder="全部" style="width: 260px">
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
      <el-form-item label="条数">
        <el-input-number v-model="limit" :min="1" :max="10000" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="loadRecords">查询</el-button>
      </el-form-item>
    </el-form>

    <div class="hint">共 {{ records?.count ?? tableData.length }} 条（默认最多 500，可调 limit）</div>

    <el-table v-loading="loading" :data="tableData" stripe border max-height="560" style="width: 100%">
      <el-table-column
        v-for="col in columns"
        :key="col"
        :prop="col"
        :label="col"
        min-width="120"
        show-overflow-tooltip
      />
    </el-table>
  </el-card>
</template>

<style scoped>
.page-card {
  border-radius: 10px;
}

.filter-form {
  margin-bottom: 8px;
}

.hint {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}
</style>
