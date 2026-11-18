<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import StatusPanel from '../components/StatusPanel.vue'
import {
  getDetection,
  getAnalyticsSummary,
  getAnnotatedImageStatus,
  getAnnotatedImageUrl,
  getDatabaseHealth,
  getHealth,
  getImageContentUrl,
  getModels,
  queryDetectionHistory,
  uploadModel,
  uploadDetection,
} from '../api.js'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const fileInput = ref(null)
const selectedFile = ref(null)
const previewUrl = ref('')
const previewWidth = ref(0)
const previewHeight = ref(0)
const activeTask = ref(null)
const historyItems = ref([])
const selectedTaskId = ref(null)
const hasAnnotatedImage = ref(false)
const modelItems = ref([])
const modelUploadEnabled = ref(false)
const selectedModelId = ref('')
const isUploadingModel = ref(false)
const modelError = ref('')
const modelNotice = ref('')
const analytics = ref(null)
const historyTotal = ref(0)
const historyPage = ref(0)
const historySearch = ref('')
const historyStatus = ref('')
const historyDateFrom = ref('')
const historyDateTo = ref('')
const backendStatus = ref('checking')
const databaseStatus = ref('checking')
const isUploading = ref(false)
const isDragging = ref(false)
const isLoadingHistory = ref(false)
const isLoadingTask = ref(false)
const isBatchRunning = ref(false)
const isBatchPaused = ref(false)
const isBatchCancelled = ref(false)
const batchInput = ref(null)
const datasetInput = ref(null)
const modelInput = ref(null)
const pageError = ref('')
const historyError = ref('')
const batchError = ref('')
const activeView = ref('dashboard')
const showOverlay = ref(true)
const showAnnotatedImage = ref(false)
const selectedModelFile = ref(null)
const selectedDatasetFile = ref(null)
const isDeveloper = import.meta.env.VITE_DEVELOPER_MODE === 'true'
const savedPlatformName = localStorage.getItem('skyvision.platformName')
const platformName = ref(
  !savedPlatformName || savedPlatformName === 'SkyVision AI'
    ? 'SKyGuard CC'
    : savedPlatformName,
)
const editablePlatformName = ref(platformName.value)
const confidenceThreshold = ref(0.25)
const nmsThreshold = ref(0.45)
const clockText = ref('')
let clockTimer

const navItems = [
  { id: 'dashboard', label: '系统总览', icon: '▦' },
  { id: 'detection', label: '图像检测', icon: '⌁' },
  { id: 'batch', label: '批量检测', icon: '▤' },
  { id: 'datasets', label: '数据集管理', icon: '◫' },
  { id: 'models', label: '模型管理', icon: '◉' },
  { id: 'history', label: '检测记录', icon: '☷' },
  { id: 'analytics', label: '数据统计', icon: '⌁' },
  { id: 'settings', label: '系统设置', icon: '⚙' },
]

const batchItems = ref([])

const results = computed(() => activeTask.value?.results ?? [])
const imageWidth = computed(
  () => activeTask.value?.image?.image_width || previewWidth.value,
)
const imageHeight = computed(
  () => activeTask.value?.image?.image_height || previewHeight.value,
)
const imageLabel = computed(
  () =>
    activeTask.value?.image?.original_filename ||
    selectedFile.value?.name ||
    '等待载入航拍图像',
)
const displayImageUrl = computed(() =>
  activeTask.value && showAnnotatedImage.value
    ? getAnnotatedImageUrl(activeTask.value.id)
    : previewUrl.value,
)
const averageConfidence = computed(() => {
  if (!results.value.length) return 0
  const total = results.value.reduce((sum, item) => sum + item.confidence, 0)
  return Math.round((total / results.value.length) * 100)
})
const highConfidenceCount = computed(
  () => results.value.filter((item) => item.confidence >= 0.8).length,
)
const succeededTaskCount = computed(
  () => historyItems.value.filter((task) => task.status === 'succeeded').length,
)
const categoryItems = computed(() => {
  const colors = ['blue', 'cyan', 'green', 'orange']
  const categories = analytics.value?.categories ?? []
  const maxCount = Math.max(1, ...categories.map((item) => item.count))
  return categories.slice(0, 5).map((item, index) => ({
    label: item.class_name,
    count: item.count,
    value: Math.max(5, Math.round((item.count / maxCount) * 100)),
    color: colors[index % colors.length],
  }))
})
const categoryVisibleTotal = computed(() =>
  categoryItems.value.reduce((sum, item) => sum + item.count, 0),
)
const categoryDonutStyle = computed(() => {
  const colors = {
    blue: '#168bff',
    cyan: '#00d4ff',
    green: '#55e6a5',
    orange: '#ffad5b',
  }
  if (!categoryVisibleTotal.value) return { background: '#122b42' }
  let offset = 0
  const stops = categoryItems.value.map((item) => {
    const start = offset
    offset += (item.count / categoryVisibleTotal.value) * 100
    return `${colors[item.color]} ${start}% ${offset}%`
  })
  return { background: `conic-gradient(${stops.join(', ')})` }
})
const recentTasks = computed(() => analytics.value?.daily_tasks ?? [])
const batchCompletedCount = computed(
  () => batchItems.value.filter((item) => item.status === '已完成').length,
)
const batchProgress = computed(() => {
  if (!batchItems.value.length) return 0
  return Math.round(
    batchItems.value.reduce((sum, item) => sum + item.progress, 0) /
      batchItems.value.length,
  )
})
const viewTitle = computed(
  () => navItems.find((item) => item.id === activeView.value)?.label ?? '系统总览',
)

function updateClock() {
  clockText.value = new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date())
}

function setPreview(file) {
  if (previewUrl.value.startsWith('blob:')) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(file)
  previewWidth.value = 0
  previewHeight.value = 0
}

function validateFile(file, errorState = pageError) {
  if (!file) return false
  const supportedType =
    ['image/jpeg', 'image/png', 'image/webp'].includes(file.type) ||
    /\.(jpe?g|png|webp)$/i.test(file.name)
  if (!supportedType) {
    errorState.value = '网页预览目前支持 JPG、PNG 或 WEBP 图像。'
    return false
  }
  if (file.size > MAX_FILE_SIZE) {
    errorState.value = '图像不能超过 10 MiB。'
    return false
  }
  return true
}

function acceptFile(file) {
  pageError.value = ''
  if (!validateFile(file)) return
  selectedFile.value = file
  activeTask.value = null
  selectedTaskId.value = null
  setPreview(file)
}

function selectFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  acceptFile(file)
}

function onDrop(event) {
  isDragging.value = false
  acceptFile(event.dataTransfer?.files?.[0])
}

function onPreviewLoad(event) {
  if (!activeTask.value) {
    previewWidth.value = event.target.naturalWidth
    previewHeight.value = event.target.naturalHeight
  }
}

function onPreviewError() {
  pageError.value = '图像预览加载失败。'
}

async function checkBackend() {
  backendStatus.value = 'checking'
  databaseStatus.value = 'checking'
  const [apiResult, databaseResult] = await Promise.allSettled([
    getHealth(),
    getDatabaseHealth(),
  ])
  backendStatus.value = apiResult.status === 'fulfilled' ? 'online' : 'offline'
  databaseStatus.value =
    databaseResult.status === 'fulfilled' ? 'online' : 'offline'
}

async function refreshHistory() {
  await searchHistory()
}

async function refreshAnalytics() {
  try {
    analytics.value = await getAnalyticsSummary()
  } catch {
    analytics.value = null
  }
}

async function refreshModels() {
  modelError.value = ''
  try {
    const response = await getModels()
    modelItems.value = response.items
    modelUploadEnabled.value = response.upload_enabled
    if (!modelItems.value.some((item) => item.id === selectedModelId.value)) {
      selectedModelId.value =
        modelItems.value.find((item) => item.is_default)?.id ??
        modelItems.value[0]?.id ??
        ''
    }
  } catch (error) {
    modelError.value = error.message
  }
}

async function searchHistory(resetPage = true) {
  if (resetPage) historyPage.value = 0
  isLoadingHistory.value = true
  historyError.value = ''
  try {
    const response = await queryDetectionHistory({
      q: historySearch.value.trim(),
      status: historyStatus.value,
      dateFrom: historyDateFrom.value,
      dateTo: historyDateTo.value,
      limit: 20,
      offset: historyPage.value * 20,
    })
    historyItems.value = response.items
    historyTotal.value = response.total
  } catch (error) {
    historyError.value = error.message
  } finally {
    isLoadingHistory.value = false
  }
}

async function runDetection() {
  if (!selectedFile.value || isUploading.value) return
  isUploading.value = true
  pageError.value = ''
  try {
    const task = await uploadDetection(selectedFile.value, {
      confidence: Number(confidenceThreshold.value),
      nmsIou: Number(nmsThreshold.value),
      modelId: selectedModelId.value,
    })
    activeTask.value = task
    hasAnnotatedImage.value = true
    showAnnotatedImage.value = false
    selectedTaskId.value = task.id
    await refreshHistory()
    await refreshAnalytics()
  } catch (error) {
    pageError.value = error.message
  } finally {
    isUploading.value = false
  }
}

function addBatchFiles(event) {
  const files = [...(event.target.files ?? [])]
  event.target.value = ''
  batchError.value = ''
  let rejectedCount = 0
  for (const file of files) {
    if (!validateFile(file, batchError)) {
      rejectedCount += 1
      continue
    }
    if (batchItems.value.some((item) => item.file?.name === file.name && item.file?.size === file.size)) {
      continue
    }
    batchItems.value.push({
      id: `${file.name}-${file.size}-${file.lastModified}`,
      file,
      name: file.name,
      size: formatBytes(file.size),
      status: '排队中',
      progress: 0,
      targets: null,
      error: '',
      task: null,
    })
  }
  if (rejectedCount) {
    batchError.value = `${rejectedCount} 个文件格式或大小不符合要求，未加入队列。`
  }
}

async function runBatch() {
  if (isBatchRunning.value) return
  isBatchRunning.value = true
  isBatchPaused.value = false
  isBatchCancelled.value = false
  for (const item of batchItems.value) {
    if (isBatchCancelled.value) break
    if (!['排队中', '失败', '已取消'].includes(item.status)) continue
    while (isBatchPaused.value && !isBatchCancelled.value) {
      await new Promise((resolve) => window.setTimeout(resolve, 200))
    }
    if (isBatchCancelled.value) break
    item.status = '处理中'
    item.progress = 0
    item.error = ''
    try {
      const task = await uploadDetection(item.file, {
        confidence: Number(confidenceThreshold.value),
        nmsIou: Number(nmsThreshold.value),
        modelId: selectedModelId.value,
      })
      item.task = task
      item.targets = task.results?.length ?? 0
      item.status = '已完成'
      item.progress = 100
    } catch (error) {
      item.error = error.message
      item.status = '失败'
      item.progress = 0
    }
  }
  isBatchRunning.value = false
  await refreshHistory()
  await refreshAnalytics()
}

function toggleBatchPause() {
  isBatchPaused.value = !isBatchPaused.value
}

function cancelBatch() {
  isBatchCancelled.value = true
  isBatchPaused.value = false
  for (const item of batchItems.value) {
    if (item.status === '排队中') item.status = '已取消'
  }
}

function removeBatchItem(itemId) {
  if (isBatchRunning.value) return
  batchItems.value = batchItems.value.filter((item) => item.id !== itemId)
}

function exportBatchResults() {
  const tasks = batchItems.value.filter((item) => item.task).map((item) => item.task)
  downloadText('skyvision-batch-results.json', JSON.stringify(tasks, null, 2))
}

async function openHistoryTask(taskId) {
  if (isLoadingTask.value) return
  isLoadingTask.value = true
  pageError.value = ''
  try {
    const task = await getDetection(taskId)
    if (previewUrl.value.startsWith('blob:')) URL.revokeObjectURL(previewUrl.value)
    selectedFile.value = null
    activeTask.value = task
    hasAnnotatedImage.value = false
    try {
      const imageStatus = await getAnnotatedImageStatus(task.id)
      hasAnnotatedImage.value = imageStatus.available
    } catch {
      hasAnnotatedImage.value = false
    }
    showAnnotatedImage.value = false
    selectedTaskId.value = task.id
    previewUrl.value = getImageContentUrl(task.image_id)
    previewWidth.value = 0
    previewHeight.value = 0
  } catch (error) {
    pageError.value = error.message
  } finally {
    isLoadingTask.value = false
  }
}

function pointsAttribute(points) {
  return points.map(([x, y]) => `${x},${y}`).join(' ')
}

function formatDate(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatBytes(value) {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function statusLabel(status) {
  return {
    pending: '等待中',
    running: '处理中',
    succeeded: '已完成',
    failed: '失败',
  }[status] ?? status
}

function switchView(view) {
  activeView.value = view
  if (view === 'history') searchHistory()
}

function savePlatformName() {
  if (!isDeveloper) return
  const nextName = editablePlatformName.value.trim()
  if (!nextName) {
    editablePlatformName.value = platformName.value
    return
  }
  platformName.value = nextName
  localStorage.setItem('skyvision.platformName', nextName)
}

function selectModelFile(event) {
  selectedModelFile.value = event.target.files?.[0] ?? null
  modelNotice.value = ''
  modelError.value = ''
  event.target.value = ''
}

async function uploadSelectedModel() {
  if (!selectedModelFile.value || isUploadingModel.value) return
  isUploadingModel.value = true
  modelError.value = ''
  modelNotice.value = ''
  try {
    const registered = await uploadModel(selectedModelFile.value)
    selectedModelFile.value = null
    await refreshModels()
    selectedModelId.value = registered.id
    modelNotice.value = `已登记“${registered.name}”权重，可在检测页选择使用。`
  } catch (error) {
    modelError.value = error.message
  } finally {
    isUploadingModel.value = false
  }
}

function selectDatasetFile(event) {
  selectedDatasetFile.value = event.target.files?.[0] ?? null
  event.target.value = ''
}

function downloadText(filename, content, type = 'application/json') {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function downloadResults(format) {
  if (!activeTask.value || !hasAnnotatedImage.value) return
  if (format === 'json') {
    downloadText(
      `skyvision-task-${activeTask.value.id}.json`,
      JSON.stringify(activeTask.value, null, 2),
    )
    return
  }
  const lines = results.value.map((item) => {
    const points = item.points.flat().join(' ')
    return `${item.class_name} ${item.confidence} ${points}`
  })
  downloadText(`skyvision-task-${activeTask.value.id}.txt`, lines.join('\n'), 'text/plain')
}

function downloadAnnotatedImage() {
  if (!activeTask.value) return
  const anchor = document.createElement('a')
  anchor.href = getAnnotatedImageUrl(activeTask.value.id)
  anchor.download = `skyvision-task-${activeTask.value.id}-prediction.jpg`
  anchor.click()
}

onMounted(() => {
  updateClock()
  clockTimer = window.setInterval(updateClock, 1000)
  checkBackend()
  refreshHistory()
  refreshAnalytics()
  refreshModels()
})

onBeforeUnmount(() => {
  window.clearInterval(clockTimer)
  if (previewUrl.value.startsWith('blob:')) URL.revokeObjectURL(previewUrl.value)
})
</script>

<template>
  <div class="platform-shell">
    <header class="topbar">
      <a class="brand" href="/" :aria-label="`${platformName} 首页`">
        <span class="brand-symbol"><span></span></span>
        <span class="brand-copy">
          <strong>{{ platformName }}</strong>
          <small>无人机遥感智能检测平台</small>
        </span>
      </a>

      <div class="topbar-center">
        <span class="breadcrumb">工作台</span>
        <span class="breadcrumb-divider">/</span>
        <strong>{{ viewTitle }}</strong>
      </div>

      <div class="topbar-status">
        <StatusPanel
          :status="backendStatus"
          :label="
            backendStatus === 'online'
              ? '系统在线'
              : backendStatus === 'offline'
                ? '服务离线'
                : '连接检查中'
          "
        />
        <span class="metric-chip resource-unavailable">GPU / CPU 未接入</span>
        <span class="clock">{{ clockText }}</span>
        <button class="avatar-button" type="button" title="账户信息">AI</button>
      </div>
    </header>

    <div class="platform-body">
      <aside class="sidebar">
        <div>
          <div class="nav-heading">平台导航</div>
          <nav class="nav-list" aria-label="平台导航">
            <button
              v-for="item in navItems"
              :key="item.id"
              class="nav-item"
              :class="{ 'nav-item--active': activeView === item.id }"
              type="button"
              @click="switchView(item.id)"
            >
              <span class="nav-item-icon" aria-hidden="true">{{ item.icon }}</span>
              <span>{{ item.label }}</span>
              <span v-if="item.id === 'detection' && results.length" class="nav-count">
                {{ results.length }}
              </span>
            </button>
          </nav>
        </div>
        <div class="sidebar-footer">
          <div class="status-line"><span class="pulse-dot"></span>API {{ backendStatus === 'online' ? '在线' : backendStatus === 'offline' ? '离线' : '检查中' }}</div>
          <div class="sidebar-meta">数据库 {{ databaseStatus === 'online' ? '在线' : databaseStatus === 'offline' ? '离线' : '检查中' }} · 硬件监控未接入</div>
          <div class="sidebar-meta">{{ platformName }} v0.1.0</div>
        </div>
      </aside>

      <main class="main-content">
        <section v-if="activeView === 'dashboard'" class="view-section">
          <div class="view-header">
            <div>
              <span class="view-kicker">COMMAND CENTER / 01</span>
              <h1>系统总览</h1>
              <p>实时掌握无人机遥感图像检测任务与模型运行状态。</p>
            </div>
            <button class="primary-button" type="button" @click="switchView('detection')">
              <span>＋</span> 新建检测任务
            </button>
          </div>

          <div class="stat-grid">
            <article class="stat-card">
              <span class="stat-icon stat-icon--blue">▧</span>
              <div><small>检测图像</small><strong>{{ analytics?.image_count ?? '—' }}</strong><span class="stat-caption">真实数据库统计</span></div>
            </article>
            <article class="stat-card">
              <span class="stat-icon stat-icon--cyan">◎</span>
              <div><small>识别目标</small><strong>{{ analytics?.result_count ?? '—' }}</strong><span class="stat-caption">真实数据库统计</span></div>
            </article>
            <article class="stat-card">
              <span class="stat-icon stat-icon--green">◉</span>
              <div><small>检测任务</small><strong>{{ analytics?.task_count ?? '—' }}</strong><span class="stat-caption">真实数据库统计</span></div>
            </article>
            <article class="stat-card">
              <span class="stat-icon stat-icon--orange">◌</span>
              <div><small>平均置信度</small><strong>{{ analytics?.average_confidence == null ? '—' : `${(analytics.average_confidence * 100).toFixed(1)}%` }}</strong><span class="stat-caption">不代表模型准确率</span></div>
            </article>
          </div>

          <div class="dashboard-grid">
            <section class="panel preview-panel">
              <div class="panel-header"><div><span class="panel-kicker">LIVE PREVIEW</span><h2>最新检测预览</h2></div><button class="ghost-button" type="button" @click="switchView('detection')">打开工作台 →</button></div>
              <div class="dashboard-preview" :class="{ 'dashboard-preview--has-image': previewUrl }">
                <img v-if="historyItems[0]?.image_id" :src="getImageContentUrl(historyItems[0].image_id)" :alt="historyItems[0].image?.original_filename || '最近检测图像'" />
                <div v-else class="preview-placeholder"><span class="crosshair">⊙</span><strong>打开图像检测工作台</strong><small>最新任务的原图与标注可在检测页查看</small></div>
                <div class="scan-line"></div>
              </div>
            </section>
            <section class="panel category-panel">
              <div class="panel-header"><div><span class="panel-kicker">OBJECT DISTRIBUTION</span><h2>目标类别统计</h2></div><span class="panel-unit">全部记录</span></div>
              <div class="category-list">
                <div v-for="item in categoryItems" :key="item.label" class="category-row">
                  <span class="category-color" :class="`category-color--${item.color}`"></span>
                  <span class="category-name">{{ item.label }}</span>
                  <div class="category-bar"><i :class="`category-bar--${item.color}`" :style="{ width: `${item.value}%` }"></i></div>
                  <strong>{{ item.count }}</strong>
                </div>
                <div v-if="!categoryItems.length" class="panel-empty">暂无可统计的真实检测结果</div>
              </div>
              <div class="category-total"><span>已记录目标</span><strong>{{ analytics?.result_count ?? '—' }}</strong></div>
            </section>
          </div>

          <div class="dashboard-grid dashboard-grid--bottom">
            <section class="panel chart-panel">
              <div class="panel-header"><div><span class="panel-kicker">ACTIVITY TREND</span><h2>检测任务趋势</h2></div><span class="panel-unit">近 7 日</span></div>
              <div v-if="recentTasks.length" class="daily-chart" aria-label="近七日检测数量趋势">
                <div v-for="item in recentTasks" :key="item.date" class="daily-bar-column">
                  <strong>{{ item.count }}</strong>
                  <div class="daily-bar-track"><i :style="{ height: `${item.count ? Math.max(3, item.count / Math.max(1, ...recentTasks.map((day) => day.count)) * 100) : 0}%` }"></i></div>
                  <small>{{ item.date.slice(5) }}</small>
                </div>
              </div>
              <div v-else class="panel-empty">统计接口不可用或暂无数据</div>
            </section>
            <section class="panel task-panel">
              <div class="panel-header"><div><span class="panel-kicker">RECENT TASKS</span><h2>最近检测任务</h2></div><button class="ghost-button" type="button" @click="switchView('history')">查看全部 →</button></div>
              <div v-if="historyItems.length" class="mini-task-list">
                <button v-for="task in historyItems.slice(0, 4)" :key="task.id" type="button" class="mini-task" @click="openHistoryTask(task.id); switchView('detection')">
                  <span class="task-file-icon">IMG</span><span class="mini-task-copy"><strong>{{ task.image?.original_filename || `检测任务 #${task.id}` }}</strong><small>{{ formatDate(task.created_at) }}</small></span><span class="mini-task-count">{{ task.results?.length ?? 0 }} 个目标</span>
                </button>
              </div>
              <div v-else class="panel-empty">暂无真实任务记录</div>
            </section>
          </div>
        </section>

        <section v-else-if="activeView === 'detection'" class="view-section">
          <div class="view-header">
            <div><span class="view-kicker">IMAGE ANALYSIS / 02</span><h1>图像检测</h1><p>上传无人机遥感图像，使用 OBB 模型识别工程目标。</p></div>
            <div class="engine-status"><span class="pulse-dot"></span><span>推理模型<small>{{ modelItems.find((model) => model.id === selectedModelId)?.name || '未选择' }}</small></span></div>
          </div>

          <div class="detection-workspace">
            <section class="detect-input panel">
              <div class="panel-header"><div><span class="panel-kicker">IMAGE INPUT</span><h2>图像输入</h2></div><span class="panel-unit">01 / 03</span></div>
              <div class="image-canvas" :class="{ 'image-canvas--dragging': isDragging }" @dragover.prevent="isDragging = true" @dragleave.prevent="isDragging = false" @drop.prevent="onDrop">
                <div v-if="previewUrl" class="canvas-toolbar"><span class="canvas-chip canvas-chip--live"><span class="canvas-chip-dot"></span>{{ showAnnotatedImage ? '预测框图' : '原始图像' }}</span><span class="canvas-chip">{{ imageWidth }} × {{ imageHeight }}</span></div>
                <div v-if="previewUrl" class="image-stage">
                  <img :src="displayImageUrl" :alt="showAnnotatedImage ? `${imageLabel} 预测框图` : imageLabel" @load="onPreviewLoad" @error="onPreviewError" />
                  <svg v-if="activeTask && !showAnnotatedImage && showOverlay && imageWidth && imageHeight && results.length" class="detection-overlay" :viewBox="`0 0 ${imageWidth} ${imageHeight}`" preserveAspectRatio="xMidYMid meet" role="img" aria-label="OBB 检测框">
                    <g v-for="(result, index) in results" :key="result.id ?? index">
                      <polygon :points="pointsAttribute(result.points)" class="detection-polygon" />
                      <text :x="result.points[0][0]" :y="Math.max(14, result.points[0][1] - 5)" class="detection-label">{{ result.class_name }} {{ (result.confidence * 100).toFixed(0) }}%</text>
                    </g>
                  </svg>
                </div>
                <label v-else class="empty-image" for="image-file"><span class="empty-image-symbol">＋</span><strong>拖拽图像至此处</strong><span>或点击选择 JPG / PNG / WEBP 图像</span></label>
              </div>
              <input id="image-file" ref="fileInput" class="visually-hidden" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" @change="selectFile" />
              <div class="input-actions"><label class="secondary-button" for="image-file">选择本地图像</label><div class="file-summary"><strong v-if="selectedFile">{{ selectedFile.name }}</strong><span v-else>尚未选择图像</span><small v-if="selectedFile">{{ formatBytes(selectedFile.size) }}</small></div></div>
              <p v-if="pageError" class="error-message" role="alert"><strong>检测未完成</strong>{{ pageError }}</p>
            </section>

            <section class="detect-settings panel">
              <div class="panel-header"><div><span class="panel-kicker">INFERENCE CONFIG</span><h2>检测参数</h2></div><span class="panel-unit">02 / 03</span></div>
              <label class="field-label">检测模型<select v-model="selectedModelId"><option v-for="model in modelItems" :key="model.id" :value="model.id">{{ model.name }}{{ model.is_default ? ' · 默认' : '' }}</option></select><small class="field-hint">{{ modelItems.length ? '当前选择：' + (modelItems.find((model) => model.id === selectedModelId)?.name || '未选择') : '请先在模型管理中添加 OBB 权重。' }}</small></label>
              <label class="field-label">置信度阈值<span class="field-value">{{ Number(confidenceThreshold).toFixed(2) }}</span><input v-model="confidenceThreshold" type="range" min="0.05" max="0.95" step="0.05" /></label>
              <label class="field-label">NMS 阈值<span class="field-value">{{ Number(nmsThreshold).toFixed(2) }}</span><input v-model="nmsThreshold" type="range" min="0.1" max="0.9" step="0.05" /></label>
              <div class="settings-divider"></div>
              <div class="setting-line"><span>推理设备</span><strong>由后端配置</strong></div>
              <div class="setting-line"><span>输入格式</span><strong>OBB 四角点</strong></div>
              <div class="setting-line"><span>最大文件</span><strong>10 MiB</strong></div>
              <button class="primary-button primary-button--wide" type="button" :disabled="!selectedFile || !selectedModelId || isUploading" @click="runDetection"><span>{{ isUploading ? '◌' : '▷' }}</span>{{ isUploading ? '模型推理中…' : '开始检测' }}</button>
            </section>

            <section class="detect-results panel">
              <div class="panel-header"><div><span class="panel-kicker">DETECTION OUTPUT</span><h2>检测结果</h2></div><span class="panel-unit">03 / 03</span></div>
              <div v-if="activeTask" class="result-content">
                <div class="result-toolbar"><span class="success-badge" :class="{ 'result-badge--error': activeTask.status === 'failed' }">● {{ statusLabel(activeTask.status) }}</span><div><button class="icon-button" type="button" :disabled="!hasAnnotatedImage" :title="hasAnnotatedImage ? '切换预测框图与原图' : '此任务没有生成预测框图'" @click="showAnnotatedImage = !showAnnotatedImage">{{ showAnnotatedImage ? '查看原图' : '预测框图' }}</button><button v-if="!showAnnotatedImage" class="icon-button" type="button" @click="showOverlay = !showOverlay">{{ showOverlay ? '隐藏框' : '显示框' }}</button><button class="icon-button" type="button" @click="downloadAnnotatedImage" :disabled="!hasAnnotatedImage">下载图片</button><button class="icon-button" type="button" @click="downloadResults('json')">JSON</button><button class="icon-button" type="button" @click="downloadResults('txt')">TXT</button></div></div>
                <div class="result-metrics"><div><strong>{{ results.length }}</strong><span>目标总数</span></div><div><strong>{{ averageConfidence }}%</strong><span>平均置信度</span></div><div><strong>{{ highConfidenceCount }}</strong><span>高置信目标</span></div></div>
                <div v-if="results.length" class="result-list">
                  <div v-for="(result, index) in results" :key="result.id ?? index" class="result-row"><span class="result-index">{{ String(index + 1).padStart(2, '0') }}</span><span class="result-type"><strong>{{ result.class_name }}</strong><small>ID {{ result.class_id }}</small></span><span class="result-confidence">{{ (result.confidence * 100).toFixed(1) }}%</span></div>
                </div>
                <div v-else class="panel-empty">当前图像未检测到目标</div>
                <div class="result-meta"><span>{{ imageWidth }} × {{ imageHeight }}</span><span>任务 #{{ activeTask.id }}</span><span>{{ formatDate(activeTask.created_at) }}</span></div>
              </div>
              <div v-else class="panel-empty panel-empty--large"><span class="empty-results-icon">◎</span><strong>等待检测结果</strong><small>上传图像并开始推理后，结果会显示在这里。</small></div>
            </section>
          </div>
        </section>

        <section v-else-if="activeView === 'batch'" class="view-section">
          <div class="view-header">
            <div><span class="view-kicker">BATCH PIPELINE / 03</span><h1>批量检测</h1><p>图像按队列顺序调用真实检测接口。</p></div>
            <div class="batch-header-actions">
              <input ref="batchInput" class="visually-hidden" type="file" multiple accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" @change="addBatchFiles" />
              <button class="secondary-button" type="button" @click="batchInput.click()">＋ 添加图像</button>
              <button class="primary-button" type="button" :disabled="isBatchRunning || !selectedModelId || !batchItems.some((item) => ['排队中', '失败', '已取消'].includes(item.status))" @click="runBatch">开始队列</button>
            </div>
          </div>
          <p v-if="batchError" class="error-message" role="alert">{{ batchError }}</p>
          <section class="panel table-panel">
            <div class="panel-header">
              <div><span class="panel-kicker">QUEUE MONITOR</span><h2>任务队列</h2></div>
              <div class="table-actions">
                <button v-if="isBatchRunning" class="ghost-button" type="button" title="当前图像完成后暂停或继续队列" @click="toggleBatchPause">{{ isBatchPaused ? '继续' : '暂停' }}</button>
                <button v-if="isBatchRunning" class="ghost-button" type="button" title="当前图像完成后停止后续队列任务" @click="cancelBatch">停止后续任务</button>
                <button class="ghost-button" type="button" :disabled="!batchItems.some((item) => item.task)" @click="exportBatchResults">导出 JSON</button>
              </div>
            </div>
            <div class="batch-progress"><span>队列进度</span><strong>{{ batchCompletedCount }} / {{ batchItems.length }} 已完成</strong><i><b :style="{ width: `${batchProgress}%` }"></b></i></div>
            <div class="data-table batch-table">
              <div class="data-head"><span>文件名</span><span>大小</span><span>状态</span><span>进度</span><span>目标数</span><span>操作</span></div>
              <div v-for="item in batchItems" :key="item.id" class="data-row">
                <span class="file-cell"><span class="file-icon">IMG</span>{{ item.name }}</span>
                <span>{{ item.size }}</span>
                <span><em class="table-status" :class="item.status === '已完成' ? 'table-status--success' : item.status === '处理中' ? 'table-status--running' : item.status === '失败' || item.status === '已取消' ? 'table-status--error' : ''" :title="item.error">{{ item.status }}</em></span>
                <span class="progress-cell"><i :class="{ 'progress-indeterminate': item.status === '处理中' }"><b :style="{ width: `${item.progress}%` }"></b></i>{{ item.status === '处理中' ? '推理中' : `${item.progress}%` }}</span>
                <span>{{ item.targets ?? '—' }}</span>
                <button class="row-action" type="button" :disabled="isBatchRunning" @click="removeBatchItem(item.id)">移除</button>
                <small v-if="item.error" class="batch-item-error">{{ item.error }}</small>
              </div>
              <div v-if="!batchItems.length" class="panel-empty">添加图像后即可启动批量检测。</div>
            </div>
          </section>
        </section>

        <section v-else-if="activeView === 'datasets'" class="view-section">
          <div class="view-header"><div><span class="view-kicker">DATA ASSETS / 04</span><h1>数据集管理</h1><p>管理训练、验证和测试数据资产。</p></div><div class="upload-action"><input ref="datasetInput" class="visually-hidden" type="file" accept=".zip,.yaml,.yml" @change="selectDatasetFile" /><button class="primary-button" type="button" @click="datasetInput.click()">＋ 导入数据集</button></div></div>
          <div v-if="selectedDatasetFile" class="selection-notice" role="status"><span class="notice-icon">i</span><span><strong>已选择 {{ selectedDatasetFile.name }}</strong><small>{{ formatBytes(selectedDatasetFile.size) }} · 当前后端尚未提供数据集导入接口，文件未上传或解压。</small></span><button class="notice-dismiss" type="button" aria-label="清除所选数据集" @click="selectedDatasetFile = null">×</button></div>
          <section class="panel table-panel"><div class="panel-header"><div><span class="panel-kicker">DATASET REGISTRY</span><h2>数据集</h2></div></div><div class="panel-empty">数据集文件仅支持本地选择。导入、解压和标注读取 API 尚未实现，因此不展示虚构数据集统计。</div></section>
        </section>

        <section v-else-if="activeView === 'models'" class="view-section">
          <div class="view-header">
            <div><span class="view-kicker">MODEL REGISTRY / 05</span><h1>模型管理</h1><p>按数据集名称登记 OBB 权重，并选择用于后续检测的模型。</p></div>
            <div class="upload-action">
              <input ref="modelInput" class="visually-hidden" type="file" accept=".pt" @change="selectModelFile" />
              <button v-if="modelUploadEnabled" class="secondary-button" type="button" @click="modelInput.click()">选择 .pt 权重</button>
              <button v-if="modelUploadEnabled" class="primary-button" type="button" :disabled="!selectedModelFile || isUploadingModel" @click="uploadSelectedModel">{{ isUploadingModel ? '上传中…' : '上传并登记' }}</button>
            </div>
          </div>
          <p v-if="!modelUploadEnabled" class="upload-disabled-notice">权重上传未启用</p>
          <p v-if="selectedModelFile" class="selection-notice" role="status">待上传：{{ selectedModelFile.name }} · {{ formatBytes(selectedModelFile.size) }}，将以文件名作为数据集名称。</p>
          <p v-if="modelNotice" class="success-message" role="status">{{ modelNotice }}</p>
          <p v-if="modelError" class="error-message" role="alert">{{ modelError }}</p>
          <p class="security-notice">仅上传你信任的 YOLO OBB 权重。权重会在检测时由后端加载；不要将此开发接口暴露到公网。</p>
          <section class="panel table-panel">
            <div class="panel-header"><div><span class="panel-kicker">MODEL REGISTRY</span><h2>可用数据集权重</h2></div><button class="ghost-button" type="button" @click="refreshModels">刷新</button></div>
            <div v-if="modelItems.length" class="model-registry-list">
              <label v-for="model in modelItems" :key="model.id" class="model-registry-row">
                <input v-model="selectedModelId" type="radio" name="active-detection-model" :value="model.id" />
                <span class="model-mini-icon">OBB</span>
                <span class="model-registry-copy"><strong>{{ model.name }}</strong><small>{{ model.is_default ? '由 SKYGUARD_MODEL_PATH 配置' : '本地已登记权重' }}</small></span>
                <span v-if="selectedModelId === model.id" class="model-selected-label">当前检测模型</span>
              </label>
            </div>
            <div v-else class="panel-empty">暂无模型权重。上传 `.pt` 文件，或将权重放入后端 `model_weights/` 目录。</div>
          </section>
        </section>

        <section v-else-if="activeView === 'history'" class="view-section">
          <div class="view-header"><div><span class="view-kicker">TASK ARCHIVE / 06</span><h1>检测记录</h1><p>查看历史检测任务、目标结果与原始图像。</p></div><button class="ghost-button" type="button" :disabled="isLoadingHistory" @click="refreshHistory">↻ 刷新记录</button></div>
          <section class="panel table-panel"><div class="filter-bar"><input v-model="historySearch" placeholder="搜索图像名称或任务编号" @keyup.enter="searchHistory()" /><select v-model="historyStatus"><option value="">全部状态</option><option value="succeeded">已完成</option><option value="running">处理中</option><option value="pending">等待中</option><option value="failed">失败</option></select><input v-model="historyDateFrom" type="date" aria-label="开始日期" /><input v-model="historyDateTo" type="date" aria-label="结束日期" /><button class="secondary-button" type="button" @click="searchHistory()">筛选</button></div><div v-if="historyError" class="error-message">{{ historyError }}</div><div v-else class="data-table history-table"><div class="data-head"><span>任务编号</span><span>图像名称</span><span>模型</span><span>目标数</span><span>状态</span><span>创建时间</span></div><button v-for="task in historyItems" :key="task.id" class="data-row data-row--button" type="button" @click="openHistoryTask(task.id); switchView('detection')"><span class="task-id">#{{ task.id }}</span><span>{{ task.image?.original_filename || `图像 #${task.image_id}` }}</span><span>{{ task.model_name || '当前模型' }}</span><span>{{ task.results?.length ?? 0 }}</span><span><em class="table-status" :class="task.status === 'succeeded' ? 'table-status--success' : ''">{{ statusLabel(task.status) }}</em></span><span>{{ formatDate(task.created_at) }}</span></button><div v-if="!historyItems.length" class="panel-empty">暂无匹配记录</div></div><div class="pagination"><span>共 {{ historyTotal }} 条</span><button class="ghost-button" type="button" :disabled="historyPage === 0 || isLoadingHistory" @click="historyPage--; searchHistory(false)">上一页</button><span>第 {{ historyTotal ? historyPage + 1 : 0 }} / {{ Math.ceil(historyTotal / 20) }} 页</span><button class="ghost-button" type="button" :disabled="(historyPage + 1) * 20 >= historyTotal || isLoadingHistory" @click="historyPage++; searchHistory(false)">下一页</button></div></section></section>

        <section v-else-if="activeView === 'analytics'" class="view-section">
          <div class="view-header"><div><span class="view-kicker">ANALYTICS / 07</span><h1>数据统计</h1><p>从检测任务数量与已记录目标类别观察平台运行情况。</p></div><span class="date-chip">全量记录</span></div>
          <div class="analytics-grid"><section class="panel chart-panel chart-panel--wide"><div class="panel-header"><div><span class="panel-kicker">DETECTION VOLUME</span><h2>检测数量变化</h2></div><span class="panel-unit">近七日真实任务</span></div><div v-if="recentTasks.length" class="daily-chart daily-chart--large"><div v-for="item in recentTasks" :key="item.date" class="daily-bar-column"><strong>{{ item.count }}</strong><div class="daily-bar-track"><i :style="{ height: `${item.count ? Math.max(3, item.count / Math.max(1, ...recentTasks.map((day) => day.count)) * 100) : 0}%` }"></i></div><small>{{ item.date }}</small></div></div><div v-else class="panel-empty">统计接口不可用或暂无数据</div></section><section class="panel"><div class="panel-header"><div><span class="panel-kicker">CLASS SHARE</span><h2>类别占比</h2></div></div><div v-if="categoryItems.length" class="donut-wrap"><div class="donut" :style="categoryDonutStyle"><strong>{{ categoryVisibleTotal }}</strong><small>前五类别</small></div><div class="donut-legend"><span v-for="item in categoryItems" :key="item.label"><i :class="`category-color--${item.color}`"></i>{{ item.label }} <b>{{ item.count }}</b></span></div></div><div v-else class="panel-empty">暂无可统计类别</div></section></div>
        </section>

        <section v-else class="view-section">
          <div class="view-header"><div><span class="view-kicker">SYSTEM CONFIG / 08</span><h1>系统设置</h1><p>配置平台运行参数、存储和通知选项。</p></div><button v-if="isDeveloper" class="primary-button" type="button" @click="savePlatformName">保存设置</button></div>
          <div class="settings-grid"><section class="panel settings-panel"><span class="panel-kicker">GENERAL</span><h2>通用设置</h2><label class="field-label">平台名称<input v-model="editablePlatformName" :readonly="!isDeveloper" :class="{ 'field-readonly': !isDeveloper }" /><small class="field-hint">{{ isDeveloper ? '开发者模式：名称保存到当前浏览器。' : '仅开发者可修改平台名称。' }}</small></label><div class="field-label">检测模型<div class="setting-line"><span>当前选择</span><strong>{{ modelItems.find((model) => model.id === selectedModelId)?.name || '未选择' }}</strong></div></div><label class="toggle-line"><span><strong>检测完成通知</strong><small>任务结束后显示桌面提示</small></span><input type="checkbox" checked /></label></section><section class="panel settings-panel"><span class="panel-kicker">STORAGE</span><h2>存储与服务</h2><div class="setting-line"><span>上传目录</span><strong>项目目录 / uploads</strong></div><div class="setting-line"><span>API 服务</span><strong :class="backendStatus === 'online' ? 'text-success' : ''">{{ backendStatus === 'online' ? '在线' : backendStatus === 'offline' ? '离线' : '检查中' }}</strong></div><div class="setting-line"><span>数据库</span><strong :class="databaseStatus === 'online' ? 'text-success' : ''">MySQL / {{ databaseStatus === 'online' ? '已连接' : databaseStatus === 'offline' ? '不可用' : '检查中' }}</strong></div><div class="setting-line"><span>模型目录</span><strong>backend/model_weights</strong></div></section></div>
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
:global(*) { box-sizing: border-box; }
:global(html) { background: #07111f; }
:global(body) { margin: 0; color: #dceafa; background: #07111f; font-family: Inter, "Segoe UI", "Microsoft YaHei", sans-serif; font-size: 13px; }
:global(button), :global(input), :global(select) { font: inherit; }
:global(button:focus-visible), :global(input:focus-visible), :global(select:focus-visible) { outline: 2px solid #168bff; outline-offset: 2px; }

.platform-shell { min-height: 100vh; background: #07111f; }
.topbar { height: 68px; display: flex; align-items: center; justify-content: space-between; gap: 28px; padding: 0 24px; background: #0b192b; border-bottom: 1px solid #17314a; }
.brand { display: flex; align-items: center; gap: 11px; min-width: 250px; color: inherit; text-decoration: none; }
.brand-symbol { position: relative; width: 31px; height: 31px; display: grid; place-items: center; border: 1px solid #168bff; transform: rotate(45deg); }
.brand-symbol::before, .brand-symbol::after, .brand-symbol span { content: ""; position: absolute; display: block; background: #00d4ff; }
.brand-symbol::before { width: 1px; height: 25px; }
.brand-symbol::after { width: 25px; height: 1px; }
.brand-symbol span { width: 7px; height: 7px; background: #168bff; border-radius: 50%; }
.brand-copy strong, .brand-copy small { display: block; }
.brand-copy strong { color: #edf7ff; font-size: 15px; letter-spacing: .06em; }
.brand-copy em { color: #00d4ff; font-style: normal; }
.brand-copy small { margin-top: 3px; color: #6f8ca5; font-size: 10px; }
.topbar-center { display: flex; align-items: center; gap: 11px; flex: 1; color: #d7e7f5; font-size: 12px; }
.breadcrumb { color: #6c8aa4; }
.breadcrumb-divider { color: #2d4b65; }
.topbar-status { display: flex; align-items: center; gap: 12px; white-space: nowrap; }
.metric-chip, .clock { color: #87a6bf; font-size: 11px; }
.metric-chip { display: inline-flex; align-items: center; gap: 5px; }
.metric-dot { width: 5px; height: 5px; border-radius: 50%; }
.metric-dot.blue { background: #168bff; box-shadow: 0 0 8px #168bff; }
.metric-dot.green { background: #55e6a5; box-shadow: 0 0 8px #55e6a5; }
.clock { padding-left: 11px; border-left: 1px solid #1c3850; font-variant-numeric: tabular-nums; }
.avatar-button { width: 30px; height: 30px; color: #07111f; background: #00d4ff; border: 0; border-radius: 50%; font-size: 11px; font-weight: 800; cursor: pointer; }

.platform-body { display: grid; grid-template-columns: 224px minmax(0, 1fr); min-height: calc(100vh - 68px); }
.sidebar { display: flex; flex-direction: column; justify-content: space-between; padding: 27px 13px 18px; background: #091625; border-right: 1px solid #142d45; }
.nav-heading { padding: 0 13px 12px; color: #53708a; font-size: 10px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
.nav-list { display: grid; gap: 4px; }
.nav-item { position: relative; display: flex; align-items: center; gap: 11px; min-height: 40px; width: 100%; padding: 0 13px; color: #7893aa; background: transparent; border: 1px solid transparent; cursor: pointer; text-align: left; transition: color .16s ease, background .16s ease, border-color .16s ease; }
.nav-item:hover { color: #d4e9fa; background: #0d2238; }
.nav-item--active { color: #e9f7ff; background: #0d2b47; border-color: #145485; }
.nav-item--active::before { content: ""; position: absolute; left: -1px; top: 7px; bottom: 7px; width: 2px; background: #00d4ff; box-shadow: 0 0 10px #00d4ff; }
.nav-item-icon { width: 20px; color: #168bff; font-size: 16px; text-align: center; }
.nav-count { margin-left: auto; padding: 2px 6px; color: #9feaff; background: #0b5271; border-radius: 3px; font-size: 10px; }
.sidebar-footer { padding: 15px 13px 0; border-top: 1px solid #17314a; }
.status-line { display: flex; align-items: center; gap: 7px; color: #9ab2c5; font-size: 11px; }
.pulse-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #55e6a5; box-shadow: 0 0 0 4px rgba(85,230,165,.12), 0 0 9px #55e6a5; }
.sidebar-meta { margin-top: 8px; color: #4f6d84; font-size: 10px; }

.main-content { min-width: 0; padding: 31px 36px 55px; background-color: #07111f; background-image: linear-gradient(rgba(22,139,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(22,139,255,.035) 1px, transparent 1px); background-size: 32px 32px; }
.view-section { width: min(1500px, 100%); margin: 0 auto; }
.view-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 25px; }
.view-kicker, .panel-kicker { display: block; color: #4d8db9; font-size: 9px; font-weight: 800; letter-spacing: .14em; }
.view-header h1 { margin: 8px 0 6px; color: #f1f8ff; font-size: 28px; letter-spacing: .01em; }
.view-header p { margin: 0; color: #6c879d; font-size: 12px; }
.panel { background: rgba(11, 25, 43, .88); border: 1px solid #173650; box-shadow: 0 15px 30px rgba(0,0,0,.14); }
.panel-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; margin-bottom: 21px; }
.panel-header h2 { margin: 6px 0 0; color: #d9e9f7; font-size: 15px; }
.panel-unit { color: #54758f; font-size: 10px; }
.primary-button, .secondary-button, .ghost-button, .icon-button, .row-action { display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-height: 35px; padding: 0 13px; border-radius: 3px; cursor: pointer; font-size: 11px; font-weight: 700; }
.primary-button { color: #04111e; background: #168bff; border: 1px solid #168bff; box-shadow: 0 0 18px rgba(22,139,255,.2); }
.primary-button:hover { background: #35a0ff; }
.primary-button:disabled { opacity: .45; cursor: not-allowed; }
.primary-button--wide { width: 100%; margin-top: 22px; }
.secondary-button { color: #a9d8ee; background: #102b43; border: 1px solid #245a7d; }
.ghost-button, .icon-button, .row-action { color: #6ea4c4; background: transparent; border: 1px solid transparent; }
.ghost-button:hover, .icon-button:hover, .row-action:hover { color: #b8eaff; border-color: #204c6d; background: #0d263d; }
.icon-button { min-height: 27px; padding: 0 8px; border-color: #204661; font-size: 10px; }
.date-chip { padding: 8px 11px; color: #8cb6d2; background: #0b2034; border: 1px solid #204761; font-size: 11px; }
.upload-action { display: inline-flex; align-items: center; gap: 8px; }
.selection-notice { display: flex; align-items: center; gap: 11px; margin: -8px 0 16px; padding: 11px 13px; color: #9fc4d9; background: rgba(0, 212, 255, .055); border: 1px solid #1b4a63; }
.upload-disabled-notice, .security-notice { margin: 0 0 14px; color: #7595aa; font-size: 10px; }
.security-notice { padding: 10px 12px; background: #0b1e30; border-left: 2px solid #ffad5b; }
.success-message { margin: 0 0 12px; padding: 9px 11px; color: #75dcae; background: rgba(85,230,165,.07); border-left: 2px solid #55e6a5; font-size: 11px; }
.notice-icon { display: grid; width: 21px; height: 21px; flex: 0 0 21px; place-items: center; color: #00d4ff; border: 1px solid #18738d; border-radius: 50%; font-size: 11px; font-weight: 700; }
.selection-notice strong, .selection-notice small { display: block; }
.selection-notice strong { color: #c9e9f5; font-size: 11px; overflow-wrap: anywhere; }
.selection-notice small { margin-top: 3px; color: #6f9bb2; font-size: 10px; line-height: 1.5; }
.notice-dismiss { width: 26px; height: 26px; flex: 0 0 26px; margin-left: auto; color: #769ab0; background: transparent; border: 0; cursor: pointer; font-size: 18px; }

.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 18px; }
.stat-card { display: flex; align-items: center; gap: 13px; min-height: 105px; padding: 18px; background: rgba(11,25,43,.84); border: 1px solid #173650; }
.stat-icon { display: grid; width: 36px; height: 36px; flex: 0 0 36px; place-items: center; border: 1px solid currentColor; border-radius: 4px; font-size: 17px; }
.stat-icon--blue { color: #168bff; background: rgba(22,139,255,.1); }.stat-icon--cyan { color: #00d4ff; background: rgba(0,212,255,.08); }.stat-icon--green { color: #55e6a5; background: rgba(85,230,165,.08); }.stat-icon--orange { color: #ffad5b; background: rgba(255,173,91,.08); }
.stat-card small, .stat-card strong, .stat-trend, .stat-caption { display: block; }
.stat-card small { color: #7694aa; font-size: 10px; }.stat-card strong { margin: 6px 0 4px; color: #e9f6ff; font-size: 24px; line-height: 1; }.stat-trend { color: #55e6a5; font-size: 10px; }.stat-caption { color: #607f98; font-size: 10px; }

.dashboard-grid { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(300px, 1fr); gap: 14px; margin-bottom: 14px; }
.dashboard-grid--bottom { grid-template-columns: minmax(0, 1.5fr) minmax(300px, 1fr); }
.preview-panel, .category-panel, .chart-panel, .task-panel { min-width: 0; padding: 20px; }
.dashboard-preview { position: relative; min-height: 265px; display: grid; place-items: center; overflow: hidden; background: #07111f; border: 1px solid #173650; }
.dashboard-preview img { width: 100%; height: 265px; object-fit: contain; }.preview-placeholder { display: grid; gap: 9px; place-items: center; color: #5c7c95; }.preview-placeholder strong { color: #8caec5; font-size: 12px; }.preview-placeholder small { font-size: 10px; }.crosshair { color: #168bff; font-size: 38px; }.scan-line { position: absolute; left: 0; right: 0; top: 25%; height: 1px; background: #00d4ff; opacity: .25; box-shadow: 0 0 12px #00d4ff; animation: scan 4s linear infinite; pointer-events: none; }
@keyframes scan { from { transform: translateY(0); } to { transform: translateY(190px); } }
.category-list { display: grid; gap: 18px; margin-top: 28px; }.category-row { display: grid; grid-template-columns: 9px 72px minmax(0, 1fr) 42px; align-items: center; gap: 8px; color: #92aec1; font-size: 11px; }.category-color { width: 6px; height: 6px; border-radius: 50%; }.category-color--blue, .category-bar--blue { background: #168bff; }.category-color--cyan, .category-bar--cyan { background: #00d4ff; }.category-color--green, .category-bar--green { background: #55e6a5; }.category-color--orange, .category-bar--orange { background: #ffad5b; }.category-bar { height: 4px; background: #122b42; }.category-bar i { display: block; height: 100%; }.category-row strong { color: #c8ddea; text-align: right; font-size: 11px; }.category-total { display: flex; justify-content: space-between; margin-top: 24px; padding-top: 14px; color: #607f96; border-top: 1px solid #173650; font-size: 10px; }.category-total strong { color: #d8ebf7; font-size: 16px; }
.line-chart { position: relative; height: 182px; padding: 5px 0 20px 34px; }.line-chart svg { width: 100%; height: 145px; overflow: visible; }.chart-y { position: absolute; left: 0; top: 0; bottom: 22px; display: flex; flex-direction: column; justify-content: space-between; color: #50708a; font-size: 9px; }.chart-x { display: flex; justify-content: space-between; color: #50708a; font-size: 9px; }.chart-line { fill: none; stroke-width: 2; vector-effect: non-scaling-stroke; }.chart-line--blue { stroke: #168bff; filter: drop-shadow(0 0 4px rgba(22,139,255,.7)); }.chart-line--cyan { stroke: #00d4ff; filter: drop-shadow(0 0 4px rgba(0,212,255,.7)); }.chart-area { fill: rgba(22,139,255,.08); }.chart-area--cyan { fill: rgba(0,212,255,.08); }
.daily-chart { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 12px; height: 175px; padding-top: 12px; }.daily-chart--large { height: 250px; }.daily-bar-column { display: grid; grid-template-rows: 16px minmax(0, 1fr) 18px; justify-items: center; gap: 7px; min-width: 0; color: #64849c; font-size: 9px; }.daily-bar-column strong { color: #9bbbd0; font-size: 10px; font-weight: 500; font-variant-numeric: tabular-nums; }.daily-bar-column small { overflow: hidden; max-width: 100%; color: #587890; text-overflow: ellipsis; white-space: nowrap; }.daily-bar-track { display: flex; align-items: flex-end; width: min(100%, 34px); height: 100%; background: #0a1d30; border-bottom: 1px solid #21445f; }.daily-bar-track i { display: block; width: 100%; min-height: 0; background: linear-gradient(0deg, #168bff, #00d4ff); box-shadow: 0 0 12px rgba(22,139,255,.18); }
.mini-task-list { display: grid; gap: 2px; }.mini-task { display: grid; grid-template-columns: 31px minmax(0,1fr) auto; align-items: center; gap: 9px; min-height: 47px; padding: 4px; color: #aec5d5; background: transparent; border: 0; border-bottom: 1px solid #142f47; cursor: pointer; text-align: left; }.mini-task:hover { background: #0d263d; }.task-file-icon, .file-icon { display: grid; place-items: center; color: #67aee0; background: #102d47; font-size: 8px; }.task-file-icon { width: 29px; height: 29px; }.mini-task-copy { min-width: 0; }.mini-task-copy strong, .mini-task-copy small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.mini-task-copy strong { color: #bdd4e3; font-size: 11px; }.mini-task-copy small { margin-top: 3px; color: #58778f; font-size: 9px; }.mini-task-count { color: #6d9abb; font-size: 10px; }.panel-empty { display: grid; min-height: 120px; place-items: center; color: #5d7c94; font-size: 11px; }.panel-empty--large { min-height: 280px; gap: 7px; align-content: center; }.panel-empty--large strong { color: #91b2c8; }.panel-empty--large small { color: #5e7e96; }.empty-results-icon { color: #168bff; font-size: 32px; }

.detection-workspace { display: grid; grid-template-columns: minmax(0, 1.45fr) 275px minmax(280px, .85fr); gap: 14px; align-items: stretch; }.detect-input, .detect-settings, .detect-results { min-width: 0; min-height: 590px; padding: 20px; }.image-canvas { position: relative; height: 425px; display: flex; align-items: center; justify-content: center; overflow: hidden; background-color: #07111f; background-image: linear-gradient(45deg, #0a1d30 25%, transparent 25%), linear-gradient(-45deg, #0a1d30 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #0a1d30 75%), linear-gradient(-45deg, transparent 75%, #0a1d30 75%); background-position: 0 0,0 8px,8px -8px,-8px 0; background-size: 16px 16px; border: 1px solid #173650; }.image-canvas--dragging { border-color: #00d4ff; box-shadow: 0 0 18px rgba(0,212,255,.16); }.canvas-toolbar { position: absolute; z-index: 2; top: 10px; left: 10px; display: flex; gap: 6px; pointer-events: none; }.canvas-chip { display: inline-flex; align-items: center; gap: 5px; min-height: 23px; padding: 0 8px; color: #7c9bb2; background: rgba(8,22,36,.9); border: 1px solid #245372; border-radius: 2px; font-size: 9px; }.canvas-chip--live { color: #75daf2; }.canvas-chip-dot { width: 5px; height: 5px; border-radius: 50%; background: #55e6a5; }.image-stage { position: relative; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; line-height: 0; }.image-stage img { display: block; width: auto; height: auto; max-width: 100%; max-height: 100%; object-fit: contain; }.detection-overlay { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }.detection-polygon { fill: rgba(22,139,255,.1); stroke: #00d4ff; stroke-width: 2; vector-effect: non-scaling-stroke; }.detection-label { fill: #dff9ff; font-size: 16px; paint-order: stroke; stroke: #07111f; stroke-width: 4px; stroke-linejoin: round; }.empty-image { display: grid; justify-items: center; gap: 9px; color: #62829a; cursor: pointer; text-align: center; }.empty-image strong { color: #9bb8ca; font-size: 12px; }.empty-image span:last-child { font-size: 10px; }.empty-image-symbol { display: grid; width: 43px; height: 43px; place-items: center; color: #168bff; background: #0e2c49; border: 1px solid #1e5e8a; border-radius: 50%; font-size: 24px; }.input-actions { display: flex; align-items: center; gap: 11px; margin-top: 14px; }.file-summary { min-width: 0; display: flex; align-items: baseline; gap: 8px; color: #7897ac; font-size: 10px; }.file-summary strong { overflow: hidden; color: #bbd1df; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.file-summary small { color: #55758d; }.error-message { display: flex; gap: 8px; margin: 12px 0 0; padding: 9px; color: #ff9c91; background: rgba(196,65,54,.1); border-left: 2px solid #ed6c5d; font-size: 10px; }.field-label { position: relative; display: block; margin-top: 25px; color: #7898ae; font-size: 10px; }.field-label select, .field-label input:not([type="range"]) { width: 100%; height: 35px; margin-top: 8px; padding: 0 9px; color: #cce0ed; background: #091b2d; border: 1px solid #1d435e; border-radius: 2px; }.field-label select { appearance: auto; }.field-label input[type="range"] { width: 100%; margin-top: 12px; accent-color: #168bff; }.field-value { float: right; color: #00d4ff; font-variant-numeric: tabular-nums; }.settings-divider { height: 1px; margin: 27px 0 17px; background: #173650; }.setting-line { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 0; color: #607f96; border-bottom: 1px solid #122d45; font-size: 10px; }.setting-line strong { color: #a5c1d2; font-weight: 500; text-align: right; }.text-success { color: #55e6a5 !important; }.result-content { display: flex; flex-direction: column; min-height: 500px; }.result-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 8px; }.result-toolbar > div { display: flex; gap: 4px; }.success-badge { color: #55e6a5; font-size: 10px; }.result-badge--error { color: #ff9c91; }.result-metrics { display: grid; grid-template-columns: repeat(3,1fr); gap: 0; margin: 21px 0 17px; padding: 14px 0; border-top: 1px solid #173650; border-bottom: 1px solid #173650; }.result-metrics div { padding: 0 8px; border-left: 1px solid #173650; }.result-metrics div:first-child { padding-left: 0; border-left: 0; }.result-metrics strong, .result-metrics span { display: block; }.result-metrics strong { color: #e5f5ff; font-size: 20px; }.result-metrics span { margin-top: 4px; color: #66879e; font-size: 9px; }.result-list { overflow: auto; max-height: 350px; }.result-row { display: grid; grid-template-columns: 25px minmax(0,1fr) auto; align-items: center; gap: 9px; min-height: 45px; border-bottom: 1px solid #122f47; }.result-index { color: #53758c; font-size: 9px; }.result-type strong, .result-type small { display: block; }.result-type strong { color: #c7e1ee; font-size: 11px; }.result-type small { margin-top: 3px; color: #5d7c94; font-size: 9px; }.result-confidence { color: #55e6a5; font-size: 11px; font-variant-numeric: tabular-nums; }.result-meta { display: flex; justify-content: space-between; gap: 8px; margin-top: auto; padding-top: 14px; color: #5d7d95; border-top: 1px solid #173650; font-size: 9px; }

.table-panel { padding: 20px; }.table-actions, .batch-header-actions { display: flex; align-items: center; gap: 5px; }.batch-progress { display: grid; grid-template-columns: 1fr auto; gap: 8px; margin-bottom: 19px; color: #7593a9; font-size: 10px; }.batch-progress strong { color: #b9d5e5; font-weight: 500; }.batch-progress i { grid-column: 1 / -1; height: 5px; background: #112c44; }.batch-progress i b { display: block; height: 100%; background: #168bff; }.data-table { overflow: hidden; border: 1px solid #173650; }.data-head, .data-row { display: grid; grid-template-columns: minmax(180px, 1.6fr) .65fr .8fr 1.2fr .65fr .55fr; align-items: center; gap: 13px; min-height: 49px; padding: 0 15px; }.data-head { min-height: 34px; color: #5f7e95; background: #091b2d; font-size: 9px; text-transform: uppercase; }.data-row { color: #91adbf; border-top: 1px solid #122f47; font-size: 11px; }.data-row--button { width: 100%; color: #91adbf; background: transparent; border-right: 0; border-bottom: 0; border-left: 0; cursor: pointer; text-align: left; }.data-row--button:hover { background: #0d263d; }.file-cell, .model-cell { display: flex; align-items: center; gap: 9px; min-width: 0; }.file-cell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.file-icon { width: 29px; height: 25px; flex: 0 0 29px; }.progress-cell { display: flex; align-items: center; gap: 7px; color: #6c8ea5; font-size: 9px; }.progress-cell i { width: 70px; height: 4px; background: #122d45; }.progress-cell b { display: block; height: 100%; background: #168bff; }.progress-cell i.progress-indeterminate { position: relative; overflow: hidden; }.progress-cell i.progress-indeterminate b { position: absolute; width: 35% !important; animation: progress-sweep 1.2s ease-in-out infinite alternate; }.batch-item-error { grid-column: 1 / -1; padding: 0 0 9px 38px; color: #ff9c91; font-size: 10px; overflow-wrap: anywhere; }.table-status { display: inline-flex; padding: 3px 6px; color: #f7bf73; background: rgba(255,173,91,.1); border-radius: 2px; font-size: 9px; font-style: normal; }.table-status--success { color: #55e6a5; background: rgba(85,230,165,.1); }.table-status--running { color: #71dfff; background: rgba(0,212,255,.1); }.table-status--error { color: #ff9c91; background: rgba(237,108,93,.1); }.model-cell strong { overflow: hidden; color: #c3dbea; font-size: 11px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }.model-mini-icon { display: grid; width: 27px; height: 27px; place-items: center; color: #00d4ff; background: #0b3048; border: 1px solid #1a6685; font-size: 8px; }.metric-number, .task-id { color: #55e6a5; }.filter-bar { display: flex; gap: 9px; margin-bottom: 16px; }.filter-bar input, .filter-bar select { height: 34px; padding: 0 10px; color: #b8d0df; background: #091b2d; border: 1px solid #1c425e; border-radius: 2px; font-size: 10px; }.filter-bar input { min-width: 280px; }.filter-bar input::placeholder { color: #54738b; }.history-table .data-head, .history-table .data-row { grid-template-columns: .65fr 1.4fr 1fr .6fr .75fr 1.1fr; }
.model-registry-list { display: grid; }.model-registry-row { display: flex; align-items: center; gap: 12px; min-height: 61px; padding: 8px 12px; border-top: 1px solid #173650; cursor: pointer; }.model-registry-row input { accent-color: #168bff; }.model-registry-copy { display: grid; gap: 4px; min-width: 0; }.model-registry-copy strong { color: #cce2ef; font-size: 12px; overflow-wrap: anywhere; }.model-registry-copy small { color: #68869d; font-size: 10px; }.model-selected-label { margin-left: auto; color: #55e6a5; font-size: 10px; }
.pagination { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-top: 14px; color: #6e8ca3; font-size: 10px; }.pagination > span:first-child { margin-right: auto; }.progress-cell i.progress-indeterminate b { transform: translateX(0); }@keyframes progress-sweep { to { transform: translateX(185%); } }

.dataset-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }.dataset-card { overflow: hidden; }.dataset-cover { height: 120px; display: flex; flex-direction: column; justify-content: flex-end; gap: 3px; padding: 17px; background: #0b273f; background-image: linear-gradient(135deg, rgba(0,212,255,.12) 1px, transparent 1px), linear-gradient(45deg, rgba(22,139,255,.1) 1px, transparent 1px); background-size: 22px 22px; border-bottom: 1px solid #173650; }.dataset-cover span { color: #5cc9eb; font-size: 23px; font-weight: 800; letter-spacing: .12em; }.dataset-cover small { color: #5f90af; font-size: 9px; letter-spacing: .14em; }.dataset-body { padding: 16px; }.dataset-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; }.dataset-title h2 { margin: 0; color: #d4e8f5; font-size: 13px; }.dataset-stats { display: grid; grid-template-columns: repeat(3,1fr); margin: 19px 0 15px; padding: 12px 0; border-top: 1px solid #173650; border-bottom: 1px solid #173650; }.dataset-stats div { padding: 0 8px; border-left: 1px solid #173650; }.dataset-stats div:first-child { padding-left: 0; border-left: 0; }.dataset-stats strong, .dataset-stats small { display: block; }.dataset-stats strong { color: #c8e1ef; font-size: 15px; }.dataset-stats small { margin-top: 4px; color: #62839a; font-size: 9px; }.dataset-footer { display: flex; align-items: center; justify-content: space-between; color: #587890; font-size: 9px; }

.analytics-grid { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(310px, 1fr); gap: 14px; }.chart-panel--wide { min-height: 330px; }.line-chart--large { height: 245px; }.line-chart--large svg { height: 205px; }.donut-wrap { display: flex; align-items: center; gap: 28px; min-height: 245px; }.donut { position: relative; width: 156px; height: 156px; flex: 0 0 156px; display: grid; place-content: center; text-align: center; border-radius: 50%; }.donut::before { position: absolute; inset: 17px; content: ""; background: #0b192b; border-radius: 50%; }.donut strong, .donut small { position: relative; z-index: 1; }.donut strong { color: #e1f2fb; font-size: 21px; }.donut small { margin-top: 4px; color: #65859b; font-size: 9px; }.donut-legend { display: grid; gap: 14px; color: #8ba9bb; font-size: 10px; }.donut-legend span { display: grid; grid-template-columns: 8px 1fr auto; gap: 6px; align-items: center; }.donut-legend i { width: 6px; height: 6px; border-radius: 50%; }.donut-legend b { color: #d3e7f2; font-weight: 500; }

.settings-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }.settings-panel { min-height: 355px; padding: 21px; }.settings-panel h2 { margin: 8px 0 20px; color: #d8eafa; font-size: 16px; }.toggle-line { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 27px; padding-top: 18px; border-top: 1px solid #173650; }.toggle-line strong, .toggle-line small { display: block; }.toggle-line strong { color: #a8c4d4; font-size: 11px; font-weight: 500; }.toggle-line small { margin-top: 4px; color: #5e7c93; font-size: 9px; }.toggle-line input { width: 35px; height: 19px; accent-color: #168bff; }

.field-hint { display: block; margin-top: 6px; color: #5e7e96; font-size: 9px; line-height: 1.4; }
.field-readonly { color: #718da2 !important; background: #071625 !important; border-color: #173650 !important; cursor: not-allowed; }
.visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }

/* Keep the dark palette while giving important boundaries more contrast. */
.panel,
.stat-card,
.dataset-card,
.settings-panel,
.detect-input,
.detect-settings,
.detect-results { border-color: #28506b; }
.dashboard-preview,
.image-canvas,
.data-table { border-color: #32617d; }
.field-label select,
.field-label input:not([type="range"]),
.filter-bar input,
.filter-bar select { border-color: #315a76; }
.sidebar,
.topbar,
.sidebar-footer,
.category-total,
.result-metrics,
.result-meta,
.dataset-stats,
.toggle-line { border-color: #25445e; }
.data-row,
.mini-task,
.result-row,
.setting-line,
.model-registry-row { border-color: #203f58; }

@media (max-width: 1250px) {
  .topbar-center { display: none; }
  .topbar-status .metric-chip { display: none; }
  .detection-workspace { grid-template-columns: minmax(0, 1fr) 270px; }
  .detect-results { grid-column: 1 / -1; min-height: 360px; }
  .result-content { min-height: 280px; }
  .result-list { max-height: 230px; }
}

@media (max-width: 900px) {
  .platform-body { grid-template-columns: 74px minmax(0, 1fr); }
  .sidebar { padding-right: 8px; padding-left: 8px; }
  .nav-heading, .nav-item span:not(.nav-item-icon), .sidebar-footer { display: none; }
  .nav-item { justify-content: center; padding: 0; }
  .nav-item-icon { font-size: 18px; }
  .main-content { padding: 25px 20px 40px; }
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .dashboard-grid, .dashboard-grid--bottom, .analytics-grid { grid-template-columns: 1fr; }
  .dataset-grid { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 680px) {
  .topbar { height: 61px; padding: 0 14px; }
  .brand { min-width: 0; }.brand-copy small, .clock { display: none; }.topbar-status { gap: 8px; }
  .platform-body { display: block; }.sidebar { display: none; }
  .main-content { padding: 22px 14px 35px; }
  .view-header { align-items: flex-start; flex-direction: column; }
  .upload-action { width: 100%; }
  .view-header h1 { font-size: 24px; }
  .detection-workspace { display: block; }.detect-input, .detect-settings, .detect-results { min-height: auto; margin-bottom: 14px; }
  .detect-settings { min-height: 430px; }.detect-results { min-height: 390px; }
  .image-canvas { height: 310px; }
  .stat-grid, .dataset-grid, .settings-grid { grid-template-columns: 1fr; }
  .data-table { overflow-x: auto; }.data-head, .data-row { min-width: 790px; }
  .filter-bar { flex-wrap: wrap; }.filter-bar input { min-width: 100%; }
}
</style>
