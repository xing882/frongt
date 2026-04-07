<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  OfficeBuilding,
  Picture,
  RefreshRight,
  View,
  Cpu,
  Location,
} from '@element-plus/icons-vue'
import * as api from '@/api'
import { ElMessage } from 'element-plus'
import {
  getMockTwinScene,
  getMockVisionAnalyze,
  getMockVisionUpload,
  ROOM_STATUS_META,
} from '@/utils/twinVisionMock'

const route = useRoute()

const activeTab = ref('scene')

/** 孪生 */
const scene = ref(null)
const loadingScene = ref(false)
const twinFromDemo = ref(false)

const selectedFloorId = ref('')
const selectedRoomId = ref('')

const floors = computed(() => scene.value?.floors ?? [])

const currentFloor = computed(() => floors.value.find((f) => f.floor_id === selectedFloorId.value) ?? null)

const currentRooms = computed(() => currentFloor.value?.rooms ?? [])

const selectedRoom = computed(() => {
  if (!selectedRoomId.value || !currentRooms.value.length) return null
  return currentRooms.value.find((r) => r.id === selectedRoomId.value) ?? null
})

watch(
  floors,
  (list) => {
    if (!list.length) {
      selectedFloorId.value = ''
      return
    }
    if (!list.some((f) => f.floor_id === selectedFloorId.value)) {
      selectedFloorId.value = list[0].floor_id
    }
  },
  { immediate: true },
)

watch([currentRooms, selectedFloorId], () => {
  const rooms = currentRooms.value
  if (!rooms.length) {
    selectedRoomId.value = ''
    return
  }
  if (!rooms.some((r) => r.id === selectedRoomId.value)) {
    selectedRoomId.value = rooms[0].id
  }
})

async function loadScene() {
  loadingScene.value = true
  twinFromDemo.value = false
  try {
    const data = await api.getV2TwinScene().catch(() => null)
    if (data && typeof data === 'object' && Object.keys(data).length) {
      scene.value = data
    } else {
      scene.value = getMockTwinScene()
      twinFromDemo.value = true
    }
  } catch (e) {
    scene.value = getMockTwinScene()
    twinFromDemo.value = true
    ElMessage.warning(e.message ?? '已切换为演示场景数据')
  } finally {
    loadingScene.value = false
  }
}

function selectRoom(roomId) {
  selectedRoomId.value = roomId
}

function statusMeta(status) {
  return ROOM_STATUS_META[status] ?? { label: status || '—', type: 'info' }
}

/** 视觉 */
const analyzeName = ref('meeting_room.jpg')
const analyzeResult = ref(null)
const uploadResult = ref(null)
const visionFromDemoAnalyze = ref(false)
const visionFromDemoUpload = ref(false)

const loadingAnalyze = ref(false)
const loadingUpload = ref(false)

const mode = ref('yolo_world')
const prompt = ref('')
const conf = ref(undefined)
const fileList = ref([])

const previewUrl = ref('')

watch(
  fileList,
  (list) => {
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value)
      previewUrl.value = ''
    }
    const raw = list?.[0]?.raw
    if (raw instanceof File) {
      previewUrl.value = URL.createObjectURL(raw)
    }
  },
  { deep: true },
)

onUnmounted(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})

const detectionRows = computed(() => {
  const r = uploadResult.value
  const boxes = r?.yolo?.boxes ?? r?.boxes
  if (!Array.isArray(boxes)) return []
  return boxes.map((b, i) => ({
    key: i,
    label: b.label ?? '—',
    confidence: b.confidence != null ? Number(b.confidence) : null,
    bbox: Array.isArray(b.bbox) ? b.bbox.join(', ') : String(b.bbox ?? '—'),
  }))
})

async function runAnalyze() {
  loadingAnalyze.value = true
  analyzeResult.value = null
  visionFromDemoAnalyze.value = false
  try {
    const data = await api.postV2VisionAnalyze({
      filename: analyzeName.value || undefined,
    })
    if (data && typeof data === 'object') {
      analyzeResult.value = data
    } else {
      analyzeResult.value = getMockVisionAnalyze(analyzeName.value)
      visionFromDemoAnalyze.value = true
    }
  } catch {
    analyzeResult.value = getMockVisionAnalyze(analyzeName.value)
    visionFromDemoAnalyze.value = true
  } finally {
    loadingAnalyze.value = false
  }
}

async function runUpload() {
  const raw = fileList.value[0]?.raw
  if (!raw || !(raw instanceof File)) {
    ElMessage.warning('请先选择图片文件')
    return
  }
  loadingUpload.value = true
  uploadResult.value = null
  visionFromDemoUpload.value = false
  try {
    const p = { mode: mode.value }
    if (prompt.value.trim()) p.prompt = prompt.value.trim()
    if (conf.value != null && !Number.isNaN(Number(conf.value))) p.conf = Number(conf.value)
    const data = await api.postV2VisionUpload(raw, p)
    if (data && typeof data === 'object') {
      uploadResult.value = data
    } else {
      uploadResult.value = getMockVisionUpload(raw.name)
      visionFromDemoUpload.value = true
    }
  } catch {
    uploadResult.value = getMockVisionUpload(raw.name)
    visionFromDemoUpload.value = true
  } finally {
    loadingUpload.value = false
  }
}

onMounted(() => {
  if (route.query.tab === 'vision') activeTab.value = 'vision'
  loadScene()
})
</script>

<template>
  <div class="myems-page twin-vision-view">
    <h1 class="myems-page-title">孪生与视觉</h1>
    <p class="myems-page-desc">
      数字孪生：楼层 / 空间状态一览（后端就绪后对接真实场景服务）。视觉识别：图片分析与检测框展示（后端就绪后对接 V2 推理）。
    </p>

    <el-tabs v-model="activeTab" class="twin-vision-tabs">
      <!-- ========== 场景孪生 ========== -->
      <el-tab-pane label="场景孪生" name="scene">
        <el-alert
          v-if="twinFromDemo"
          title="当前为前端演示数据"
          type="info"
          show-icon
          :closable="false"
          class="tv-alert"
        >
          后端孪生接口暂无返回或为空时已自动使用本地示例场景，接口联调完成后将显示实时数据。
        </el-alert>

        <div v-loading="loadingScene" class="twin-scene-layout">
          <el-card shadow="never" class="ems-card twin-side-card">
            <template #header>
              <span class="card-title">
                <el-icon><OfficeBuilding /></el-icon>
                建筑与楼层
              </span>
            </template>
            <div v-if="scene" class="building-line">
              <span class="building-name">{{ scene.building_name ?? scene.building_id ?? '—' }}</span>
              <el-tag v-if="scene.building_id" size="small" effect="plain">{{ scene.building_id }}</el-tag>
            </div>
            <el-menu
              v-if="floors.length"
              :key="`floors-${scene?.building_id ?? ''}-${floors.length}`"
              :default-active="selectedFloorId"
              class="floor-menu"
              @select="(id) => (selectedFloorId = id)"
            >
              <el-menu-item v-for="f in floors" :key="f.floor_id" :index="f.floor_id">
                <el-icon><Location /></el-icon>
                <span>{{ f.name ?? f.floor_id }}</span>
                <el-tag size="small" type="info" effect="plain" class="room-count">
                  {{ f.rooms?.length ?? 0 }} 间
                </el-tag>
              </el-menu-item>
            </el-menu>
            <el-empty v-else description="无楼层数据" :image-size="72" />
          </el-card>

          <div class="twin-main">
            <el-card shadow="never" class="ems-card twin-floor-card">
              <template #header>
                <div class="card-head">
                  <span class="card-title">
                    <el-icon><View /></el-icon>
                    楼层空间视图
                    <span v-if="currentFloor" class="floor-sub">· {{ currentFloor.name ?? currentFloor.floor_id }}</span>
                  </span>
                  <el-button type="primary" link :icon="RefreshRight" @click="loadScene">刷新场景</el-button>
                </div>
              </template>

              <div v-if="currentRooms.length" class="room-grid">
                <button
                  v-for="room in currentRooms"
                  :key="room.id"
                  type="button"
                  class="room-tile"
                  :class="{ 'room-tile--active': selectedRoomId === room.id }"
                  @click="selectRoom(room.id)"
                >
                  <div class="room-tile__name">{{ room.name ?? room.id }}</div>
                  <div class="room-tile__id">{{ room.id }}</div>
                  <el-tag :type="statusMeta(room.status).type" size="small" effect="light" class="room-tile__tag">
                    {{ statusMeta(room.status).label }}
                  </el-tag>
                </button>
              </div>
              <el-empty v-else description="该楼层暂无房间节点" :image-size="80" />
            </el-card>

            <el-card v-if="selectedRoom" shadow="never" class="ems-card twin-detail-card">
              <template #header>
                <span class="card-title">
                  <el-icon><Cpu /></el-icon>
                  选中空间详情
                </span>
              </template>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="房间编号">{{ selectedRoom.id }}</el-descriptions-item>
                <el-descriptions-item label="名称">{{ selectedRoom.name ?? '—' }}</el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="statusMeta(selectedRoom.status).type" size="small">
                    {{ statusMeta(selectedRoom.status).label }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item v-if="selectedRoom.area_m2 != null" label="面积 (㎡)">
                  {{ selectedRoom.area_m2 }}
                </el-descriptions-item>
                <el-descriptions-item v-if="selectedRoom.occupancy != null" label="占用率">
                  {{ (Number(selectedRoom.occupancy) * 100).toFixed(0) }}%
                </el-descriptions-item>
                <el-descriptions-item v-if="selectedRoom.device_hint" label="设备提示" :span="2">
                  {{ selectedRoom.device_hint }}
                </el-descriptions-item>
              </el-descriptions>
            </el-card>

            <el-collapse class="twin-json-collapse">
              <el-collapse-item title="原始场景 JSON（联调 / 排错）" name="json">
                <pre v-if="scene" class="json-preview json-preview--twin">{{ JSON.stringify(scene, null, 2) }}</pre>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>
      </el-tab-pane>

      <!-- ========== 视觉识别 ========== -->
      <el-tab-pane label="视觉识别" name="vision">
        <el-row :gutter="16" class="vision-row">
          <el-col :xs="24" :lg="10">
            <div class="vision-stack">
              <el-card shadow="never" class="ems-card">
                <template #header>
                  <span class="card-title">
                    <el-icon><Picture /></el-icon>
                    快速分析（filename）
                  </span>
                </template>
                <p class="hint">对接 <code>POST /api/v2/vision/analyze</code>；后端未就绪时使用演示数据。</p>
                <el-form :inline="true" class="vision-form-inline">
                  <el-form-item label="filename">
                    <el-input v-model="analyzeName" placeholder="示例文件名" clearable style="width: 220px" />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" :loading="loadingAnalyze" @click="runAnalyze">调用 analyze</el-button>
                  </el-form-item>
                </el-form>
                <el-alert
                  v-if="visionFromDemoAnalyze && analyzeResult"
                  type="warning"
                  show-icon
                  :closable="false"
                  class="mini-alert"
                >
                  演示数据：真实结果待后端推理服务接入
                </el-alert>
                <pre v-if="analyzeResult" class="json-preview json-preview--vision">{{ JSON.stringify(analyzeResult, null, 2) }}</pre>
              </el-card>

              <el-card shadow="never" class="ems-card">
                <template #header>
                  <span class="card-title">本地上传（YOLO）</span>
                </template>
                <p class="hint">对接 <code>POST /api/v2/vision/upload</code>，单图、multipart。</p>
                <el-form label-width="88px">
                  <el-form-item label="模式">
                    <el-select v-model="mode" style="width: 200px">
                      <el-option label="yolo_world" value="yolo_world" />
                      <el-option label="yolo_seg" value="yolo_seg" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="prompt">
                    <el-input v-model="prompt" placeholder="YOLO-World 可选" clearable style="max-width: 100%" />
                  </el-form-item>
                  <el-form-item label="conf">
                    <el-input-number v-model="conf" :min="0.02" :max="0.95" :step="0.01" placeholder="默认" />
                  </el-form-item>
                  <el-form-item label="图片">
                    <el-upload
                      v-model:file-list="fileList"
                      drag
                      class="vision-upload"
                      :auto-upload="false"
                      :limit="1"
                      accept="image/*"
                    >
                      <el-icon class="upload-ico"><Picture /></el-icon>
                      <div class="upload-text">拖拽到此处，或点击选择</div>
                      <div class="upload-sub">支持常见图片格式，单张最大以后端限制为准</div>
                    </el-upload>
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" :loading="loadingUpload" :disabled="!fileList.length" @click="runUpload">
                      上传并识别
                    </el-button>
                  </el-form-item>
                </el-form>
              </el-card>
            </div>
          </el-col>

          <el-col :xs="24" :lg="14">
            <el-card shadow="never" class="ems-card vision-result-card">
              <template #header>
                <span class="card-title">检测结果与预览</span>
              </template>

              <div class="preview-row">
                <div class="preview-box">
                  <div class="preview-label">待识别图片</div>
                  <div class="preview-inner">
                    <el-image
                      v-if="previewUrl"
                      :src="previewUrl"
                      fit="contain"
                      class="preview-img"
                    />
                    <el-empty v-else description="左侧上传图片后在此预览" :image-size="72" />
                  </div>
                </div>
                <div class="preview-hint">
                  <p>识别完成后，下方表格汇总检测框；完整 JSON 便于与后端字段对齐。</p>
                  <el-alert
                    v-if="visionFromDemoUpload && uploadResult"
                    type="warning"
                    show-icon
                    :closable="false"
                  >
                    当前为演示检测框，后端就绪后将显示真实推理输出。
                  </el-alert>
                </div>
              </div>

              <div v-if="uploadResult" class="result-block">
                <div class="result-label">检测框列表</div>
                <el-table
                  v-if="detectionRows.length"
                  :data="detectionRows"
                  stripe
                  border
                  size="small"
                  class="det-table"
                  max-height="280"
                >
                  <el-table-column prop="label" label="类别" min-width="100" />
                  <el-table-column label="置信度" width="110" align="right">
                    <template #default="{ row }">
                      {{
                        row.confidence != null && Number.isFinite(row.confidence)
                          ? row.confidence.toFixed(3)
                          : '—'
                      }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="bbox" label="bbox (x1,y1,x2,y2)" min-width="200" show-overflow-tooltip />
                </el-table>
                <el-empty v-else description="无检测框或结构待后端约定" :image-size="64" />

                <el-collapse class="vision-json-collapse">
                  <el-collapse-item title="完整响应 JSON" name="vjson">
                    <pre class="json-preview json-preview--vision">{{ JSON.stringify(uploadResult, null, 2) }}</pre>
                  </el-collapse-item>
                </el-collapse>
              </div>
              <el-empty v-else description="上传并识别后，在此查看表格与 JSON" :image-size="80" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.tv-alert {
  margin-bottom: 14px;
}

.twin-vision-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.card-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.floor-sub {
  font-weight: 400;
  color: var(--ems-text-secondary, rgba(0, 0, 0, 0.45));
  font-size: 13px;
}

.twin-scene-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 16px;
  align-items: start;
}

@media (max-width: 992px) {
  .twin-scene-layout {
    grid-template-columns: 1fr;
  }
}

.twin-side-card {
  position: sticky;
  top: 12px;
}

.building-line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.building-name {
  font-weight: 600;
  font-size: 15px;
}

.floor-menu {
  border-right: none;
}

.floor-menu :deep(.el-menu-item) {
  display: flex;
  align-items: center;
  gap: 6px;
}

.room-count {
  margin-left: auto;
}

.twin-main {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.room-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.room-tile {
  text-align: left;
  padding: 12px 14px;
  border: 1px solid var(--ems-border, #e8e8e8);
  border-radius: var(--ems-card-radius, 6px);
  background: #fff;
  cursor: pointer;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}

.room-tile:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.12);
}

.room-tile--active {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-7);
}

.room-tile__name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
}

.room-tile__id {
  font-size: 12px;
  color: var(--ems-text-secondary);
  margin-bottom: 8px;
  font-family: ui-monospace, monospace;
}

.room-tile__tag {
  margin: 0;
}

.twin-json-collapse {
  border: none;
  --el-collapse-header-height: 44px;
}

.twin-json-collapse :deep(.el-collapse-item__header) {
  font-size: 13px;
  color: var(--ems-text-secondary);
}

.vision-row {
  align-items: stretch;
}

.vision-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hint {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 12px;
  line-height: 1.5;
}

.hint code {
  font-size: 12px;
  padding: 1px 6px;
  background: #f0f2f5;
  border-radius: 4px;
}

.vision-form-inline {
  flex-wrap: wrap;
}

.mini-alert {
  margin-bottom: 10px;
}

.vision-upload :deep(.el-upload-dragger) {
  padding: 20px 16px;
}

.upload-ico {
  font-size: 36px;
  color: var(--el-color-primary);
  margin-bottom: 6px;
}

.upload-text {
  font-size: 14px;
  color: var(--ems-text);
}

.upload-sub {
  font-size: 12px;
  color: var(--ems-text-secondary);
  margin-top: 4px;
}

.vision-result-card {
  min-height: 420px;
}

.preview-row {
  display: grid;
  grid-template-columns: minmax(200px, 1fr) minmax(180px, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .preview-row {
    grid-template-columns: 1fr;
  }
}

.preview-box {
  border: 1px solid var(--ems-border);
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;
}

.preview-label {
  font-size: 12px;
  padding: 6px 10px;
  background: #f0f2f5;
  color: var(--ems-text-secondary);
}

.preview-inner {
  min-height: 200px;
  max-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
}

.preview-img {
  width: 100%;
  max-height: 300px;
}

.preview-hint {
  font-size: 13px;
  color: var(--ems-text-secondary);
  line-height: 1.6;
}

.preview-hint p {
  margin: 0 0 8px;
}

.result-block {
  border-top: 1px solid var(--ems-border);
  padding-top: 14px;
}

.result-label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}

.det-table {
  width: 100%;
}

.vision-json-collapse {
  margin-top: 12px;
  border: none;
}

.json-preview {
  margin: 0;
  overflow: auto;
  font-size: 12px;
  padding: 12px;
  border-radius: 8px;
}

.json-preview--twin {
  max-height: min(50vh, 400px);
  background: #001529;
  color: #e6f4ff;
}

.json-preview--vision {
  max-height: 280px;
  background: #0f172a;
  color: #e2e8f0;
}
</style>
