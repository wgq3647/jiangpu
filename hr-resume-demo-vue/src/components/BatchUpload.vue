<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { resumeApi } from '../api/index.js'

const emit = defineEmits(['upload-complete'])

// 支持的文件格式
const ACCEPTED_TYPES = '.pdf,.docx,.doc,.txt,.md,.png,.jpg,.jpeg,.gif,.bmp'
const MAX_FILE_SIZE = 20 * 1024 * 1024 // 20MB

// 状态
const isDragging = ref(false)
const isUploading = ref(false)
const batchId = ref(null)
const batchJob = ref(null)
const pollTimer = ref(null)
const errorMsg = ref('')
const fileInput = ref(null) // Vue 3 ref引用

// 计算属性
const overallProgress = computed(() => batchJob.value?.overall_progress || 0)
const successCount = computed(() => batchJob.value?.success_count || 0)
const failedCount = computed(() => batchJob.value?.failed_count || 0)
const pendingCount = computed(() => batchJob.value?.pending_count || 0)
const isProcessing = computed(() => batchJob.value?.status === 'processing')
const isCompleted = computed(() => batchJob.value && batchJob.value.status !== 'processing')

// 文件选择
function handleFileSelect(event) {
  const files = Array.from(event.target.files)
  processFiles(files)
  event.target.value = '' // 重置以便重复选择同一文件
}

// 拖拽
function handleDragOver(e) {
  e.preventDefault()
  isDragging.value = true
}
function handleDragLeave() {
  isDragging.value = false
}
function handleDrop(e) {
  e.preventDefault()
  isDragging.value = false
  const files = Array.from(e.dataTransfer.files)
  processFiles(files)
}

// 处理文件
function processFiles(files) {
  errorMsg.value = ''

  // 过滤不支持的格式
  const validFiles = []
  const invalidFiles = []
  files.forEach(file => {
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!ACCEPTED_TYPES.includes(ext)) {
      invalidFiles.push(file.name)
    } else if (file.size > MAX_FILE_SIZE) {
      invalidFiles.push(`${file.name}(超过20MB)`)
    } else {
      validFiles.push(file)
    }
  })

  if (invalidFiles.length > 0) {
    errorMsg.value = `以下文件不支持或过大：${invalidFiles.join(', ')}`
  }

  if (validFiles.length === 0) return

  startUpload(validFiles)
}

// 开始上传
async function startUpload(files) {
  isUploading.value = true
  errorMsg.value = ''

  try {
    const result = await resumeApi.upload(files)
    batchId.value = result.batch_id
    batchJob.value = {
      batch_id: result.batch_id,
      total_files: result.total_files,
      status: 'processing',
      overall_progress: 0,
      success_count: 0,
      failed_count: 0,
      pending_count: result.total_files,
      tasks: []
    }

    // 开始轮询进度
    startPolling()
  } catch (e) {
    errorMsg.value = e.message || '上传失败'
    isUploading.value = false
  }
}

// 轮询进度
function startPolling() {
  if (pollTimer.value) clearInterval(pollTimer.value)
  pollTimer.value = setInterval(async () => {
    if (!batchId.value) return
    try {
      const job = await resumeApi.getBatchStatus(batchId.value)
      batchJob.value = job

      if (job.status !== 'processing') {
        stopPolling()
        isUploading.value = false
        emit('upload-complete', job)
      }
    } catch (e) {
      console.error('轮询进度失败:', e)
    }
  }, 1000)
}

function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

// 重试单个
async function retryTask(task) {
  if (!batchId.value) return
  try {
    await resumeApi.retryTask(batchId.value, task.task_id)
    // 重新获取状态
    const job = await resumeApi.getBatchStatus(batchId.value)
    batchJob.value = job
  } catch (e) {
    errorMsg.value = e.message || '重试失败'
  }
}

// 重试全部失败
async function retryAllFailed() {
  if (!batchId.value) return
  try {
    await resumeApi.retryAll(batchId.value)
    const job = await resumeApi.getBatchStatus(batchId.value)
    batchJob.value = job
  } catch (e) {
    errorMsg.value = e.message || '重试失败'
  }
}

// 重置（开始新的上传）
function reset() {
  stopPolling()
  batchId.value = null
  batchJob.value = null
  isUploading.value = false
  errorMsg.value = ''
}

// 状态标签
function statusText(status) {
  const map = {
    pending: '等待中',
    parsing: '解析中',
    success: '成功',
    failed: '失败'
  }
  return map[status] || status
}

function statusClass(status) {
  const map = {
    pending: 'status-pending',
    parsing: 'status-parsing',
    success: 'status-success',
    failed: 'status-failed'
  }
  return map[status] || ''
}

// 文件大小格式化
function formatSize(bytes) {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / (1024 * 1024)).toFixed(1) + 'MB'
}

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="batch-upload">
    <!-- 上传区域 -->
    <div
      class="upload-zone"
      :class="{ dragging: isDragging, disabled: isUploading }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
      @click="!isUploading && fileInput?.click()"
    >
      <input
        ref="fileInput"
        type="file"
        multiple
        :accept="ACCEPTED_TYPES"
        style="display:none"
        @change="handleFileSelect"
      />
      <div class="upload-icon">📄</div>
      <div class="upload-text">
        <strong>{{ isUploading ? '正在处理中...' : '点击或拖拽上传简历' }}</strong>
        <p>支持 PDF / Word / 图片 / 文本格式，单次最多100份，单文件不超过20MB</p>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

    <!-- 批量进度概览 -->
    <div v-if="batchJob" class="batch-overview">
      <div class="overview-header">
        <span class="batch-title">批量处理进度</span>
        <span class="batch-id">任务ID: {{ batchJob.batch_id }}</span>
        <button v-if="isCompleted" class="btn-reset" @click="reset">重新上传</button>
      </div>

      <!-- 总进度条 -->
      <div class="total-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: overallProgress + '%' }"></div>
        </div>
        <span class="progress-text">{{ overallProgress }}%</span>
      </div>

      <!-- 统计 -->
      <div class="stats-row">
        <span class="stat stat-total">总计: {{ batchJob.total_files }}</span>
        <span class="stat stat-success">成功: {{ successCount }}</span>
        <span class="stat stat-failed">失败: {{ failedCount }}</span>
        <span class="stat stat-pending">处理中: {{ pendingCount }}</span>
        <button
          v-if="failedCount > 0"
          class="btn-retry-all"
          @click="retryAllFailed"
        >
          重试全部失败
        </button>
      </div>
    </div>

    <!-- 文件队列列表 -->
    <div v-if="batchJob && batchJob.tasks.length > 0" class="file-list">
      <div
        v-for="task in batchJob.tasks"
        :key="task.task_id"
        class="file-item"
      >
        <div class="file-info">
          <span class="file-icon">📎</span>
          <span class="file-name">{{ task.file_name }}</span>
          <span class="file-size">{{ formatSize(task.file_size) }}</span>
        </div>

        <div class="file-status">
          <!-- 处理中：显示进度条 -->
          <template v-if="task.status === 'parsing' || task.status === 'pending'">
            <div class="mini-progress">
              <div class="mini-progress-fill" :style="{ width: task.progress + '%' }"></div>
            </div>
            <span class="status-label status-parsing">{{ statusText(task.status) }}</span>
          </template>

          <!-- 成功 -->
          <template v-else-if="task.status === 'success'">
            <span class="status-label status-success">✓ 成功</span>
            <span v-if="task.parse_method === 'ai'" class="method-tag method-ai">AI解析</span>
            <span v-else-if="task.parse_method === 'rule'" class="method-tag method-rule">规则解析</span>
            <span v-else-if="task.parse_method === 'duplicate'" class="method-tag method-dup">重复跳过</span>
          </template>

          <!-- 失败 -->
          <template v-else-if="task.status === 'failed'">
            <span class="status-label status-failed">✗ 失败</span>
            <span class="error-detail">{{ task.error }}</span>
            <button class="btn-retry" @click="retryTask(task)">重试</button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.batch-upload {
  width: 100%;
}

.upload-zone {
  border: 2px dashed #CBD5E1;
  border-radius: 12px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #F8FAFC;
}
.upload-zone:hover {
  border-color: #4F6EF7;
  background: #EFF4FF;
}
.upload-zone.dragging {
  border-color: #4F6EF7;
  background: #EFF4FF;
  transform: scale(1.01);
}
.upload-zone.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.upload-icon {
  font-size: 40px;
  margin-bottom: 12px;
}
.upload-text strong {
  font-size: 15px;
  color: #1E293B;
}
.upload-text p {
  font-size: 12px;
  color: #94A3B8;
  margin: 6px 0 0;
}

.error-msg {
  margin-top: 12px;
  padding: 10px 14px;
  background: #FEF2F2;
  color: #EF4444;
  border-radius: 8px;
  font-size: 13px;
}

.batch-overview {
  margin-top: 20px;
  padding: 16px;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
}
.overview-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.batch-title {
  font-weight: 600;
  font-size: 14px;
  color: #1E293B;
}
.batch-id {
  font-size: 12px;
  color: #94A3B8;
  font-family: monospace;
}
.btn-reset {
  margin-left: auto;
  padding: 4px 12px;
  font-size: 12px;
  background: #F1F5F9;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  cursor: pointer;
  color: #475569;
}
.btn-reset:hover {
  background: #E2E8F0;
}

.total-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.progress-bar {
  flex: 1;
  height: 8px;
  background: #E2E8F0;
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4F6EF7, #7C9AFF);
  border-radius: 4px;
  transition: width 0.3s;
}
.progress-text {
  font-size: 13px;
  font-weight: 600;
  color: #4F6EF7;
  min-width: 40px;
  text-align: right;
}

.stats-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.stat {
  font-size: 13px;
  color: #64748B;
}
.stat-total { color: #1E293B; font-weight: 500; }
.stat-success { color: #10B981; }
.stat-failed { color: #EF4444; }
.stat-pending { color: #F59E0B; }
.btn-retry-all {
  margin-left: auto;
  padding: 4px 12px;
  font-size: 12px;
  background: #FFF7ED;
  border: 1px solid #FED7AA;
  border-radius: 6px;
  cursor: pointer;
  color: #EA580C;
}
.btn-retry-all:hover {
  background: #FFEDD5;
}

.file-list {
  margin-top: 16px;
  max-height: 400px;
  overflow-y: auto;
}
.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  margin-bottom: 8px;
  background: #fff;
}
.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.file-icon { font-size: 16px; }
.file-name {
  font-size: 13px;
  color: #1E293B;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-size {
  font-size: 11px;
  color: #94A3B8;
  flex-shrink: 0;
}

.file-status {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.mini-progress {
  width: 60px;
  height: 4px;
  background: #E2E8F0;
  border-radius: 2px;
  overflow: hidden;
}
.mini-progress-fill {
  height: 100%;
  background: #4F6EF7;
  transition: width 0.3s;
}
.status-label {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
}
.status-pending { background: #F1F5F9; color: #64748B; }
.status-parsing { background: #EFF4FF; color: #4F6EF7; }
.status-success { background: #ECFDF5; color: #10B981; }
.status-failed { background: #FEF2F2; color: #EF4444; }

.method-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
}
.method-ai { background: #F0FDF4; color: #16A34A; }
.method-rule { background: #F0F9FF; color: #0284C7; }
.method-dup { background: #FFFBEB; color: #D97706; }

.error-detail {
  font-size: 11px;
  color: #94A3B8;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.btn-retry {
  padding: 2px 8px;
  font-size: 11px;
  background: #FFF7ED;
  border: 1px solid #FED7AA;
  border-radius: 4px;
  cursor: pointer;
  color: #EA580C;
}
.btn-retry:hover {
  background: #FFEDD5;
}
</style>
