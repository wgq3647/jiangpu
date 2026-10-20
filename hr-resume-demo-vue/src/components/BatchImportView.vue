<template>
  <div class="batch-import-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">批量导入</h2>
        <p class="page-desc">一键批量导入公司信息、岗位JD和Schema匹配规则，支持AI语义解析和规则解析两种模式</p>
      </div>
      <a :href="templateUrl" class="btn-download" download>
        <span class="download-icon">📥</span> 下载导入模板
      </a>
    </div>

    <!-- 模式切换 -->
    <div class="mode-switch-card">
      <div class="mode-label">解析模式</div>
      <div class="mode-options">
        <div class="mode-option" :class="{ active: importMode === 'rule' }" @click="importMode = 'rule'">
          <div class="mode-icon">📋</div>
          <div class="mode-info">
            <div class="mode-name">规则解析</div>
            <div class="mode-desc">按列名直接映射，速度快，Schema配置需标准JSON格式</div>
          </div>
        </div>
        <div class="mode-option" :class="{ active: importMode === 'ai' }" @click="importMode = 'ai'">
          <div class="mode-icon">🤖</div>
          <div class="mode-info">
            <div class="mode-name">AI语义解析</div>
            <div class="mode-desc">AI自动清洗数据，Schema配置为空时自动生成匹配规则</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 上传区域 -->
    <div class="upload-card">
      <div
        class="upload-area"
        :class="{ dragging: isDragging, uploading: uploading }"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
        @click="triggerFileInput"
      >
        <input ref="fileInput" type="file" accept=".xlsx,.xls,.csv" @change="handleFileSelect" style="display:none" />
        <div v-if="!uploading" class="upload-content">
          <div class="upload-icon">📁</div>
          <div class="upload-title">点击或拖拽文件到此处上传</div>
          <div class="upload-formats">支持 Excel(.xlsx) 和 CSV 格式</div>
          <div v-if="selectedFile" class="selected-file">
                            已选择：{{ selectedFile.name }}（{{ formatFileSize(selectedFile.size) }}）
          </div>
        </div>
        <div v-else class="uploading-content">
          <div class="upload-spinner"></div>
          <div class="uploading-title">正在导入...</div>
          <div class="uploading-desc">AI正在解析文件，请稍候</div>
        </div>
      </div>

      <div v-if="selectedFile && !uploading" class="upload-actions">
        <button class="btn-primary" @click="startUpload" :disabled="!selectedFile">
          开始导入
        </button>
        <button class="btn-secondary" @click="clearFile">
          清除
        </button>
      </div>
    </div>

    <!-- 导入结果 -->
    <div v-if="importResult" class="result-card">
      <div class="result-header">
        <h3 class="result-title">导入结果</h3>
        <div class="result-summary">
          <span class="summary-item total">总计 {{ importResult.total }}</span>
          <span class="summary-item success">成功 {{ importResult.success }}</span>
          <span class="summary-item failed">失败 {{ importResult.failed }}</span>
          <span class="summary-item mode">模式：{{ importResult.mode === 'ai' ? 'AI语义解析' : '规则解析' }}</span>
        </div>
      </div>

      <!-- 成功列表 -->
      <div v-if="importResult.success_items && importResult.success_items.length" class="result-section">
        <div class="section-title success-title">✓ 成功导入（{{ importResult.success_items.length }}）</div>
        <div class="result-table-wrap">
          <table class="result-table">
            <thead>
              <tr>
                <th style="width:60px">行号</th>
                <th>公司名称</th>
                <th>岗位名称</th>
                <th style="width:100px">公司状态</th>
                <th style="width:100px">Schema字段数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in importResult.success_items" :key="item.row">
                <td>{{ item.row }}</td>
                <td>{{ item.company }}</td>
                <td>{{ item.position }}</td>
                <td>
                  <span class="badge" :class="item.company_created ? 'badge-new' : 'badge-exist'">
                    {{ item.company_created ? '新建' : '已存在' }}
                  </span>
                </td>
                <td>{{ item.schema_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 失败列表 -->
      <div v-if="importResult.failed_items && importResult.failed_items.length" class="result-section">
        <div class="section-title fail-title">✗ 导入失败（{{ importResult.failed_items.length }}）</div>
        <div class="result-table-wrap">
          <table class="result-table">
            <thead>
              <tr>
                <th style="width:60px">行号</th>
                <th>公司名称</th>
                <th>岗位名称</th>
                <th>失败原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in importResult.failed_items" :key="item.row">
                <td>{{ item.row }}</td>
                <td>{{ item.company || '-' }}</td>
                <td>{{ item.position || '-' }}</td>
                <td class="fail-reason">{{ item.errors.join('；') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 使用说明 -->
    <div class="help-card">
      <h3 class="help-title">📖 使用说明</h3>
      <div class="help-content">
        <div class="help-step">
          <span class="step-num">1</span>
          <div class="step-content">
            <strong>下载模板</strong>：点击右上角「下载导入模板」，获取标准Excel模板
          </div>
        </div>
        <div class="help-step">
          <span class="step-num">2</span>
          <div class="step-content">
            <strong>填写数据</strong>：按照模板格式填写公司、岗位和Schema配置信息，公司名称和岗位名称为必填项
          </div>
        </div>
        <div class="help-step">
          <span class="step-num">3</span>
          <div class="step-content">
            <strong>选择模式</strong>：规则解析速度快，要求Schema配置为标准JSON；AI语义解析会自动清洗数据并生成Schema
          </div>
        </div>
        <div class="help-step">
          <span class="step-num">4</span>
          <div class="step-content">
            <strong>上传导入</strong>：选择文件后点击「开始导入」，系统会自动级联创建公司、岗位和Schema配置
          </div>
        </div>
      </div>
      <div class="help-tip">
        <strong>💡 提示：</strong>公司名称会自动去重，已存在的公司不会重复创建，只会在该公司下新增岗位。Schema字段配置为JSON数组格式，包含field_name、field_type、requirement、weight、is_hard等字段。
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'
import { batchImportApi } from '../api/index.js'

const showAlert = inject('showAlert')
const showConfirm = inject('showConfirm')

const importMode = ref('rule')
const selectedFile = ref(null)
const uploading = ref(false)
const isDragging = ref(false)
const importResult = ref(null)
const fileInput = ref(null)

const templateUrl = computed(() => batchImportApi.downloadTemplate())

function triggerFileInput() {
  if (uploading.value) return
  fileInput.value?.click()
}

function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) {
    selectedFile.value = file
  }
}

function handleDrop(e) {
  if (uploading.value) return
  const file = e.dataTransfer.files[0]
  if (file) {
    const ext = file.name.toLowerCase().split('.').pop()
    if (['xlsx', 'xls', 'csv'].includes(ext)) {
      selectedFile.value = file
    } else {
      showAlert('请上传 Excel(.xlsx) 或 CSV 文件', 'warning')
    }
  }
  isDragging.value = false
}

function clearFile() {
  selectedFile.value = null
  importResult.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function startUpload() {
  if (!selectedFile.value) {
    showAlert('请先选择文件', 'warning')
    return
  }
  uploading.value = true
  importResult.value = null
  try {
    const result = await batchImportApi.upload(selectedFile.value, importMode.value)
    importResult.value = result
  } catch (e) {
    showAlert('导入失败: ' + (e.message || e), 'error')
  } finally {
    uploading.value = false
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<style scoped>
.batch-import-page { padding: 24px; max-width: 1200px; margin: 0 auto; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-title { font-size: 24px; font-weight: 700; color: #1E293B; margin: 0 0 8px; }
.page-desc { font-size: 14px; color: #64748B; margin: 0; }

.btn-download {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 20px; background: #EEF2FF; color: #4F46E5;
  border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 600;
  border: 1px solid #C7D2FE; transition: all 0.2s;
}
.btn-download:hover { background: #E0E7FF; }
.download-icon { font-size: 16px; }

/* 模式切换 */
.mode-switch-card {
  background: #fff; border: 1px solid #E2E8F0; border-radius: 12px;
  padding: 20px; margin-bottom: 20px;
}
.mode-label { font-size: 14px; font-weight: 600; color: #475569; margin-bottom: 12px; }
.mode-options { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.mode-option {
  display: flex; gap: 12px; padding: 16px; border: 2px solid #E2E8F0;
  border-radius: 10px; cursor: pointer; transition: all 0.2s;
}
.mode-option:hover { border-color: #C7D2FE; }
.mode-option.active { border-color: #4F46E5; background: #EEF2FF; }
.mode-icon { font-size: 28px; flex-shrink: 0; }
.mode-name { font-size: 15px; font-weight: 700; color: #1E293B; margin-bottom: 4px; }
.mode-desc { font-size: 12px; color: #64748B; line-height: 1.5; }

/* 上传区域 */
.upload-card {
  background: #fff; border: 1px solid #E2E8F0; border-radius: 12px;
  padding: 24px; margin-bottom: 20px;
}
.upload-area {
  border: 2px dashed #CBD5E1; border-radius: 12px; padding: 48px 24px;
  text-align: center; cursor: pointer; transition: all 0.2s;
}
.upload-area:hover { border-color: #4F46E5; background: #F8FAFC; }
.upload-area.dragging { border-color: #4F46E5; background: #EEF2FF; }
.upload-area.uploading { cursor: default; }
.upload-icon { font-size: 48px; margin-bottom: 16px; }
.upload-title { font-size: 18px; font-weight: 600; color: #1E293B; margin-bottom: 8px; }
.upload-formats { font-size: 13px; color: #94A3B8; }
.selected-file {
  margin-top: 16px; padding: 10px 16px; background: #F0FDF4;
  border: 1px solid #BBF7D0; border-radius: 8px; font-size: 13px; color: #166534;
}
.upload-spinner {
  width: 48px; height: 48px; border: 4px solid #E2E8F0;
  border-top-color: #4F46E5; border-radius: 50%;
  animation: spin 0.8s linear infinite; margin: 0 auto 16px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.uploading-title { font-size: 18px; font-weight: 600; color: #1E293B; margin-bottom: 8px; }
.uploading-desc { font-size: 13px; color: #64748B; }

.upload-actions { display: flex; gap: 12px; justify-content: center; margin-top: 20px; }
.btn-primary {
  padding: 10px 32px; background: #4F46E5; color: #fff; border: none;
  border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s;
}
.btn-primary:hover { background: #4338CA; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  padding: 10px 32px; background: #F1F5F9; color: #475569; border: 1px solid #E2E8F0;
  border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s;
}
.btn-secondary:hover { background: #E2E8F0; }

/* 结果卡片 */
.result-card {
  background: #fff; border: 1px solid #E2E8F0; border-radius: 12px;
  padding: 24px; margin-bottom: 20px;
}
.result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.result-title { font-size: 18px; font-weight: 700; color: #1E293B; margin: 0; }
.result-summary { display: flex; gap: 12px; flex-wrap: wrap; }
.summary-item {
  padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600;
}
.summary-item.total { background: #F1F5F9; color: #475569; }
.summary-item.success { background: #D1FAE5; color: #065F46; }
.summary-item.failed { background: #FEE2E2; color: #991B1B; }
.summary-item.mode { background: #DBEAFE; color: #1E40AF; }

.result-section { margin-bottom: 24px; }
.section-title { font-size: 15px; font-weight: 700; margin-bottom: 12px; }
.success-title { color: #059669; }
.fail-title { color: #DC2626; }

.result-table-wrap { overflow-x: auto; border: 1px solid #E2E8F0; border-radius: 8px; }
.result-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.result-table th {
  background: #F8FAFC; padding: 10px 12px; text-align: left;
  font-weight: 600; color: #475569; border-bottom: 1px solid #E2E8F0; white-space: nowrap;
}
.result-table td { padding: 10px 12px; border-bottom: 1px solid #F1F5F9; color: #334155; }
.result-table tr:last-child td { border-bottom: none; }
.result-table tr:hover { background: #F8FAFC; }

.badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge-new { background: #DBEAFE; color: #1E40AF; }
.badge-exist { background: #F1F5F9; color: #64748B; }
.fail-reason { color: #DC2626; }

/* 使用说明 */
.help-card {
  background: #fff; border: 1px solid #E2E8F0; border-radius: 12px; padding: 24px;
}
.help-title { font-size: 18px; font-weight: 700; color: #1E293B; margin: 0 0 20px; }
.help-content { display: flex; flex-direction: column; gap: 16px; margin-bottom: 20px; }
.help-step { display: flex; gap: 12px; align-items: flex-start; }
.step-num {
  width: 28px; height: 28px; border-radius: 50%; background: #4F46E5; color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; flex-shrink: 0;
}
.step-content { font-size: 14px; color: #475569; line-height: 1.6; padding-top: 3px; }
.help-tip {
  padding: 16px; background: #FFFBEB; border: 1px solid #FDE68A;
  border-radius: 8px; font-size: 13px; color: #92400E; line-height: 1.6;
}
</style>
