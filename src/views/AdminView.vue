<script setup>
import { onMounted, ref } from 'vue'
import * as api from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const status = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    status.value = await api.getAdminStatus()
  } catch (e) {
    ElMessage.error(e.message ?? '无法读取管理状态')
  } finally {
    loading.value = false
  }
}

async function reloadData() {
  await ElMessageBox.confirm('将清缓存并重新加载 CSV/司空，确认？', '提示', { type: 'warning' })
  loading.value = true
  try {
    await api.postAdminReload()
    ElMessage.success('已触发 reload')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message ?? '失败')
  } finally {
    loading.value = false
  }
}

async function reindexKb() {
  await ElMessageBox.confirm('重建知识库索引可能较慢，确认？', '提示', { type: 'warning' })
  loading.value = true
  try {
    await api.postAdminKbReindex()
    ElMessage.success('已触发重建')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message ?? '失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <el-card v-loading="loading" shadow="never" class="page-card">
    <template #header>
      <div class="head">
        <span>数据与系统</span>
        <div>
          <el-button @click="load">刷新状态</el-button>
          <el-button type="warning" @click="reloadData">Reload 数据</el-button>
          <el-button type="danger" plain @click="reindexKb">重建 KB 索引</el-button>
        </div>
      </div>
    </template>

    <el-alert
      title="生产环境请为 /api/admin 增加鉴权；当前为演示联调用途。"
      type="warning"
      show-icon
      class="mb"
    />

    <pre v-if="status" class="json-preview">{{ JSON.stringify(status, null, 2) }}</pre>
    <el-empty v-else description="无数据" />
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
  flex-wrap: wrap;
  gap: 8px;
}

.mb {
  margin-bottom: 12px;
}

.json-preview {
  margin: 0;
  max-height: 60vh;
  overflow: auto;
  font-size: 12px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
}
</style>
