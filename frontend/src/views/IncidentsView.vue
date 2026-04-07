<script setup>
import { onMounted, ref } from 'vue'
import * as api from '@/api'
import { ElMessage } from 'element-plus'

const list = ref([])
const summary = ref(null)
const buildings = ref([])
const loading = ref(false)

const dialogVisible = ref(false)
const form = ref({
  title: '',
  building_id: '',
  severity: 'medium',
  status: 'open',
  detail: '',
})

async function loadSummary() {
  summary.value = await api.getIncidentsSummary().catch(() => null)
}

async function loadList() {
  loading.value = true
  try {
    const data = await api.getIncidents({ limit: 200 })
    list.value = data.items ?? []
  } catch (e) {
    ElMessage.error(e.message ?? '加载工单失败')
  } finally {
    loading.value = false
  }
}

async function loadBuildings() {
  const data = await api.getBuildings().catch(() => ({ items: [] }))
  buildings.value = data.items ?? []
}

async function submit() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  loading.value = true
  try {
    await api.postIncident(form.value)
    ElMessage.success('已创建')
    dialogVisible.value = false
    form.value = {
      title: '',
      building_id: '',
      severity: 'medium',
      status: 'open',
      detail: '',
    }
    await loadList()
    await loadSummary()
  } catch (e) {
    ElMessage.error(e.message ?? '创建失败')
  } finally {
    loading.value = false
  }
}

async function patchStatus(row, status) {
  loading.value = true
  try {
    const id = row.incident_id ?? row.id
    if (!id) throw new Error('缺少工单 id')
    await api.patchIncident(id, { status })
    ElMessage.success('已更新')
    await loadList()
    await loadSummary()
  } catch (e) {
    ElMessage.error(e.message ?? '更新失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadBuildings()
  await loadSummary()
  await loadList()
})
</script>

<template>
  <el-card shadow="never" class="page-card">
    <template #header>
      <div class="head">
        <span>运维工单</span>
        <div>
          <el-button type="primary" @click="dialogVisible = true">新建工单</el-button>
          <el-button @click="loadList">刷新</el-button>
        </div>
      </div>
    </template>

    <el-row :gutter="16" class="summary-row">
      <el-col :span="6">
        <el-statistic title="待处理 (open+进行中)" :value="summary?.pending ?? 0" />
      </el-col>
      <el-col :span="6">
        <el-statistic title="总数" :value="summary?.total ?? 0" />
      </el-col>
      <el-col v-for="(n, k) in summary?.by_status ?? {}" :key="k" :span="4">
        <el-statistic :title="String(k)" :value="n" />
      </el-col>
    </el-row>

    <el-table v-loading="loading" :data="list" stripe border class="mt">
      <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
      <el-table-column prop="building_id" label="建筑" width="200" show-overflow-tooltip />
      <el-table-column prop="severity" label="级别" width="100" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="detail" label="详情" min-width="200" show-overflow-tooltip />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="patchStatus(row, 'in_progress')">受理</el-button>
          <el-button size="small" type="success" @click="patchStatus(row, 'resolved')">解决</el-button>
          <el-button size="small" type="info" @click="patchStatus(row, 'closed')">关闭</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="新建工单" width="520px">
      <el-form label-width="88px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="建筑">
          <el-select v-model="form.building_id" clearable filterable style="width: 100%">
            <el-option
              v-for="b in buildings"
              :key="JSON.stringify(b)"
              :label="b.building_id ?? String(b)"
              :value="b.building_id ?? b.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="级别">
          <el-select v-model="form.severity" style="width: 100%">
            <el-option label="low" value="low" />
            <el-option label="medium" value="medium" />
            <el-option label="high" value="high" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="open" value="open" />
            <el-option label="in_progress" value="in_progress" />
          </el-select>
        </el-form-item>
        <el-form-item label="详情">
          <el-input v-model="form.detail" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submit">提交</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<style scoped>
.page-card {
  border-radius: 10px;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.summary-row {
  margin-bottom: 12px;
}

.mt {
  margin-top: 12px;
}
</style>
