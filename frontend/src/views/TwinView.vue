<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Picture, Document, CircleCheck } from '@element-plus/icons-vue'
import * as api from '@/api'
import { ElMessage } from 'element-plus'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
const activeTab = ref('vision')

/** 视觉 */
const uploadResult = ref(null)
const loadingUpload = ref(false)

const mode = ref('yolo_world')
const prompt = ref('')
const conf = ref(undefined)
const fileList = ref([])
const panelCollapsed = ref(false)
const showGrid = ref(true)

const previewUrl = ref('')
const modelHost = ref(null)
const modelCanvas = ref(null)
const modelReady = ref(false)
const uploadRef = ref(null)
const selectedFile = ref(null)

function _setPreviewFromFile(raw) {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
  if (raw instanceof File) {
    previewUrl.value = URL.createObjectURL(raw)
  }
}

function onUploadChange(uploadFile, uploadFiles) {
  // 仅保留最后一张，避免旧文件残留导致“识别还是上一张”
  const latest = uploadFiles?.length ? uploadFiles[uploadFiles.length - 1] : null
  fileList.value = latest ? [latest] : []
  selectedFile.value = latest?.raw instanceof File ? latest.raw : null
  _setPreviewFromFile(selectedFile.value)
  // 新选文件时清空旧结果，避免右侧误显示旧建模
  uploadResult.value = null
  _disposeModel()
}

function onUploadExceed(files) {
  // limit=1 时默认不替换；这里改成“新图覆盖旧图”
  const f = files?.[0]
  if (!(f instanceof File)) return
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
    uploadRef.value.handleStart(f)
  }
  selectedFile.value = f
  _setPreviewFromFile(f)
  uploadResult.value = null
  _disposeModel()
}

onUnmounted(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  _disposeModel()
})

const modelBoxes = computed(() => {
  const r = uploadResult.value
  const boxes = r?.yolo?.boxes ?? r?.boxes
  if (!Array.isArray(boxes)) return []
  return boxes
    .map((b) => ({
      label: b?.label ?? 'object',
      conf: b?.conf ?? b?.confidence ?? null,
      bbox: Array.isArray(b?.bbox_xyxy) ? b.bbox_xyxy : (Array.isArray(b?.bbox) ? b.bbox : null),
    }))
    .filter((x) => Array.isArray(x.bbox) && x.bbox.length >= 4)
})

const previewFileName = computed(() => {
  const raw = selectedFile.value ?? fileList.value?.[0]?.raw
  if (raw instanceof File) return raw.name
  return ''
})

const previewImageMeta = computed(() => {
  const r = uploadResult.value
  const w = r?.yolo?.image_size?.w
  const h = r?.yolo?.image_size?.h
  if (w != null && h != null) return { w: Number(w), h: Number(h) }
  return null
})

watch(
  [modelBoxes, activeTab],
  async ([boxes, tab]) => {
    if (tab !== 'vision') return
    if (!boxes.length) {
      _disposeModel()
      return
    }
    await nextTick()
    _buildModelFromDetections()
  },
  { deep: true },
)

let modelRenderer = null
let modelScene = null
let modelCamera = null
let modelControls = null
let modelFrame = 0
let modelMeshes = []
let modelDragMeshes = []
let modelSurfaceMeshes = []
let surfaceBaseColors = new Map()
let modelGrid = null
let modelRaycaster = null
let modelMouse = null
const dragState = {
  active: false,
  mesh: null,
}

function _disposeModel() {
  if (modelFrame) {
    cancelAnimationFrame(modelFrame)
    modelFrame = 0
  }
  if (modelRenderer) {
    _unbindModelDrag()
    modelRenderer.dispose()
    const el = modelRenderer.domElement
    if (el && el.parentNode) el.parentNode.removeChild(el)
  }
  for (const m of modelMeshes) {
    if (m.geometry) m.geometry.dispose()
    if (Array.isArray(m.material)) m.material.forEach((mat) => mat.dispose && mat.dispose())
    else if (m.material) m.material.dispose && m.material.dispose()
  }
  modelMeshes = []
  modelRenderer = null
  modelScene = null
  modelCamera = null
  modelControls = null
  modelDragMeshes = []
  modelSurfaceMeshes = []
  surfaceBaseColors = new Map()
  modelGrid = null
  modelRaycaster = null
  modelMouse = null
  dragState.active = false
  dragState.mesh = null
  modelReady.value = false
}

function _labelColor(label) {
  const s = String(label || '').toLowerCase()
  if (s.includes('person')) return 0x60a5fa
  if (s.includes('chair') || s.includes('sofa')) return 0xf59e0b
  if (s.includes('desk') || s.includes('table')) return 0x22c55e
  if (s.includes('light') || s.includes('lamp')) return 0xeab308
  return 0xa78bfa
}

function _makeTextSprite(text) {
  const c = document.createElement('canvas')
  c.width = 256
  c.height = 64
  const ctx = c.getContext('2d')
  if (!ctx) return null
  ctx.fillStyle = 'rgba(15,23,42,0.84)'
  ctx.fillRect(0, 0, c.width, c.height)
  ctx.fillStyle = '#ffffff'
  ctx.font = 'bold 24px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(String(text || 'object').slice(0, 18), c.width / 2, c.height / 2)
  const tex = new THREE.CanvasTexture(c)
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true })
  const sp = new THREE.Sprite(mat)
  sp.scale.set(1.8, 0.45, 1)
  return sp
}

function _getMouseNdc(ev) {
  const rect = modelRenderer.domElement.getBoundingClientRect()
  modelMouse.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1
  modelMouse.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1
}

function _bindModelDrag() {
  if (!modelRenderer || !modelCamera) return
  const dom = modelRenderer.domElement
  modelRaycaster = new THREE.Raycaster()
  modelMouse = new THREE.Vector2()

  const onDown = (ev) => {
    _getMouseNdc(ev)
    modelRaycaster.setFromCamera(modelMouse, modelCamera)
    const hits = modelRaycaster.intersectObjects(modelDragMeshes, false)
    if (!hits.length) return
    dragState.active = true
    dragState.mesh = hits[0].object
    if (modelControls) modelControls.enabled = false
  }
  const onMove = (ev) => {
    if (!dragState.active || !dragState.mesh) return
    _getMouseNdc(ev)
    modelRaycaster.setFromCamera(modelMouse, modelCamera)
    const hits = modelRaycaster.intersectObjects(modelSurfaceMeshes, false)
    if (!hits.length) return
    const hit = hits[0]
    for (const s of modelSurfaceMeshes) {
      if (s.material && s.material.color) {
        const base = surfaceBaseColors.get(s.uuid)
        if (base) s.material.color.set(base)
      }
    }
    if (hit.object?.material?.color) hit.object.material.color.set(0x93c5fd)

    const mesh = dragState.mesh
    const halfY = Math.max(0.12, mesh.scale?.y ? mesh.scale.y / 2 : (mesh.geometry?.parameters?.height || 0.4) / 2)
    const userSurface = hit.object?.userData?.surface

    // floor: normal placement
    if (userSurface === 'floor') {
      mesh.rotation.set(0, 0, 0)
      mesh.position.x = THREE.MathUtils.clamp(hit.point.x, -4.8, 4.8)
      mesh.position.z = THREE.MathUtils.clamp(hit.point.z, -3.3, 3.3)
      mesh.position.y = halfY
      return
    }

    // back wall z=-3.5
    if (userSurface === 'back') {
      mesh.rotation.set(0, 0, 0)
      mesh.position.x = THREE.MathUtils.clamp(hit.point.x, -4.8, 4.8)
      mesh.position.y = THREE.MathUtils.clamp(hit.point.y, halfY, 2.6 - halfY)
      mesh.position.z = -3.5 + (mesh.geometry?.parameters?.depth || 0.3) / 2
      return
    }

    // left / right walls
    if (userSurface === 'left') {
      mesh.rotation.set(0, Math.PI / 2, 0)
      mesh.position.x = -5 + (mesh.geometry?.parameters?.depth || 0.3) / 2
      mesh.position.y = THREE.MathUtils.clamp(hit.point.y, halfY, 2.6 - halfY)
      mesh.position.z = THREE.MathUtils.clamp(hit.point.z, -3.3, 3.3)
      return
    }
    if (userSurface === 'right') {
      mesh.rotation.set(0, Math.PI / 2, 0)
      mesh.position.x = 5 - (mesh.geometry?.parameters?.depth || 0.3) / 2
      mesh.position.y = THREE.MathUtils.clamp(hit.point.y, halfY, 2.6 - halfY)
      mesh.position.z = THREE.MathUtils.clamp(hit.point.z, -3.3, 3.3)
    }
  }
  const onUp = () => {
    dragState.active = false
    dragState.mesh = null
    for (const s of modelSurfaceMeshes) {
      if (s.material && s.material.color) {
        const base = surfaceBaseColors.get(s.uuid)
        if (base) s.material.color.set(base)
      }
    }
    if (modelControls) modelControls.enabled = true
  }

  dom.addEventListener('pointerdown', onDown)
  dom.addEventListener('pointermove', onMove)
  dom.addEventListener('pointerup', onUp)
  dom.addEventListener('pointerleave', onUp)
  dom.__modelDragHandlers = { onDown, onMove, onUp }
}

function _unbindModelDrag() {
  if (!modelRenderer) return
  const dom = modelRenderer.domElement
  const h = dom.__modelDragHandlers
  if (!h) return
  dom.removeEventListener('pointerdown', h.onDown)
  dom.removeEventListener('pointermove', h.onMove)
  dom.removeEventListener('pointerup', h.onUp)
  dom.removeEventListener('pointerleave', h.onUp)
  delete dom.__modelDragHandlers
}

function _buildModelFromDetections() {
  const host = modelHost.value
  const mount = modelCanvas.value
  if (!host || !mount) return
  _disposeModel()

  const w = Math.max(320, host.clientWidth || 320)
  const h = Math.max(220, host.clientHeight || 220)
  modelRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  modelRenderer.setSize(w, h)
  mount.innerHTML = ''
  mount.appendChild(modelRenderer.domElement)

  modelScene = new THREE.Scene()
  modelScene.background = new THREE.Color(0x0b1220)
  modelCamera = new THREE.PerspectiveCamera(50, w / h, 0.1, 200)
  modelCamera.position.set(0, 7.8, 12.5)
  modelCamera.lookAt(0, 1.2, 0)
  modelControls = new OrbitControls(modelCamera, modelRenderer.domElement)
  modelControls.enableDamping = true
  modelControls.dampingFactor = 0.06
  modelControls.target.set(0, 1.1, 0)
  modelControls.update()

  modelScene.add(new THREE.AmbientLight(0xffffff, 0.85))
  const dl = new THREE.DirectionalLight(0xffffff, 0.9)
  dl.position.set(6, 10, 4)
  modelScene.add(dl)
  modelGrid = new THREE.GridHelper(12, 24, 0x334155, 0x1e293b)
  modelGrid.position.y = 0.01
  modelGrid.visible = !!showGrid.value
  modelScene.add(modelGrid)
  modelMeshes.push(modelGrid)

  const roomW = 10
  const roomD = 7
  const floorMat = new THREE.MeshStandardMaterial({ color: 0x1f2937, roughness: 0.92 })
  const floor = new THREE.Mesh(
    new THREE.BoxGeometry(roomW, 0.2, roomD),
    floorMat,
  )
  floor.position.set(0, -0.1, 0)
  floor.userData.surface = 'floor'
  modelScene.add(floor)
  modelMeshes.push(floor)
  modelSurfaceMeshes.push(floor)

  const wallMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.98 })
  const wallBack = new THREE.Mesh(new THREE.BoxGeometry(roomW, 2.8, 0.14), wallMat)
  wallBack.position.set(0, 1.3, -roomD / 2)
  wallBack.userData.surface = 'back'
  modelScene.add(wallBack)
  modelMeshes.push(wallBack)
  modelSurfaceMeshes.push(wallBack)
  const wallLeft = new THREE.Mesh(new THREE.BoxGeometry(0.14, 2.8, roomD), wallMat)
  wallLeft.position.set(-roomW / 2, 1.3, 0)
  wallLeft.userData.surface = 'left'
  modelScene.add(wallLeft)
  modelMeshes.push(wallLeft)
  modelSurfaceMeshes.push(wallLeft)
  const wallRight = new THREE.Mesh(new THREE.BoxGeometry(0.14, 2.8, roomD), wallMat)
  wallRight.position.set(roomW / 2, 1.3, 0)
  wallRight.userData.surface = 'right'
  modelScene.add(wallRight)
  modelMeshes.push(wallRight)
  modelSurfaceMeshes.push(wallRight)
  for (const s of modelSurfaceMeshes) {
    if (s.material?.color) surfaceBaseColors.set(s.uuid, `#${s.material.color.getHexString()}`)
  }

  const imgW = Number(uploadResult.value?.yolo?.image_size?.w) || 1000
  const imgH = Number(uploadResult.value?.yolo?.image_size?.h) || 1000

  modelBoxes.value.slice(0, 60).forEach((it) => {
    const [x1, y1, x2, y2] = it.bbox.map((x) => Number(x) || 0)
    const bw = Math.max(8, Math.abs(x2 - x1))
    const bh = Math.max(8, Math.abs(y2 - y1))
    const cx = (x1 + x2) / 2
    const cy = (y1 + y2) / 2

    // 体量缩放：较之前整体缩小，避免遮挡空间
    const sx = Math.max(0.16, (bw / imgW) * roomW * 0.56)
    const sz = Math.max(0.16, (bh / imgH) * roomD * 0.56)
    const sy = Math.min(1.3, Math.max(0.16, 0.12 + (it.conf == null ? 0.22 : Number(it.conf) * 0.68)))

    const px = (cx / imgW - 0.5) * roomW
    const pz = (cy / imgH - 0.5) * roomD

    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(sx, sy, sz),
      new THREE.MeshStandardMaterial({
        color: _labelColor(it.label),
        transparent: true,
        opacity: 0.9,
        roughness: 0.65,
      }),
    )
    mesh.position.set(px, sy / 2, pz)
    modelScene.add(mesh)
    modelMeshes.push(mesh)
    modelDragMeshes.push(mesh)
    const label = _makeTextSprite(it.label)
    if (label) {
      label.position.set(0, sy / 2 + 0.35, 0)
      mesh.add(label)
      modelMeshes.push(label)
    }
  })

  _bindModelDrag()

  const render = () => {
    if (!modelRenderer || !modelScene || !modelCamera) return
    if (modelControls) modelControls.update()
    modelRenderer.render(modelScene, modelCamera)
    modelFrame = requestAnimationFrame(render)
  }
  modelReady.value = true
  render()
}

watch(showGrid, (v) => {
  if (modelGrid) modelGrid.visible = !!v
})

function resetView() {
  if (!modelCamera || !modelControls) return
  modelCamera.position.set(0, 7.8, 12.5)
  modelControls.target.set(0, 1.1, 0)
  modelControls.update()
}

async function runUpload() {
  const raw = selectedFile.value ?? fileList.value[0]?.raw
  if (!raw || !(raw instanceof File)) {
    ElMessage.warning('请先选择图片文件')
    return
  }
  loadingUpload.value = true
  uploadResult.value = null
  try {
    const p = { mode: mode.value }
    if (prompt.value.trim()) p.prompt = prompt.value.trim()
    if (conf.value != null && !Number.isNaN(Number(conf.value))) p.conf = Number(conf.value)
    uploadResult.value = await api.postV2VisionUpload(raw, p)
  } catch (e) {
    ElMessage.error(e.message ?? 'upload 调用失败')
  } finally {
    loadingUpload.value = false
  }
}

onMounted(() => {
  activeTab.value = 'vision'
})
</script>

<template>
  <div class="myems-page twin-vision-view">
    <div class="page-hero">
      <h1 class="myems-page-title">孪生与视觉</h1>
      <p class="myems-page-desc">
        上传空间图片后调用 <code>/api/v2/vision/upload</code>，自动生成可交互 3D 建模结果。
      </p>
      <div class="hero-tips">
        <el-tag effect="light" type="primary">拖拽到墙面 / 地面</el-tag>
        <el-tag effect="light">滚轮缩放</el-tag>
        <el-tag effect="light">鼠标拖动旋转视角</el-tag>
      </div>
    </div>

    <div class="vision-layout">
      <div class="top-row">
        <el-card v-show="!panelCollapsed" shadow="hover" class="ems-card control-panel">
          <template #header>
            <span class="card-title">识别参数</span>
          </template>
          <el-form label-position="top" class="control-form" size="default">
            <div class="control-section">
              <div class="section-head">
                <span class="section-title">推理设置</span>
                <span class="section-hint">模式、提示词与置信度阈值</span>
              </div>
              <el-form-item label="模式" class="form-item-tight">
                <el-segmented
                  v-model="mode"
                  class="mode-segmented"
                  block
                  :options="[
                    { label: 'YOLO-World', value: 'yolo_world' },
                    { label: 'YOLO-Seg', value: 'yolo_seg' },
                  ]"
                />
              </el-form-item>
              <el-form-item label="prompt（可选）">
                <el-input
                  v-model="prompt"
                  placeholder="英文类别，如 person, chair, desk"
                  clearable
                  maxlength="256"
                  show-word-limit
                />
              </el-form-item>
              <el-form-item label="置信度 conf" class="form-item-slider">
                <el-slider
                  v-model="conf"
                  :min="0.02"
                  :max="0.95"
                  :step="0.01"
                  show-input
                  :show-input-controls="false"
                />
                <p class="field-tip">不填则使用后端默认；拖动或输入数值</p>
              </el-form-item>
            </div>

            <el-divider class="control-divider" />

            <div class="control-section">
              <div class="section-head">
                <span class="section-title">图片</span>
                <span class="section-hint">单张，识别前可预览右侧</span>
              </div>
              <el-form-item class="form-item-upload">
                <el-upload
                  ref="uploadRef"
                  v-model:file-list="fileList"
                  drag
                  class="vision-upload"
                  :on-change="onUploadChange"
                  :on-exceed="onUploadExceed"
                  :auto-upload="false"
                  :limit="1"
                  accept="image/*"
                >
                  <el-icon class="upload-ico"><Picture /></el-icon>
                  <div class="upload-text">拖拽到此处，或点击选择</div>
                  <div class="upload-sub">常见图片格式；大小以后端限制为准</div>
                </el-upload>
              </el-form-item>
            </div>

            <div class="control-actions">
              <el-button
                type="primary"
                size="large"
                class="submit-primary"
                :loading="loadingUpload"
                :disabled="!fileList.length"
                @click="runUpload"
              >
                上传并建模
              </el-button>
              <p v-if="!fileList.length" class="action-tip">请先选择一张图片</p>
            </div>
          </el-form>
        </el-card>

        <el-card shadow="hover" class="ems-card preview-panel">
          <template #header>
            <div class="model-header preview-card-header">
              <span class="card-title">识别原图</span>
              <div class="header-actions">
                <el-tag v-if="uploadResult" type="success" effect="light" size="small">已识别</el-tag>
                <el-tag v-else-if="previewUrl" type="warning" effect="light" size="small">待识别</el-tag>
                <el-tag v-else type="info" effect="plain" size="small">未选择</el-tag>
                <el-button text type="primary" size="small" @click="panelCollapsed = !panelCollapsed">
                  {{ panelCollapsed ? '展开参数' : '收起参数' }}
                </el-button>
              </div>
            </div>
          </template>
          <div class="preview-body">
            <div class="preview-stage-block">
              <div class="preview-stage-toolbar">
                <span class="preview-stage-label">
                  <el-icon class="preview-stage-ico"><Picture /></el-icon>
                  画面预览
                </span>
                <span v-if="previewFileName" class="preview-file-name" :title="previewFileName">
                  <el-icon class="file-ico"><Document /></el-icon>
                  {{ previewFileName }}
                </span>
              </div>
              <div class="preview-stage">
                <el-image
                  v-if="previewUrl"
                  :src="previewUrl"
                  fit="contain"
                  class="preview-img"
                />
                <div v-else class="preview-empty-wrap">
                  <el-empty description="暂无预览" :image-size="80">
                    <template #description>
                      <span class="preview-empty-text">在左侧选择或拖入图片后，此处显示原图</span>
                    </template>
                  </el-empty>
                </div>
              </div>
            </div>

            <div v-if="previewImageMeta || (uploadResult && modelBoxes.length)" class="preview-meta-bar">
              <template v-if="previewImageMeta">
                <span class="meta-pill">原图尺寸 {{ previewImageMeta.w }} × {{ previewImageMeta.h }}</span>
              </template>
              <template v-if="uploadResult && modelBoxes.length">
                <span class="meta-pill meta-pill--accent">检出 {{ modelBoxes.length }} 个目标</span>
              </template>
            </div>

            <div class="preview-tips">
              <div class="section-head preview-tips-head">
                <span class="section-title">说明</span>
                <span class="section-hint">与下方 3D 预览联动</span>
              </div>
              <ul class="preview-tip-list">
                <li>
                  <el-icon class="tip-ico"><CircleCheck /></el-icon>
                  <span>识别完成后，下方自动生成可交互 3D 场景。</span>
                </li>
                <li>
                  <el-icon class="tip-ico"><CircleCheck /></el-icon>
                  <span>物体模块可拖拽至地面与三面墙；标签随模块移动。</span>
                </li>
                <li>
                  <el-icon class="tip-ico"><CircleCheck /></el-icon>
                  <span>滚轮缩放视角，鼠标拖动旋转观察空间关系。</span>
                </li>
              </ul>
            </div>
          </div>
        </el-card>
      </div>

      <el-card shadow="hover" class="ems-card model-panel full-row">
        <template #header>
          <div class="model-header">
            <span class="card-title">3D 建模预览</span>
            <div class="canvas-toolbar">
              <el-switch v-model="showGrid" inline-prompt active-text="网格" inactive-text="网格" />
              <el-button size="small" @click="resetView">重置视角</el-button>
            </div>
          </div>
        </template>
        <div ref="modelHost" class="model3d-host">
          <div ref="modelCanvas" class="model3d-canvas"></div>
          <el-empty
            v-if="!modelReady"
            class="model3d-empty"
            description="上传并识别后自动生成 3D 模型"
            :image-size="64"
          />
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.twin-vision-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-hero {
  background: linear-gradient(135deg, #f8fbff 0%, #eef6ff 100%);
  border: 1px solid #dbeafe;
  border-radius: 14px;
  padding: 16px 18px;
}

.hero-tips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.vision-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.top-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
}

@media (max-width: 1100px) {
  .top-row {
    grid-template-columns: 1fr;
  }
}

.card-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}

.control-panel,
.preview-panel,
.model-panel {
  border-radius: 14px;
}

.preview-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.preview-panel :deep(.el-card__body) {
  padding: 16px 18px 18px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.preview-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
  min-height: 0;
}

.preview-card-header {
  flex-wrap: wrap;
  row-gap: 6px;
}

.preview-stage-block {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid var(--ems-border);
  border-radius: 10px;
  overflow: hidden;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
}

.preview-stage-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.85);
  border-bottom: 1px solid var(--ems-border);
}

.preview-stage-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.65);
}

.preview-stage-ico {
  font-size: 15px;
  color: var(--el-color-primary);
}

.preview-file-name {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: min(100%, 220px);
  font-size: 12px;
  color: var(--ems-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-ico {
  flex-shrink: 0;
  font-size: 14px;
  opacity: 0.85;
}

.preview-stage {
  position: relative;
  min-height: 220px;
  height: clamp(220px, 32vh, 380px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  background: radial-gradient(120% 80% at 50% 40%, #e2e8f0 0%, #f8fafc 55%, #fff 100%);
}

.preview-img {
  width: 100%;
  height: 100%;
  max-height: 100%;
}

.preview-img :deep(.el-image__inner) {
  max-height: min(340px, 100%);
  object-fit: contain;
}

.preview-img :deep(.el-image__wrapper) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-empty-wrap {
  width: 100%;
  height: 100%;
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-empty-text {
  font-size: 13px;
  color: var(--ems-text-secondary);
  line-height: 1.5;
}

.preview-meta-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.meta-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  font-size: 12px;
  line-height: 1.4;
  color: rgba(0, 0, 0, 0.65);
  background: #f0f2f5;
  border-radius: 999px;
  border: 1px solid var(--ems-border);
}

.meta-pill--accent {
  color: var(--el-color-primary);
  background: rgba(24, 144, 255, 0.08);
  border-color: rgba(24, 144, 255, 0.25);
}

.preview-tips {
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--ems-border);
  background: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.preview-tips-head {
  margin-bottom: 10px;
}

.preview-tip-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.preview-tip-list li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.55;
  color: rgba(0, 0, 0, 0.72);
}

.tip-ico {
  flex-shrink: 0;
  margin-top: 2px;
  font-size: 14px;
  color: var(--el-color-success);
}

.full-row {
  width: 100%;
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

.control-panel :deep(.el-card__body) {
  padding: 16px 18px 18px;
}

.control-form {
  --ctrl-label-color: rgba(0, 0, 0, 0.55);
}

.control-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.control-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--ctrl-label-color);
  line-height: 1.35;
  margin-bottom: 6px !important;
}

.control-section {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.section-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.78);
  letter-spacing: 0.02em;
}

.section-hint {
  font-size: 12px;
  color: var(--ems-text-secondary);
  line-height: 1.45;
}

.form-item-tight :deep(.el-form-item__label) {
  margin-bottom: 8px !important;
}

.mode-segmented {
  width: 100%;
}

.form-item-slider :deep(.el-slider) {
  width: 100%;
  padding-right: 0;
}

.form-item-slider :deep(.el-slider__runway.show-input) {
  margin-right: 12px;
}

.field-tip {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--ems-text-secondary);
  line-height: 1.4;
}

.control-divider {
  margin: 4px 0 16px;
  border-color: var(--ems-border);
}

.form-item-upload {
  margin-bottom: 0 !important;
}

.form-item-upload :deep(.el-form-item__content) {
  line-height: normal;
}

.control-actions {
  margin-top: 16px;
  padding-top: 4px;
}

.submit-primary {
  width: 100%;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.action-tip {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-color-primary);
  text-align: center;
  line-height: 1.4;
}

.model-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.vision-upload {
  width: 100%;
}

.vision-upload :deep(.el-upload) {
  width: 100%;
}

.vision-upload :deep(.el-upload-dragger) {
  width: 100%;
  padding: 18px 14px;
  border-radius: 10px;
  border-style: dashed;
  border-color: rgba(24, 144, 255, 0.35);
  background: linear-gradient(180deg, rgba(24, 144, 255, 0.04), rgba(255, 255, 255, 0.6));
  transition: border-color 0.2s, background 0.2s;
}

.vision-upload :deep(.el-upload-dragger:hover) {
  border-color: var(--el-color-primary);
  background: rgba(24, 144, 255, 0.06);
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

.canvas-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.model3d-host {
  position: relative;
  min-height: 300px;
  height: min(62vh, 560px);
  border: 1px solid var(--ems-border);
  border-radius: 12px;
  background: radial-gradient(100% 100% at 50% 0%, #0f172a 0%, #020617 100%);
  overflow: hidden;
}

.model3d-canvas {
  position: absolute;
  inset: 0;
}

.model3d-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.result-label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}

</style>
