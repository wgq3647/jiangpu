<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import BatchUpload from './BatchUpload.vue'
import { resumeApi, userApi, companyApi, positionApi } from '../api/index.js'
import { getStoredUser } from '../api/index.js'

const navigateTo = inject('navigateTo', () => {})
const showAlert = inject('showAlert')
const showConfirm = inject('showConfirm')

const matching = ref(false)
const matchResult = ref(null)
const matchError = ref('')

// 上传结果（不自动匹配，等待用户点击匹配）
const uploadResult = ref(null)
const showUploadResult = ref(false)

// 单份简历匹配结果
const singleMatchResult = ref(null)
const showSingleMatchResult = ref(false)
const singleMatching = ref(false)

// 批量匹配结果弹窗
const showBatchMatchModal = ref(false)

// 本次匹配的简历ID列表，用于跳转到匹配结果页面时筛选
const lastMatchedResumeIds = ref([])
// 本次上传成功的简历ID列表
const lastUploadedResumeIds = ref([])

// 上传结果弹窗
const showUploadModal = ref(false)

// 匹配模式：all=全量匹配，targeted=定向匹配
const matchMode = ref('all')
const matchCompanies = ref([])
const matchPositions = ref([])
const selectedMatchCompanyId = ref(null)
const selectedMatchPositionId = ref(null)

async function loadMatchCompanies() {
  try {
    matchCompanies.value = await companyApi.list()
  } catch (e) {
    console.error('加载公司列表失败:', e)
  }
}

async function onMatchCompanyChange() {
  matchPositions.value = []
  selectedMatchPositionId.value = null
  if (!selectedMatchCompanyId.value) return
  try {
    // 直接用API按公司和状态查询岗位
    matchPositions.value = await positionApi.list({ 
      company_id: selectedMatchCompanyId.value,
      status: '招聘中'
    })
  } catch (e) {
    console.error('加载岗位列表失败:', e)
  }
}

// 错误提示弹窗
const showErrorModal = ref(false)
const errorModalMsg = ref('')

const resumeList = ref([])
const loadingResumes = ref(false)
const currentUser = getStoredUser()
const canReassign = computed(() => currentUser?.role === 'super_admin' || currentUser?.role === 'maintainer')
const canSetAdvancedStatus = computed(() => currentUser?.role === 'super_admin' || currentUser?.role === 'maintainer')

// 分配简历
const recruiters = ref([])
const showReassignModal = ref(false)
const reassignTarget = ref(null)

// 批量选择与批量分配
const selectedResumeIds = ref([])
const editingStatusId = ref(null)  // 当前正在编辑业务状态的简历ID
const showBatchReassignModal = ref(false)

const allSelected = computed(() => {
  if (pagedResumes.value.length === 0) return false
  return pagedResumes.value.every(r => selectedResumeIds.value.includes(r.id))
})

function toggleSelectAll() {
  if (allSelected.value) {
    // 取消当前页全选
    const pageIds = pagedResumes.value.map(r => r.id)
    selectedResumeIds.value = selectedResumeIds.value.filter(id => !pageIds.includes(id))
  } else {
    // 选中当前页
    const pageIds = pagedResumes.value.map(r => r.id)
    for (const id of pageIds) {
      if (!selectedResumeIds.value.includes(id)) {
        selectedResumeIds.value.push(id)
      }
    }
  }
}

function toggleSelectOne(id) {
  const idx = selectedResumeIds.value.indexOf(id)
  if (idx > -1) {
    selectedResumeIds.value.splice(idx, 1)
  } else {
    selectedResumeIds.value.push(id)
  }
}

function clearSelection() {
  selectedResumeIds.value = []
}

function openBatchReassign() {
  if (selectedResumeIds.value.length === 0) return
  showBatchReassignModal.value = true
}

async function confirmBatchReassign(ownerId) {
  try {
    const result = await resumeApi.batchReassign(selectedResumeIds.value, ownerId)
    showAlert(result.message || '批量分配成功', 'success')
    showBatchReassignModal.value = false
    clearSelection()
    await loadResumes()
  } catch (e) {
    showAlert('批量分配失败: ' + (e.message || e), 'error')
  }
}

async function loadRecruiters() {
  try {
    recruiters.value = await userApi.recruiters()
  } catch (e) {
    console.error('加载招聘人员列表失败:', e)
  }
}

function openReassign(resume) {
  reassignTarget.value = resume
  showReassignModal.value = true
}

async function confirmReassign(ownerId) {
  if (!reassignTarget.value) return
  try {
    await resumeApi.reassignOwner(reassignTarget.value.id, ownerId)
    const target = recruiters.value.find(u => u.id === ownerId)
    showAlert('已将「' + reassignTarget.value.file_name + '」分配给 ' + (target?.name || target?.phone), 'success', '分配成功')
    showReassignModal.value = false
    reassignTarget.value = null
    await loadResumes()
  } catch (e) {
    showAlert('分配失败: ' + (e.message || e), 'error')
  }
}

// 搜索与分页
const searchName = ref('')
const currentPage = ref(1)
const pageSize = 10

// 按候选人名字/文件名模糊过滤
const filteredResumes = computed(() => {
  if (!searchName.value.trim()) return resumeList.value
  const kw = searchName.value.trim().toLowerCase()
  return resumeList.value.filter(r =>
    (r.candidate_name && r.candidate_name.toLowerCase().includes(kw)) ||
    (r.file_name && r.file_name.toLowerCase().includes(kw))
  )
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredResumes.value.length / pageSize)))
const pagedResumes = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredResumes.value.slice(start, start + pageSize)
})

function goPage(p) {
  if (p < 1 || p > totalPages.value) return
  currentPage.value = p
}
function onSearchInput() {
  currentPage.value = 1
}

async function loadResumes() {
  loadingResumes.value = true
  try {
    resumeList.value = await resumeApi.list()
  } catch (e) {
    console.error('加载简历列表失败:', e)
  } finally {
    loadingResumes.value = false
  }
}

async function onUploadComplete(batchJob) {
  await loadResumes()
  if (!batchJob || (!batchJob.success_count && !batchJob.failed_count)) {
    errorModalMsg.value = '没有成功解析的简历'
    showErrorModal.value = true
    return
  }
  // 从batchJob中提取本次上传成功的简历ID，并区分有效/无效
  lastUploadedResumeIds.value = []
  let invalidCount = 0
  const invalidReasons = []
  if (batchJob.tasks && batchJob.tasks.length > 0) {
    for (const task of batchJob.tasks) {
      if (task.status === 'success' && task.resume_id) {
        // 检查是否为无效简历（error字段包含"非简历"或"无效"）
        if (task.error && (task.error.includes('非简历') || task.error.includes('无效'))) {
          invalidCount++
          if (task.error.length > 50) {
            invalidReasons.push(task.error.substring(0, 50) + '...')
          } else {
            invalidReasons.push(task.error)
          }
        } else {
          lastUploadedResumeIds.value.push(task.resume_id)
        }
      }
    }
  }
  // 不自动匹配，显示上传结果弹窗，等待用户点击匹配
  const validCount = batchJob.success_count - invalidCount
  uploadResult.value = {
    total: batchJob.total_files || batchJob.success_count + (batchJob.failed_count || 0),
    success: validCount,
    invalid: invalidCount,
    failed: batchJob.failed_count || 0,
    invalidReasons: invalidReasons
  }
  // 重置匹配模式为全量匹配
  matchMode.value = 'all'
  selectedMatchCompanyId.value = null
  selectedMatchPositionId.value = null
  matchPositions.value = []
  showUploadModal.value = true
  matchResult.value = null
  matchError.value = ''
}

// 对刚上传的简历执行匹配
async function matchUploadedResumes() {
  // 定向匹配时校验
  if (matchMode.value === 'targeted') {
    if (!selectedMatchCompanyId.value) {
      errorModalMsg.value = '请选择公司'
      showErrorModal.value = true
      return
    }
    if (!selectedMatchPositionId.value) {
      errorModalMsg.value = '请选择岗位'
      showErrorModal.value = true
      return
    }
  }
  matching.value = true
  matchError.value = ''
  matchResult.value = null
  lastMatchedResumeIds.value = [...lastUploadedResumeIds.value]
  try {
    const resumeListAll = await resumeApi.list()
    // 只匹配本次上传的简历（ID统一转字符串比较，避免类型不匹配）
    // 不强制检查status，因为刚上传的简历可能状态还没更新
    const uploadedIdSet = new Set(lastUploadedResumeIds.value.map(id => String(id)))
    const parsedResumes = resumeListAll.filter(r => uploadedIdSet.has(String(r.id)))
    let successCount = 0
    let failCount = 0
    let totalMatchedPositions = 0
    let totalPassedHard = 0
    const failedDetails = []
    for (const resume of parsedResumes) {
      try {
        let result
        if (matchMode.value === 'targeted' && selectedMatchPositionId.value) {
          // 定向匹配单个岗位
          const singleResult = await resumeApi.matchPosition(resume.id, selectedMatchPositionId.value)
          // 统一格式：定向匹配只匹配1个岗位
          result = {
            total_positions: 1,
            matched_positions: singleResult.passed_hard ? 1 : 0,
            results: [singleResult]
          }
        } else {
          // 全量匹配所有岗位
          result = await resumeApi.matchAll(resume.id)
        }
        successCount++
        totalMatchedPositions += result.total_positions || 0
        totalPassedHard += result.matched_positions || 0
      } catch (e) {
        failCount++
        const errMsg = e && e.message ? e.message : String(e)
        failedDetails.push({
          name: resume.candidate_name || resume.file_name || ('简历#' + resume.id),
          reason: errMsg
        })
        console.error('单份简历匹配失败:', resume.id, resume.candidate_name, errMsg)
      }
    }
    matchResult.value = {
      total: parsedResumes.length,
      success: successCount,
      failed: failCount,
      totalPositions: totalMatchedPositions,
      passedHard: totalPassedHard,
      mode: matchMode.value,
      failedDetails: failedDetails
    }
    showUploadResult.value = false
    showBatchMatchModal.value = true
  } catch (e) {
    console.error('匹配整体失败:', e)
    const errMsg = e && e.message ? e.message : String(e)
    errorModalMsg.value = '匹配失败: ' + errMsg + ' | 本次上传简历数: ' + (lastUploadedResumeIds.value?.length || 0) + ' | 匹配模式: ' + matchMode.value
    showErrorModal.value = true
  } finally {
    matching.value = false
    try { await loadResumes() } catch (e) { console.error('刷新简历列表失败:', e) }
  }
}

// 跳转到匹配结果页面
function goToMatchResults(resumeIds = null) {
  const ids = resumeIds || lastMatchedResumeIds.value
  navigateTo && navigateTo('查看匹配结果', { resume_ids: ids.length > 0 ? ids : null })
}

async function matchSingleResume(resume) {
  singleMatching.value = true
  singleMatchResult.value = null
  try {
    const result = await resumeApi.matchAll(resume.id)
    singleMatchResult.value = {
      resume: resume,
      totalPositions: result.total_positions,
      matchedPositions: result.matched_positions,
      results: result.results
    }
    showSingleMatchResult.value = true
    await loadResumes()
  } catch (e) {
    showAlert('匹配失败: ' + e.message, 'error')
  } finally {
    singleMatching.value = false
  }
}

function closeSingleMatchResult() {
  showSingleMatchResult.value = false
  singleMatchResult.value = null
}

// 业务状态样式
function getBizStatusClass(status) {
  const map = {
    '有效': 'biz-valid',
    '投递中': 'biz-submitted',
    '已面试通过': 'biz-passed',
    '无效': 'biz-invalid'
  }
  return map[status] || 'biz-valid'
}

// 开始编辑状态
function startEditStatus(resume) {
  editingStatusId.value = resume.id
}

// 内联变更业务状态
async function changeStatusInline(resume, newStatus) {
  editingStatusId.value = null
  if (newStatus === resume.business_status) return
  try {
    await resumeApi.updateStatus(resume.id, newStatus)
    resume.business_status = newStatus
    if (newStatus === '有效') resume.routing_paused = false
  } catch (e) {
    showAlert('状态变更失败：' + (e.message || e), 'error')
    loadData()
  }
}

// 变更业务状态
async function changeStatus(resume, newStatus) {
  if (newStatus === resume.business_status) return
  try {
    await resumeApi.updateStatus(resume.id, newStatus)
    resume.business_status = newStatus
    if (newStatus === '有效') resume.routing_paused = false
    showAlert('状态已变更为「' + newStatus + '」', 'success')
  } catch (e) {
    showAlert('状态变更失败：' + (e.message || e), 'error')
    loadData()
  }
}

// 切换路由开关
async function toggleRouting(resume) {
  const newPaused = !resume.routing_paused
  try {
    await resumeApi.toggleRouting(resume.id, newPaused)
    resume.routing_paused = newPaused
  } catch (e) {
    showAlert('路由切换失败：' + (e.message || e), 'error')
  }
}

async function deleteResume(resume) {
  const confirmed = await showConfirm('确定要删除简历「' + resume.file_name + '」吗？相关的匹配结果也会一并删除，此操作不可恢复。', '删除确认', 'warning')
  if (!confirmed) return
  try {
    await resumeApi.delete(resume.id)
    resumeList.value = resumeList.value.filter(r => r.id !== resume.id)
  } catch (e) {
    showAlert('删除失败: ' + e.message, 'error')
  }
}

async function deleteAllResumes() {
  if (resumeList.value.length === 0) {
    showAlert('没有可删除的简历', 'warning')
    return
  }
  const confirmed = await showConfirm('确定要删除全部 ' + resumeList.value.length + ' 份简历吗？相关的匹配结果也会一并删除，此操作不可恢复！', '全部删除确认', 'warning')
  if (!confirmed) return
  try {
    let successCount = 0
    let failCount = 0
    for (const resume of resumeList.value) {
      try {
        await resumeApi.delete(resume.id)
        successCount++
      } catch (e) {
        failCount++
      }
    }
    resumeList.value = []
    showAlert('全部删除完成！成功删除 ' + successCount + ' 份' + (failCount > 0 ? '，失败 ' + failCount + ' 份' : ''), 'success', '删除完成')
  } catch (e) {
    showAlert('删除失败: ' + e.message, 'error')
  }
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatType(type) {
  const map = {
    'pdf': { text: 'PDF', class: 'type-pdf' },
    'word': { text: 'Word', class: 'type-word' },
    'text': { text: '文本', class: 'type-text' },
    'image': { text: '图片', class: 'type-image' },
  }
  return map[type] || { text: type || '未知', class: 'type-unknown' }
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  const d = new Date(timeStr)
  const pad = n => String(n).padStart(2, '0')
  return d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes())
}

// 生成匹配岗位悬浮提示
function getMatchTooltip(resume) {
  const positions = resume.matched_positions || []
  if (positions.length === 0) return '已匹配 ' + resume.matched_count + ' 个岗位'
  const showCount = Math.min(positions.length, 8)
  let tip = '已匹配 ' + resume.matched_count + ' 个岗位：\n'
  for (let i = 0; i < showCount; i++) {
    const p = positions[i]
    tip += (i + 1) + '. ' + p.name + '（' + p.score + '分' + (p.passed_hard ? '，满足硬性条件' : '') + '）\n'
  }
  if (positions.length > showCount) {
    tip += '...等' + positions.length + '个岗位'
  }
  return tip
}

onMounted(() => {
  loadResumes()
  loadMatchCompanies()
  if (canReassign.value) loadRecruiters()
})
</script>

<template>
  <div class="resume-filter-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">上传简历和匹配</h2>
        <p class="page-desc">批量上传简历，AI自动解析并匹配岗位要求</p>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="step-num">1</span>
        <span class="card-title">批量导入简历</span>
        <span class="card-subtitle">支持 Word / 文本，单次最多100份</span>
      </div>
      <div class="card-body">
        <BatchUpload @upload-complete="onUploadComplete" />
      </div>
    </div>

    <div v-if="matching" class="card match-status-card">
      <div class="match-status-content">
        <div class="match-spinner"></div>
        <div>
          <div class="match-status-title">正在执行匹配...</div>
          <div class="match-status-desc">对已解析简历匹配全部在招岗位，请稍候</div>
        </div>
      </div>
    </div>

    <!-- 上传结果弹窗 -->
    <div v-if="showUploadModal && uploadResult" class="upload-modal" @click.self="showUploadModal = false">
      <div class="upload-modal-content">
        <div class="upload-modal-header">
          <div class="upload-modal-icon">&#128228;</div>
          <h3>上传完成！</h3>
          <button class="upload-modal-close" @click="showUploadModal = false">✕</button>
        </div>
        <div class="upload-modal-body">
          <div class="upload-modal-stats">
            <div class="upload-stat-card">
              <div class="upload-stat-num">{{ uploadResult.total }}</div>
              <div class="upload-stat-label">共上传</div>
            </div>
            <div class="upload-stat-card success" v-if="uploadResult.success > 0">
              <div class="upload-stat-num">{{ uploadResult.success }}</div>
              <div class="upload-stat-label">有效简历</div>
            </div>
            <div class="upload-stat-card warning" v-if="uploadResult.invalid > 0">
              <div class="upload-stat-num">{{ uploadResult.invalid }}</div>
              <div class="upload-stat-label">非简历文件</div>
            </div>
            <div class="upload-stat-card" v-if="uploadResult.failed > 0">
              <div class="upload-stat-num fail">{{ uploadResult.failed }}</div>
              <div class="upload-stat-label">解析失败</div>
            </div>
          </div>
          <!-- 无效简历原因提示 -->
          <div v-if="uploadResult.invalid > 0" class="upload-invalid-tip">
            <div class="upload-invalid-title">⚠️ 已识别 {{ uploadResult.invalid }} 个非简历文件，已标记为无效，不参与匹配</div>
            <div v-for="(reason, idx) in uploadResult.invalidReasons" :key="idx" class="upload-invalid-reason">{{ reason }}</div>
          </div>
          <div class="upload-modal-tip" v-if="uploadResult.success > 0">
            共 {{ uploadResult.success }} 份有效简历已解析完成，请选择匹配方式：
          </div>
          <div class="upload-modal-tip" v-else>
            没有可用于匹配的有效简历
          </div>
          <!-- 匹配模式选择 -->
          <div v-if="uploadResult.success > 0" class="match-mode-selector">
            <div class="match-mode-options">
              <label class="match-mode-option" :class="{ active: matchMode === 'all' }">
                <input type="radio" v-model="matchMode" value="all" />
                <span class="mode-icon">&#127760;</span>
                <span class="mode-text">
                  <strong>全量匹配</strong>
                  <small>匹配所有公司的所有在招岗位</small>
                </span>
              </label>
              <label class="match-mode-option" :class="{ active: matchMode === 'targeted' }">
                <input type="radio" v-model="matchMode" value="targeted" />
                <span class="mode-icon">&#127919;</span>
                <span class="mode-text">
                  <strong>定向匹配</strong>
                  <small>只匹配指定公司的指定岗位</small>
                </span>
              </label>
            </div>
            <!-- 定向匹配：公司和岗位选择 -->
            <div v-if="matchMode === 'targeted'" class="targeted-match-fields">
              <div class="form-row">
                <label class="form-label">选择公司</label>
                <select v-model="selectedMatchCompanyId" @change="onMatchCompanyChange" class="form-select">
                  <option value="">请选择公司</option>
                  <option v-for="c in matchCompanies" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </div>
              <div class="form-row">
                <label class="form-label">选择岗位</label>
                <select v-model="selectedMatchPositionId" :disabled="!selectedMatchCompanyId" class="form-select">
                  <option value="">请选择岗位</option>
                  <option v-for="p in matchPositions" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
              </div>
            </div>
          </div>
        </div>
        <div class="upload-modal-footer">
          <button v-if="uploadResult.success > 0" class="btn-match-now" @click="showUploadModal = false; matchUploadedResumes()">立即匹配</button>
          <button class="btn-match-later" @click="showUploadModal = false">{{ uploadResult.success > 0 ? '稍后匹配' : '我知道了' }}</button>
        </div>
      </div>
    </div>

    <!-- 错误提示弹窗 -->
    <div v-if="showErrorModal" class="error-modal" @click.self="showErrorModal = false">
      <div class="error-modal-content">
        <div class="error-modal-header">
          <div class="error-modal-icon">&#10007;</div>
          <h3>操作提示</h3>
          <button class="error-modal-close" @click="showErrorModal = false">✕</button>
        </div>
        <div class="error-modal-body">
          <p>{{ errorModalMsg }}</p>
        </div>
        <div class="error-modal-footer">
          <button class="btn-match-now" @click="showErrorModal = false">我知道了</button>
        </div>
      </div>
    </div>

    <!-- 批量匹配结果弹窗 -->
    <div v-if="showBatchMatchModal && matchResult" class="batch-match-modal" @click.self="showBatchMatchModal = false">
      <div class="batch-match-content">
        <div class="batch-match-header">
          <div class="batch-match-icon">&#10003;</div>
          <h3>匹配完成！</h3>
          <button class="batch-match-close" @click="showBatchMatchModal = false">✕</button>
        </div>
        <div class="batch-match-body">
          <div class="batch-match-stats">
            <div class="batch-stat-card">
              <div class="batch-stat-num">{{ matchResult.total }}</div>
              <div class="batch-stat-label">处理简历</div>
            </div>
            <div class="batch-stat-card">
              <div class="batch-stat-num">{{ matchResult.totalPositions }}</div>
              <div class="batch-stat-label">匹配岗位</div>
            </div>
            <div class="batch-stat-card success">
              <div class="batch-stat-num">{{ matchResult.passedHard }}</div>
              <div class="batch-stat-label">满足硬性条件</div>
            </div>
          </div>
          <div v-if="matchResult.failed > 0" class="batch-match-failed">
            <div class="batch-failed-title">其中 {{ matchResult.failed }} 份简历匹配失败：</div>
            <div class="batch-failed-list">
              <div v-for="(item, idx) in matchResult.failedDetails" :key="idx" class="batch-failed-item">
                <span class="batch-failed-name">{{ item.name }}</span>
                <span class="batch-failed-reason">{{ item.reason }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="batch-match-footer">
          <button class="btn-view-results" @click="showBatchMatchModal = false; goToMatchResults()">查看匹配结果 →</button>
          <button class="btn-close-modal" @click="showBatchMatchModal = false">关闭</button>
        </div>
      </div>
    </div>

    <div class="card resume-list-card">
      <div class="card-header">
        <span class="step-num">2</span>
        <span class="card-title">简历库</span>
        <span class="card-subtitle">已上传 {{ resumeList.length }} 份简历</span>
        <button class="btn-refresh-list" @click="loadResumes" :disabled="loadingResumes">
          {{ loadingResumes ? '加载中...' : '刷新' }}
        </button>
        <button class="btn-delete-all-resumes" @click="deleteAllResumes" :disabled="loadingResumes || resumeList.length === 0">
          全部删除
        </button>
      </div>
      <div class="card-body" style="padding: 0;">
        <div v-if="loadingResumes" class="list-loading">
          <div class="loading-spinner"></div>
          <span>加载中...</span>
        </div>
        <div v-else-if="resumeList.length === 0" class="list-empty">
          <div class="empty-icon">&#128196;</div>
          <div class="empty-text">暂无简历</div>
          <div class="empty-hint">请在上方上传简历文件</div>
        </div>
        <template v-else>
          <!-- 搜索栏 -->
          <div class="resume-search-bar">
            <div class="search-input-wrap">
              <span class="search-icon">&#128269;</span>
              <input v-model="searchName" type="text" class="search-input" placeholder="搜索候选人姓名或文件名..." @input="onSearchInput" />
            </div>
            <span class="search-count">共 {{ filteredResumes.length }} 份简历</span>
          </div>
          <!-- 批量操作栏 -->
          <div v-if="canReassign && selectedResumeIds.length > 0" class="batch-action-bar">
            <span class="batch-selected-info">已选中 <strong>{{ selectedResumeIds.length }}</strong> 份简历</span>
            <button class="btn-batch-reassign" @click="openBatchReassign">批量分配</button>
            <button class="btn-clear-selection" @click="clearSelection">取消选择</button>
          </div>
          <!-- 搜索无结果 -->
          <div v-if="filteredResumes.length === 0" class="list-empty" style="padding: 32px 20px;">
            <div class="empty-icon">&#128269;</div>
            <div class="empty-text">未找到匹配的简历</div>
            <div class="empty-hint">试试其他关键词，或清空搜索条件</div>
          </div>
          <div v-else class="resume-table-wrap">
          <table class="resume-table">
            <thead>
              <tr>
                <th style="width:40px">
                  <input type="checkbox" :checked="allSelected" @change="toggleSelectAll" class="checkbox" />
                </th>
                <th style="width:50px">序号</th>
                <th>文件名</th>
                <th style="width:90px">候选人</th>
                <th style="width:80px">大小</th>
                <th style="width:70px">格式</th>
                <th style="width:70px">解析状态</th>
                <th style="width:70px">解析方式</th>
                <th style="width:90px">业务状态</th>
                <th style="width:140px">上传时间</th>
                <th style="width:200px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(resume, idx) in pagedResumes" :key="resume.id" class="resume-row" :class="{ 'row-selected': selectedResumeIds.includes(resume.id) }">
                <td>
                  <input type="checkbox" :checked="selectedResumeIds.includes(resume.id)" @change="toggleSelectOne(resume.id)" class="checkbox" />
                </td>
                <td class="cell-index">{{ (currentPage - 1) * pageSize + idx + 1 }}</td>
                <td class="cell-filename">
                  <span class="filename-text" :title="resume.file_name">{{ resume.file_name }}</span>
                </td>
                <td class="cell-candidate">
                  <div style="display:flex; align-items:center; gap:4px;">
                    <span v-if="resume.candidate_name" class="candidate-name">{{ resume.candidate_name }}</span>
                    <span v-else class="candidate-empty">-</span>
                    <span v-if="resume.duplicate_of_id" class="dup-tag" :title="'与 ' + (resume.duplicate_of_owner || '他人') + ' 上传的简历内容重复'">重复</span>
                  </div>
                </td>
                <td class="cell-size">{{ formatSize(resume.file_size) }}</td>
                <td class="cell-type">
                  <span class="type-tag" :class="formatType(resume.file_type).class">
                    {{ formatType(resume.file_type).text }}
                  </span>
                </td>
                <td class="cell-status">
                  <span v-if="resume.status === '已解析'" class="status-tag status-success">已解析</span>
                  <span v-else-if="resume.status === '解析失败'" class="status-tag status-failed">解析失败</span>
                  <span v-else class="status-tag status-pending">{{ resume.status }}</span>
                </td>
                <td class="cell-method">
                  <span v-if="resume.parse_method === 'ai'" class="method-tag method-ai">AI</span>
                  <span v-else-if="resume.parse_method === 'rule'" class="method-tag method-rule">规则</span>
                  <span v-else class="method-tag method-unknown">-</span>
                </td>
                <td class="cell-business-status">
                  <div v-if="editingStatusId === resume.id" class="status-edit-wrap">
                    <select class="status-select-inline" :value="resume.business_status || '有效'" @change="changeStatusInline(resume, $event.target.value)" @blur="editingStatusId = null" ref="statusSelect">
                      <option value="有效">有效</option>
                      <option value="投递中">投递中</option>
                      <option value="已面试通过" :disabled="!canSetAdvancedStatus">已面试通过</option>
                      <option value="无效" :disabled="!canSetAdvancedStatus">无效</option>
                    </select>
                  </div>
                  <span v-else class="biz-status-tag" :class="getBizStatusClass(resume.business_status)" @click="startEditStatus(resume)" title="点击修改状态">
                    {{ resume.business_status || '有效' }}
                    <span v-if="resume.business_status === '投递中' && resume.routing_paused" class="routing-paused-dot" title="路由已暂停">⏸</span>
                  </span>
                  <button v-if="resume.business_status === '投递中'" class="btn-routing-inline" :class="{ paused: resume.routing_paused }" @click="toggleRouting(resume)" :title="resume.routing_paused ? '点击恢复路由' : '点击暂停路由'">
                    {{ resume.routing_paused ? '⏸' : '▶' }}
                  </button>
                </td>
                <td class="cell-time">{{ formatTime(resume.created_at) }}</td>
                <td class="cell-action">
                  <div class="action-row">
                    <template v-if="resume.business_status !== '已面试通过' && resume.status === '已解析'">
                      <button class="btn-action btn-match" @click="matchSingleResume(resume)" :disabled="singleMatching">
                        {{ resume.matched_count > 0 ? '重新匹配' : '匹配' }}
                      </button>
                      <span v-if="resume.matched_count > 0" class="matched-count-tag" :title="getMatchTooltip(resume)">
                        {{ resume.matched_count }}岗
                      </span>
                    </template>
                    <button v-if="canReassign" class="btn-action btn-reassign" @click="openReassign(resume)">分配</button>
                    <button class="btn-action btn-delete" @click="deleteResume(resume)">删除</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <!-- 分页 -->
          <div class="pagination" v-if="filteredResumes.length > pageSize">
            <button class="page-btn" :disabled="currentPage === 1" @click="goPage(currentPage - 1)">上一页</button>
            <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页（共 {{ filteredResumes.length }} 条）</span>
            <button class="page-btn" :disabled="currentPage === totalPages" @click="goPage(currentPage + 1)">下一页</button>
          </div>
          </div>
        </template>
      </div>
    </div>
    <!-- 单份简历匹配结果弹窗 -->
    <div v-if="showSingleMatchResult && singleMatchResult" class="single-match-modal" @click.self="closeSingleMatchResult">
      <div class="single-match-content">
        <div class="single-match-header">
          <h3>匹配结果 - {{ singleMatchResult.resume.candidate_name || singleMatchResult.resume.file_name }}</h3>
          <button class="single-match-close" @click="closeSingleMatchResult">✕</button>
        </div>
        <div class="single-match-body">
          <div class="single-match-stats">
            <div class="single-stat-card">
              <div class="single-stat-num">{{ singleMatchResult.totalPositions }}</div>
              <div class="single-stat-label">匹配岗位数</div>
            </div>
            <div class="single-stat-card success">
              <div class="single-stat-num">{{ singleMatchResult.matchedPositions }}</div>
              <div class="single-stat-label">满足硬性条件</div>
            </div>
            <div class="single-stat-card">
              <div class="single-stat-num">{{ singleMatchResult.results?.[0]?.total_score || '-' }}</div>
              <div class="single-stat-label">最高匹配分</div>
            </div>
          </div>
          <div class="single-match-list-title">匹配详情（按分数排序）</div>
          <div class="single-match-list">
            <div v-for="(item, idx) in singleMatchResult.results" :key="idx" class="single-match-item" :class="{ 'passed': item.passed_hard }">
              <div class="match-item-rank">{{ idx + 1 }}</div>
              <div class="match-item-info">
                <div class="match-item-position">{{ item.company_name }} - {{ item.position_name }}</div>
                <div class="match-item-highlight" v-if="item.match_highlights">{{ item.match_highlights }}</div>
              </div>
              <div class="match-item-score">
                <div class="score-num">{{ item.total_score }}</div>
                <div class="score-label">匹配分</div>
              </div>
              <div class="match-item-status">
                <span v-if="item.passed_hard" class="hard-pass-tag">满足硬性条件</span>
                <span v-else class="hard-fail-tag">不满足硬性条件</span>
              </div>
            </div>
          </div>
        </div>
        <div class="single-match-footer">
          <button class="btn-view-results" @click="closeSingleMatchResult(); goToMatchResults([singleMatchResult.resume.id])">前往匹配结果页面 →</button>
        </div>
      </div>
    </div>

    <!-- 分配简历弹窗 -->
    <div v-if="showReassignModal" class="reassign-modal" @click.self="showReassignModal = false">
      <div class="reassign-content">
        <div class="reassign-header">
          <h3>分配简历归属</h3>
          <button class="reassign-close" @click="showReassignModal = false">✕</button>
        </div>
        <div class="reassign-body">
          <p class="reassign-desc">将「<strong>{{ reassignTarget?.file_name }}</strong>」分配给以下招聘人员：</p>
          <p v-if="reassignTarget?.owner_name" class="reassign-current">当前归属：{{ reassignTarget.owner_name }}</p>
          <div class="recruiter-list">
            <div
              v-for="r in recruiters"
              :key="r.id"
              class="recruiter-item"
              :class="{ active: reassignTarget?.owner_id === r.id }"
              @click="confirmReassign(r.id)"
            >
              <span class="recruiter-name">{{ r.name || r.phone }}</span>
              <span class="recruiter-phone">{{ r.phone }}</span>
              <span v-if="reassignTarget?.owner_id === r.id" class="recruiter-current-tag">当前</span>
            </div>
            <div v-if="recruiters.length === 0" class="recruiter-empty">暂无可用的招聘人员账号</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 批量分配弹窗 -->
    <div v-if="showBatchReassignModal" class="reassign-modal" @click.self="showBatchReassignModal = false">
      <div class="reassign-content">
        <div class="reassign-header">
          <h3>批量分配简历</h3>
          <button class="reassign-close" @click="showBatchReassignModal = false">✕</button>
        </div>
        <div class="reassign-body">
          <p class="reassign-desc">将选中的 <strong>{{ selectedResumeIds.length }}</strong> 份简历分配给以下招聘人员：</p>
          <div class="recruiter-list">
            <div
              v-for="r in recruiters"
              :key="r.id"
              class="recruiter-item"
              @click="confirmBatchReassign(r.id)"
            >
              <span class="recruiter-name">{{ r.name || r.phone }}</span>
              <span class="recruiter-phone">{{ r.phone }}</span>
            </div>
            <div v-if="recruiters.length === 0" class="recruiter-empty">暂无可用的招聘人员账号</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.resume-filter-page { display: flex; flex-direction: column; gap: 20px; width: 100%; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; }
.page-title { font-size: 20px; font-weight: 700; color: #1E293B; margin: 0; }
.page-desc { font-size: 13px; color: #64748B; margin-top: 4px; }

/* 上传结果卡片 */
.upload-result-card { padding: 16px 20px; border-left: 4px solid #4F6EF7; }
.upload-result-content { display: flex; align-items: center; gap: 14px; }
.upload-icon { font-size: 28px; flex-shrink: 0; }
.upload-result-info { flex: 1; }
.upload-result-title { font-size: 14px; font-weight: 600; color: #1E293B; }
.upload-result-desc { font-size: 13px; color: #64748B; margin-top: 2px; }
.upload-result-actions { display: flex; gap: 8px; flex-shrink: 0; }
.btn-match-now { padding: 8px 18px; background: linear-gradient(135deg, #4F6EF7 0%, #6366F1 100%); color: #fff; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }
.btn-match-now:hover { opacity: 0.9; }
.btn-match-later { padding: 8px 16px; background: #fff; color: #64748B; border: 1px solid #CBD5E1; border-radius: 8px; font-size: 13px; cursor: pointer; }
.btn-match-later:hover { background: #F8FAFC; }

/* 匹配结果统计 */
.match-result-info { flex: 1; }
.match-result-stats { display: flex; gap: 20px; margin-top: 6px; }
.stat-item { font-size: 13px; color: #64748B; }
.stat-item b { color: #1E293B; font-size: 15px; }
.btn-view-results { padding: 8px 16px; background: #EEF1FE; color: #4F6EF7; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; flex-shrink: 0; }
.btn-view-results:hover { background: #E0E6FD; }

/* 匹配数量标签 */
.matched-count-tag { display: inline-block; padding: 2px 6px; background: #ECFDF5; color: #10B981; border-radius: 4px; font-size: 11px; font-weight: 600; }

/* 上传结果弹窗 */
.upload-modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1100; }
.upload-modal-content { background: #fff; border-radius: 16px; width: 440px; max-width: 90%; box-shadow: 0 20px 60px rgba(0,0,0,0.2); overflow: hidden; }
.upload-modal-header { padding: 24px 24px 0; position: relative; text-align: center; }
.upload-modal-icon { width: 56px; height: 56px; background: #EFF4FF; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; margin: 0 auto 12px; }
.upload-modal-header h3 { font-size: 18px; font-weight: 700; color: #1E293B; margin: 0; }
.upload-modal-close { position: absolute; top: 16px; right: 16px; background: none; border: none; font-size: 18px; cursor: pointer; color: #94A3B8; }
.upload-modal-close:hover { color: #475569; }
.upload-modal-body { padding: 20px 24px; }
.upload-modal-stats { display: flex; gap: 12px; }
.upload-stat-card { flex: 1; padding: 14px 8px; background: #F8FAFC; border-radius: 10px; text-align: center; }
.upload-stat-card.success { background: #ECFDF5; }
.upload-stat-card.warning { background: #FFFBEB; }
.upload-stat-num { font-size: 26px; font-weight: 700; color: #1E293B; }
.upload-stat-card.success .upload-stat-num { color: #10B981; }
.upload-stat-card.warning .upload-stat-num { color: #F59E0B; }
.upload-stat-num.fail { color: #EF4444; }
.upload-stat-label { font-size: 12px; color: #64748B; margin-top: 4px; }
.upload-invalid-tip { margin-top: 14px; padding: 10px 12px; background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 8px; }
.upload-invalid-title { font-size: 13px; font-weight: 600; color: #92400E; margin-bottom: 6px; }
.upload-invalid-reason { font-size: 11px; color: #B45309; margin-top: 2px; padding-left: 8px; }
.upload-modal-tip { margin-top: 16px; font-size: 13px; color: #64748B; text-align: center; }
.upload-modal-footer { padding: 0 24px 24px; display: flex; gap: 10px; }
.upload-modal-footer .btn-match-now { flex: 1; padding: 10px; }
.upload-modal-footer .btn-match-later { flex: 1; padding: 10px; }

/* 匹配模式选择器 */
.match-mode-selector { margin-top: 16px; }
.match-mode-options { display: flex; gap: 10px; margin-bottom: 14px; }
.match-mode-option { flex: 1; display: flex; align-items: center; gap: 8px; padding: 12px; border: 2px solid #E2E8F0; border-radius: 10px; cursor: pointer; transition: all 0.2s; background: #F8FAFC; }
.match-mode-option:hover { border-color: #93C5FD; background: #EFF6FF; }
.match-mode-option.active { border-color: #4F6EF7; background: #EFF6FF; box-shadow: 0 0 0 3px rgba(79,110,247,0.1); }
.match-mode-option input[type="radio"] { display: none; }
.match-mode-option .mode-icon { font-size: 20px; }
.match-mode-option .mode-text { display: flex; flex-direction: column; }
.match-mode-option .mode-text strong { font-size: 13px; color: #1E293B; font-weight: 600; }
.match-mode-option .mode-text small { font-size: 11px; color: #64748B; margin-top: 2px; }
.targeted-match-fields { background: #F8FAFC; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 12px; }
.targeted-match-fields .form-row { display: flex; flex-direction: column; gap: 6px; }
.targeted-match-fields .form-label { font-size: 12px; font-weight: 600; color: #475569; }
.targeted-match-fields .form-select { padding: 8px 12px; border: 1px solid #CBD5E1; border-radius: 8px; font-size: 13px; color: #1E293B; background: #fff; outline: none; transition: border-color 0.2s; }
.targeted-match-fields .form-select:focus { border-color: #4F6EF7; box-shadow: 0 0 0 3px rgba(79,110,247,0.1); }
.targeted-match-fields .form-select:disabled { background: #F1F5F9; color: #94A3B8; cursor: not-allowed; }

/* 错误提示弹窗 */
.error-modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1200; }
.error-modal-content { background: #fff; border-radius: 16px; width: 380px; max-width: 90%; box-shadow: 0 20px 60px rgba(0,0,0,0.2); overflow: hidden; }
.error-modal-header { padding: 24px 24px 0; position: relative; text-align: center; }
.error-modal-icon { width: 56px; height: 56px; background: #FEF2F2; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; color: #EF4444; margin: 0 auto 12px; }
.error-modal-header h3 { font-size: 18px; font-weight: 700; color: #1E293B; margin: 0; }
.error-modal-close { position: absolute; top: 16px; right: 16px; background: none; border: none; font-size: 18px; cursor: pointer; color: #94A3B8; }
.error-modal-close:hover { color: #475569; }
.error-modal-body { padding: 16px 24px 20px; }
.error-modal-body p { font-size: 14px; color: #475569; text-align: center; margin: 0; line-height: 1.6; }
.error-modal-footer { padding: 0 24px 24px; display: flex; justify-content: center; }
.error-modal-footer .btn-match-now { padding: 10px 32px; }

/* 批量匹配结果弹窗 */
.batch-match-modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1100; }
.batch-match-content { background: #fff; border-radius: 16px; width: 480px; max-width: 90%; box-shadow: 0 20px 60px rgba(0,0,0,0.2); overflow: hidden; }
.batch-match-header { padding: 24px 24px 0; position: relative; text-align: center; }
.batch-match-icon { width: 56px; height: 56px; background: #ECFDF5; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; color: #10B981; margin: 0 auto 12px; }
.batch-match-header h3 { font-size: 18px; font-weight: 700; color: #1E293B; margin: 0; }
.batch-match-close { position: absolute; top: 16px; right: 16px; background: none; border: none; font-size: 18px; cursor: pointer; color: #94A3B8; }
.batch-match-close:hover { color: #475569; }
.batch-match-body { padding: 24px; }
.batch-match-stats { display: flex; gap: 12px; }
.batch-stat-card { flex: 1; padding: 16px 8px; background: #F8FAFC; border-radius: 10px; text-align: center; }
.batch-stat-card.success { background: #ECFDF5; }
.batch-stat-num { font-size: 28px; font-weight: 700; color: #1E293B; }
.batch-stat-card.success .batch-stat-num { color: #10B981; }
.batch-stat-label { font-size: 12px; color: #64748B; margin-top: 4px; }
.batch-match-failed { margin-top: 12px; font-size: 13px; color: #EF4444; }
.batch-failed-title { font-weight: 600; margin-bottom: 8px; }
.batch-failed-list { background: #FEF2F2; border-radius: 8px; padding: 10px 12px; max-height: 120px; overflow-y: auto; }
.batch-failed-item { display: flex; flex-direction: column; gap: 2px; padding: 6px 0; border-bottom: 1px solid #FECACA; }
.batch-failed-item:last-child { border-bottom: none; }
.batch-failed-name { font-weight: 600; color: #991B1B; font-size: 12px; }
.batch-failed-reason { color: #B91C1C; font-size: 11px; word-break: break-all; }
.batch-match-footer { padding: 0 24px 24px; display: flex; gap: 10px; }
.batch-match-footer .btn-view-results { flex: 1; padding: 10px; }
.btn-close-modal { flex: 1; padding: 10px; background: #fff; color: #64748B; border: 1px solid #CBD5E1; border-radius: 8px; font-size: 13px; cursor: pointer; }
.btn-close-modal:hover { background: #F8FAFC; }

/* 单份简历匹配结果弹窗 */
.single-match-modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1100; }
.single-match-content { background: #fff; border-radius: 12px; width: 700px; max-width: 95%; max-height: 85vh; display: flex; flex-direction: column; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
.single-match-header { padding: 16px 20px; border-bottom: 1px solid #E8ECF0; display: flex; align-items: center; justify-content: space-between; }
.single-match-header h3 { font-size: 16px; font-weight: 600; color: #1E293B; margin: 0; }
.single-match-close { background: none; border: none; font-size: 18px; cursor: pointer; color: #64748B; }
.single-match-body { padding: 20px; overflow-y: auto; flex: 1; }
.single-match-stats { display: flex; gap: 16px; margin-bottom: 20px; }
.single-stat-card { flex: 1; padding: 16px; background: #F8FAFC; border-radius: 10px; text-align: center; }
.single-stat-card.success { background: #ECFDF5; }
.single-stat-num { font-size: 24px; font-weight: 700; color: #1E293B; }
.single-stat-card.success .single-stat-num { color: #10B981; }
.single-stat-label { font-size: 12px; color: #64748B; margin-top: 4px; }
.single-match-list-title { font-size: 14px; font-weight: 600; color: #1E293B; margin-bottom: 12px; }
.single-match-list { display: flex; flex-direction: column; gap: 8px; }
.single-match-item { display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid #E2E8F0; border-radius: 8px; }
.single-match-item.passed { border-color: #10B981; background: #F0FDF4; }
.match-item-rank { width: 24px; height: 24px; background: #E2E8F0; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; color: #475569; flex-shrink: 0; }
.single-match-item.passed .match-item-rank { background: #10B981; color: #fff; }
.match-item-info { flex: 1; min-width: 0; }
.match-item-position { font-size: 13px; font-weight: 600; color: #1E293B; }
.match-item-highlight { font-size: 12px; color: #64748B; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.match-item-score { text-align: center; flex-shrink: 0; }
.score-num { font-size: 18px; font-weight: 700; color: #4F6EF7; }
.score-label { font-size: 11px; color: #94A3B8; }
.match-item-status { flex-shrink: 0; }
.hard-pass-tag { padding: 4px 8px; background: #ECFDF5; color: #10B981; border-radius: 4px; font-size: 11px; font-weight: 600; }
.hard-fail-tag { padding: 4px 8px; background: #FEF2F2; color: #EF4444; border-radius: 4px; font-size: 11px; font-weight: 600; }
.single-match-footer { padding: 16px 20px; border-top: 1px solid #E8ECF0; display: flex; justify-content: flex-end; }

.match-status-card { padding: 16px 20px; }
.match-status-content { display: flex; align-items: center; gap: 14px; }
.match-spinner { width: 32px; height: 32px; border: 3px solid #E2E8F0; border-top-color: #4F6EF7; border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }
.match-icon { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 700; flex-shrink: 0; }
.match-icon.success { background: #ECFDF5; color: #10B981; }
.match-icon.error { background: #FEF2F2; color: #EF4444; }
.match-status-title { font-size: 14px; font-weight: 600; color: #1E293B; }
.match-status-desc { font-size: 13px; color: #64748B; margin-top: 2px; }
.resume-list-card .card-header { position: relative; }
.btn-refresh-list { margin-left: auto; padding: 5px 14px; background: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 6px; font-size: 12px; color: #64748B; cursor: pointer; }
.btn-refresh-list:hover { background: #E2E8F0; }
.btn-refresh-list:disabled { opacity: 0.5; cursor: not-allowed; }
.list-loading, .list-empty { padding: 40px 20px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 10px; }
.loading-spinner { width: 28px; height: 28px; border: 3px solid #E2E8F0; border-top-color: #4F6EF7; border-radius: 50%; animation: spin 0.8s linear infinite; }
.empty-icon { font-size: 36px; }
.empty-text { font-size: 15px; font-weight: 600; color: #475569; }
.empty-hint { font-size: 12px; color: #94A3B8; }
.resume-table-wrap { overflow-x: auto; }
.resume-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.resume-table th { background: #F8FAFC; padding: 10px 12px; text-align: left; font-weight: 600; color: #64748B; font-size: 12.5px; border-bottom: 1px solid #E2E8F0; white-space: nowrap; }
.resume-table td { padding: 10px 12px; border-bottom: 1px solid #F1F5F9; color: #334155; vertical-align: middle; }
.resume-row:hover { background: #F8FAFC; }
.cell-index { color: #94A3B8; }
.filename-text { display: inline-block; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; color: #1E293B; }
.candidate-name { font-weight: 600; color: #1E293B; }
.candidate-empty { color: #CBD5E1; }
.cell-size { color: #64748B; font-size: 12.5px; }
.type-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.type-pdf { background: #FEF2F2; color: #EF4444; }
.type-word { background: #EFF6FF; color: #3B82F6; }
.type-text { background: #F0FDF4; color: #22C55E; }
.type-image { background: #FFF7ED; color: #F59E0B; }
.type-unknown { background: #F1F5F9; color: #64748B; }
.status-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11.5px; font-weight: 500; }
.status-success { background: #ECFDF5; color: #10B981; }
.status-failed { background: #FEF2F2; color: #EF4444; }
.status-pending { background: #FFFBEB; color: #F59E0B; }
.method-tag { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; }
.method-ai { background: #F0FDF4; color: #16A34A; }
.method-rule { background: #F0F9FF; color: #0284C7; }
.method-unknown { background: #F1F5F9; color: #94A3B8; }
.cell-time { color: #64748B; font-size: 12px; white-space: nowrap; }
.cell-action { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.btn-action { padding: 3px 10px; border-radius: 5px; font-size: 12px; font-weight: 500; cursor: pointer; border: none; }
.btn-match { background: #EEF1FE; color: #4F6EF7; }
.btn-match:hover { background: #E0E6FD; }
.btn-match:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-delete { background: #FEF2F2; color: #EF4444; }
.btn-delete:hover { background: #FEE2E2; }
.action-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.status-select {
  padding: 3px 6px;
  border: 1px solid #CBD5E1;
  border-radius: 5px;
  font-size: 12px;
  color: #334155;
  background: #fff;
  cursor: pointer;
  max-width: 90px;
}
.status-select:hover { border-color: #4F6EF7; }
.status-select:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-routing { background: #FFFBEB; color: #D97706; border: 1px solid #FDE68A; }
.btn-routing:hover { background: #FEF3C7; }
.btn-routing.paused { background: #FEF2F2; color: #EF4444; border-color: #FECACA; }
.btn-routing.paused:hover { background: #FEE2E2; }
.btn-reassign { background: #F0FDF4; color: #16A34A; border: 1px solid #BBF7D0; }
.btn-reassign:hover { background: #DCFCE7; }

/* 业务状态标签 */
.cell-business-status { text-align: center; }
.biz-status-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.biz-valid { background: #DBEAFE; color: #2563EB; }
.biz-submitted { background: #FEF3C7; color: #D97706; }
.biz-passed { background: #D1FAE5; color: #059669; }
.biz-invalid { background: #FEE2E2; color: #DC2626; }
.routing-paused-dot { font-size: 10px; }
.status-edit-wrap { display: inline-block; }
.status-select-inline {
  padding: 3px 6px;
  border: 1px solid #4F6EF7;
  border-radius: 10px;
  font-size: 11px;
  color: #334155;
  background: #fff;
  cursor: pointer;
  outline: none;
}
.btn-routing-inline {
  margin-left: 4px;
  padding: 2px 6px;
  border: 1px solid #FDE68A;
  border-radius: 8px;
  font-size: 10px;
  background: #FFFBEB;
  color: #D97706;
  cursor: pointer;
  line-height: 1;
}
.btn-routing-inline.paused {
  background: #FEF2F2;
  color: #EF4444;
  border-color: #FECACA;
}
.btn-routing-inline:hover { opacity: 0.8; }
.btn-delete-all-resumes {
  margin-left: 8px;
  padding: 5px 14px;
  background: #FEF2F2;
  border: 1px solid #FECACA;
  border-radius: 6px;
  font-size: 12px;
  color: #EF4444;
  font-weight: 500;
  cursor: pointer;
}
.btn-delete-all-resumes:hover { background: #FEE2E2; }
.btn-delete-all-resumes:disabled { opacity: 0.5; cursor: not-allowed; }

/* 搜索栏 */
.resume-search-bar { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.search-input-wrap { position: relative; flex: 1; max-width: 360px; }
.search-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); font-size: 14px; opacity: 0.5; }
.search-input { width: 100%; padding: 9px 12px 9px 36px; border: 1px solid #E2E8F0; border-radius: 8px; font-size: 13px; color: #1E293B; background: #fff; transition: border-color 0.2s; }
.search-input:focus { outline: none; border-color: #4F6EF7; box-shadow: 0 0 0 3px rgba(79,110,247,0.1); }
.search-input::placeholder { color: #94A3B8; }
.search-count { font-size: 12px; color: #94A3B8; white-space: nowrap; }
/* 分页 */
.pagination { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 16px; padding-top: 16px; border-top: 1px solid #F1F5F9; }
.page-btn { padding: 6px 14px; border: 1px solid #E2E8F0; border-radius: 6px; background: #fff; color: #475569; font-size: 12px; cursor: pointer; }
.page-btn:hover:not(:disabled) { border-color: #4F6EF7; color: #4F6EF7; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 12px; color: #64748B; }

/* 重复标记 */
.dup-tag { display: inline-block; padding: 1px 6px; background: #FEF3C7; color: #92400E; font-size: 10px; border-radius: 3px; font-weight: 600; }
/* 分配按钮 */
.btn-reassign { background: #EEF2FF; color: #4F46E5; }
.btn-reassign:hover { background: #E0E7FF; }
/* 分配弹窗 */
.reassign-modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.reassign-content { background: #fff; border-radius: 12px; width: 420px; max-height: 80vh; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
.reassign-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid #F1F5F9; }
.reassign-header h3 { margin: 0; font-size: 16px; color: #1E293B; }
.reassign-close { background: none; border: none; font-size: 18px; color: #94A3B8; cursor: pointer; }
.reassign-body { padding: 20px; }
.reassign-desc { font-size: 13px; color: #475569; margin: 0 0 8px; }
.reassign-current { font-size: 12px; color: #94A3B8; margin: 0 0 16px; }
.recruiter-list { max-height: 300px; overflow-y: auto; }
.recruiter-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid #E2E8F0; border-radius: 8px; margin-bottom: 8px; cursor: pointer; transition: all 0.15s; }
.recruiter-item:hover { border-color: #4F6EF7; background: #F8FAFF; }
.recruiter-item.active { border-color: #4F6EF7; background: #EEF2FF; }
.recruiter-name { font-weight: 600; color: #1E293B; font-size: 13px; }
.recruiter-phone { font-size: 12px; color: #94A3B8; margin-left: auto; }
.recruiter-current-tag { padding: 2px 8px; background: #4F6EF7; color: #fff; font-size: 10px; border-radius: 10px; }
.recruiter-empty { text-align: center; padding: 32px; color: #94A3B8; font-size: 13px; }

/* 复选框 */
.checkbox { width: 16px; height: 16px; cursor: pointer; accent-color: #4F6EF7; }
.row-selected { background: #F0F4FF !important; }
/* 批量操作栏 */
.batch-action-bar { display: flex; align-items: center; gap: 12px; padding: 10px 16px; margin-bottom: 12px; background: #EFF4FF; border: 1px solid #C7D2FE; border-radius: 8px; }
.batch-selected-info { font-size: 13px; color: #3730A3; }
.batch-selected-info strong { color: #4F46E5; font-size: 15px; }
.btn-batch-reassign { padding: 6px 16px; background: #4F46E5; color: #fff; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; }
.btn-batch-reassign:hover { background: #4338CA; }
.btn-clear-selection { padding: 6px 12px; background: none; border: 1px solid #C7D2FE; color: #6366F1; border-radius: 6px; font-size: 12px; cursor: pointer; }
.btn-clear-selection:hover { background: #E0E7FF; }
</style>