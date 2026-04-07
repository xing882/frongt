<script setup>
import { onMounted, ref } from 'vue'
import * as api from '@/api'
import { ElMessage } from 'element-plus'

const kbQ = ref('')
const kbResults = ref(null)
const sikongQ = ref('')
const sikongResults = ref(null)
const ragQuery = ref('空气源热泵能效限定值')
const ragAnswer = ref(null)
const kbStatus = ref(null)
const sikongStatus = ref(null)
const loadingKb = ref(false)
const loadingSi = ref(false)
const loadingRag = ref(false)

async function searchKb() {
  if (!kbQ.value.trim()) {
    ElMessage.warning('请输入检索词')
    return
  }
  loadingKb.value = true
  try {
    kbResults.value = await api.getKbSearch({ q: kbQ.value, limit: 15 })
  } catch (e) {
    ElMessage.error(e.message ?? 'KB 检索失败')
  } finally {
    loadingKb.value = false
  }
}

async function searchSikong() {
  if (!sikongQ.value.trim()) {
    ElMessage.warning('请输入检索词')
    return
  }
  loadingSi.value = true
  try {
    sikongResults.value = await api.getSikongSearch({ q: sikongQ.value, limit: 20 })
  } catch (e) {
    ElMessage.error(e.message ?? '司空检索失败')
  } finally {
    loadingSi.value = false
  }
}

async function runRag() {
  if (!ragQuery.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }
  loadingRag.value = true
  try {
    ragAnswer.value = await api.postAssistantRagAnswer({
      query: ragQuery.value,
      kb_limit: 8,
      sikong_limit: 5,
    })
  } catch (e) {
    ElMessage.error(e.message ?? 'RAG 失败')
  } finally {
    loadingRag.value = false
  }
}

onMounted(async () => {
  try {
    kbStatus.value = await api.getKbStatus().catch(() => null)
    sikongStatus.value = await api.getSikongStatus().catch(() => null)
  } catch {
    /* ignore */
  }
})
</script>

<template>
  <div class="page-knowledge">
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>规范 PDF 检索</template>
          <p class="status-line">
            索引：
            <el-tag :type="kbStatus?.ready ? 'success' : 'info'" size="small">
              {{ kbStatus?.ready ? '就绪' : '未知' }}
            </el-tag>
          </p>
          <el-input v-model="kbQ" placeholder="关键词" clearable @keyup.enter="searchKb" />
          <el-button class="mt" type="primary" :loading="loadingKb" @click="searchKb">检索</el-button>
          <el-table
            v-if="kbResults?.results?.length"
            :data="kbResults.results"
            class="mt"
            max-height="420"
            stripe
          >
            <el-table-column prop="snippet" label="摘要" min-width="220" show-overflow-tooltip />
            <el-table-column prop="source_path" label="来源" min-width="160" show-overflow-tooltip />
            <el-table-column prop="chunk_id" label="chunk" width="90" />
          </el-table>
          <el-empty v-else-if="kbResults" description="无结果" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>司空语料检索</template>
          <p class="status-line">
            行数：{{ sikongStatus?.rows ?? '—' }}
          </p>
          <el-input v-model="sikongQ" placeholder="关键词" clearable @keyup.enter="searchSikong" />
          <el-button class="mt" type="primary" :loading="loadingSi" @click="searchSikong">检索</el-button>
          <el-table
            v-if="sikongResults?.results?.length"
            :data="sikongResults.results"
            class="mt"
            max-height="420"
            stripe
          >
            <el-table-column prop="input" label="输入" min-width="160" show-overflow-tooltip />
            <el-table-column prop="output" label="输出" min-width="220" show-overflow-tooltip />
          </el-table>
          <el-empty v-else-if="sikongResults" description="无结果" />
        </el-card>
      </el-col>
    </el-row>

    <el-card class="mt" shadow="never">
      <template #header>赛题 RAG（规范 PDF + 司空）</template>
      <el-input
        v-model="ragQuery"
        type="textarea"
        :rows="3"
        placeholder="输入自然语言问题"
      />
      <el-button class="mt" type="primary" :loading="loadingRag" @click="runRag">生成回答</el-button>
      <div v-if="ragAnswer" class="rag-block">
        <el-alert :title="ragAnswer.description" type="info" show-icon class="mb" />
        <pre class="answer-text">{{ ragAnswer.answer }}</pre>
        <el-divider />
        <div v-if="ragAnswer.citations?.length" class="citations">
          <div v-for="(c, i) in ragAnswer.citations" :key="i" class="cit">
            {{ typeof c === 'string' ? c : JSON.stringify(c) }}
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.page-knowledge {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-line {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 8px;
}

.mt {
  margin-top: 12px;
}

.mb {
  margin-bottom: 12px;
}

.rag-block {
  margin-top: 12px;
}

.answer-text {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  color: #0f172a;
  background: #f8fafc;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.citations {
  font-size: 13px;
  color: #475569;
}

.cit {
  margin-bottom: 6px;
}
</style>
