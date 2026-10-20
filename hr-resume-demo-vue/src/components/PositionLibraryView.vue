<script setup>
import { ref, onMounted, computed, inject } from 'vue'
import { companyApi, positionApi } from '../api/index.js'
import { getStoredUser } from '../api/index.js'
import SchemaConfig from './SchemaConfig.vue'

const navigateTo = inject('navigateTo')
const showAlert = inject('showAlert')
const showConfirm = inject('showConfirm')
const currentUser = getStoredUser()

// 权限判断：超管/维护人员可编辑所有；招聘人员只能编辑自己创建的
function canEdit(item) {
  if (!currentUser) return false
  if (currentUser.role === 'super_admin') return true
  if (currentUser.role === 'maintainer') return true
  if (currentUser.role === 'recruiter') return item.creator_id === currentUser.id
  return false
}

const companies = ref([])
const positions = ref([])
const loading = ref(false)

// 搜索与分页
const filterCompany = ref('')
const filterPosition = ref('')
const currentPage = ref(1)
const pageSize = 10

// 联动：选公司后岗位下拉只显示该公司的岗位
const filteredPositionOptions = computed(() => {
  if (!filterCompany.value) return positions.value
  return positions.value.filter(p => p.company_id === filterCompany.value)
})

// 按搜索条件过滤岗位
const filteredPositions = computed(() => {
  let list = positions.value
  if (filterCompany.value) {
    list = list.filter(p => p.company_id === filterCompany.value)
  }
  if (filterPosition.value) {
    list = list.filter(p => p.id === filterPosition.value)
  }
  return list
})

// 分页
const totalPages = computed(() => Math.max(1, Math.ceil(filteredPositions.value.length / pageSize)))
const pagedPositions = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredPositions.value.slice(start, start + pageSize)
})

function goPage(p) {
  if (p < 1 || p > totalPages.value) return
  currentPage.value = p
}
function resetPositionFilters() {
  filterCompany.value = ''
  filterPosition.value = ''
  currentPage.value = 1
}
const error = ref('')
const matchingPositionId = ref(null)  // 正在匹配的岗位ID

// 岗位弹窗状态
const showPositionModal = ref(false)
const editingPosition = ref(null)
const savedPositionId = ref(null)  // 已保存的岗位ID（用于加载Schema配置）
const positionForm = ref({
  company_id: null,
  name: '',
  description: '',
  status: '招聘中',
  headcount: 1
})

// 加载数据
async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const companyData = await companyApi.list()
    // 公司按倒序排列，最新创建的在前面
    companies.value = companyData.sort((a, b) => (b.id || 0) - (a.id || 0))
    const positionData = await positionApi.list()
    // 岗位按倒序排列，最新创建的在前面
    positions.value = positionData.sort((a, b) => (b.id || 0) - (a.id || 0))
  } catch (e) {
    error.value = '加载数据失败: ' + e.message
  } finally {
    loading.value = false
  }
}

// ========== 岗位管理 ==========
function openAddPosition() {
  editingPosition.value = null
  savedPositionId.value = null
  positionForm.value = {
    company_id: companies.value[0]?.id || null,
    name: '',
    description: '',
    status: '招聘中',
    headcount: 1
  }
  showPositionModal.value = true
}

function openEditPosition(pos) {
  editingPosition.value = pos
  savedPositionId.value = pos.id
  positionForm.value = {
    company_id: pos.company_id,
    name: pos.name,
    description: pos.description || '',
    status: pos.status,
    headcount: pos.headcount
  }
  showPositionModal.value = true
}

// 保存成功提示
const showSaveSuccess = ref(false)
// SchemaConfig组件引用
const schemaConfigRef = ref(null)
// 正在保存中
const savingAll = ref(false)

// 完成配置：保存岗位信息 + Schema配置，然后关闭弹窗
async function saveAndClose() {
  if (!positionForm.value.company_id) {
    showAlert('请选择所属公司', 'warning')
    return
  }
  if (!positionForm.value.name.trim()) {
    showAlert('请输入岗位名称', 'warning')
    return
  }

  // 校验Schema配置：如果有字段但要求未填写完整，阻止保存
  if (schemaConfigRef.value && schemaConfigRef.value.hasFields()) {
    if (!schemaConfigRef.value.allRequirementsFilled()) {
      const unfilledNames = schemaConfigRef.value.getUnfilledFieldNames()
      showAlert(`还有 ${unfilledNames.length} 个字段未填写匹配要求（${unfilledNames.join('、')}），请填写完整后再保存`, 'warning')
      return
    }
  }

  if (savingAll.value) return
  savingAll.value = true

  try {
    // 1. 先保存岗位基本信息
    let isNewPosition = false
    if (editingPosition.value) {
      await positionApi.update(editingPosition.value.id, positionForm.value)
      savedPositionId.value = editingPosition.value.id
    } else {
      const result = await positionApi.create(positionForm.value)
      savedPositionId.value = result.id || result.position_id
      editingPosition.value = result
      isNewPosition = true
    }

    // 2. 如果是新增岗位，等待SchemaConfig从草稿模式转为正式模式
    if (isNewPosition && schemaConfigRef.value) {
      // 等待Vue更新props和watch执行
      await new Promise(resolve => setTimeout(resolve, 100))
    }

    // 3. 保存Schema配置（如果有修改）
    if (schemaConfigRef.value && savedPositionId.value) {
      const hasChanges = schemaConfigRef.value.isDirty()
      if (hasChanges) {
        const result = await schemaConfigRef.value.saveAll(false)
        if (!result.success && result.reason && result.reason !== 'no_changes') {
          showAlert('Schema配置保存失败: ' + result.reason, 'error')
          savingAll.value = false
          return
        }
      }
    }

    // 4. 刷新数据并关闭弹窗
    await loadData()
    showPositionModal.value = false
  } catch (e) {
    showAlert('保存失败: ' + e.message, 'error')
  } finally {
    savingAll.value = false
  }
}

async function deletePosition(pos) {
  const confirmed = await showConfirm(`确定删除岗位"${pos.name}"吗？`, '删除确认', 'warning')
  if (!confirmed) return
  try {
    await positionApi.delete(pos.id)
    await loadData()
  } catch (e) {
    showAlert('删除失败: ' + e.message, 'error')
  }
}

async function matchPositionResumes(pos) {
  const confirmed = await showConfirm(`确定要对岗位"${pos.name}"匹配所有已解析简历吗？\n匹配完成后可在「匹配结果」页面查看。`, '匹配确认', 'info')
  if (!confirmed) return
  matchingPositionId.value = pos.id
  try {
    const result = await positionApi.matchAllResumes(pos.id)
    showAlert(`匹配完成！\n岗位：${result.position_name}\n共处理 ${result.total_resumes} 份简历\n成功匹配 ${result.matched_count} 份\n通过硬性条件 ${result.passed_count} 份\n\n请前往「匹配结果」页面查看详情。`, 'success', '匹配完成')
  } catch (e) {
    showAlert('匹配失败: ' + e.message, 'error')
  } finally {
    matchingPositionId.value = null
  }
}

async function toggleStatus(pos) {
  const nextStatus = pos.status === '招聘中' ? '暂停' : '招聘中'
  try {
    await positionApi.updateStatus(pos.id, nextStatus)
    await loadData()
  } catch (e) {
    showAlert('状态更新失败: ' + e.message, 'error')
  }
}

// 岗位状态标签颜色
function statusClass(status) {
  const map = {
    '招聘中': 'tag-hard',
    '暂停': 'tag-soft',
    '已满岗': 'tag-soft'
  }
  return map[status] || 'tag-soft'
}

onMounted(() => loadData())
</script>

<template>
  <div class="page-view">
    <div class="card">
      <div class="card-header">
        <span class="card-title">配置岗位需求</span>
        <span class="card-subtitle">全公司岗位台账管理</span>
        <button v-if="currentUser?.role !== 'recruiter'" class="btn-batch-import" style="margin-left: auto;" @click="navigateTo && navigateTo('批量导入')">
          📥 批量导入
        </button>
        <button class="btn-primary" style="padding: 6px 16px; font-size: 13px; margin-left: 8px;" @click="openAddPosition">
          + 新增岗位
        </button>
      </div>
      <div class="card-body">
        <div v-if="error" style="color:#EF4444; margin-bottom:12px; padding:8px; background:#FEF2F2; border-radius:6px;">
          {{ error }}
        </div>
        <!-- 搜索栏 -->
        <div class="filter-bar" style="margin-bottom:16px;">
          <div class="filter-item">
            <label>公司</label>
            <select v-model="filterCompany" class="filter-select" @change="filterPosition=''; currentPage=1">
              <option value="">全部公司</option>
              <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </div>
          <div class="filter-item">
            <label>岗位</label>
            <select v-model="filterPosition" class="filter-select" @change="currentPage=1">
              <option value="">全部岗位</option>
              <option v-for="p in filteredPositionOptions" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <button class="btn-reset-filter" @click="resetPositionFilters">重置</button>
          <span style="margin-left:auto; font-size:12px; color:#94A3B8;">共 {{ filteredPositions.length }} 条</span>
        </div>

        <div v-if="loading" style="text-align:center; padding:40px; color:#94A3B8;">加载中...</div>
        <div v-else-if="filteredPositions.length === 0" style="text-align:center; padding:40px; color:#94A3B8;">
          暂无岗位数据，点击右上角「新增岗位」添加
        </div>
        <table v-else class="schema-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>所属公司</th>
              <th>岗位名称</th>
              <th>招聘人数</th>
              <th>岗位状态</th>
              <th>创建者</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pos in pagedPositions" :key="pos.id">
              <td>{{ pos.id }}</td>
              <td>
                {{ companies.find(c => c.id === pos.company_id)?.name || '未知公司' }}
              </td>
              <td style="font-weight: 500;">{{ pos.name }}</td>
              <td>{{ pos.headcount }} 人</td>
              <td>
                <span
                  :class="statusClass(pos.status)"
                  :style="{ cursor: canEdit(pos) ? 'pointer' : 'default' }"
                  @click="canEdit(pos) && toggleStatus(pos)"
                  :title="canEdit(pos) ? '点击切换状态' : '无权修改'"
                >
                  {{ pos.status }}
                </span>
              </td>
              <td style="font-size:12px; color:#64748B;">{{ pos.creator_name || '系统' }}</td>
              <td>{{ new Date(pos.updated_at).toLocaleDateString() }}</td>
              <td style="white-space:nowrap;">
                <div class="table-action-btns">
                  <button class="table-btn table-btn-success" @click="matchPositionResumes(pos)" :disabled="matchingPositionId === pos.id">
                    {{ matchingPositionId === pos.id ? '匹配中...' : '匹配简历' }}
                  </button>
                  <template v-if="canEdit(pos)">
                    <button class="table-btn table-btn-primary" @click="openEditPosition(pos)">编辑</button>
                    <button class="table-btn table-btn-danger" @click="deletePosition(pos)">删除</button>
                  </template>
                  <span v-else style="font-size:12px; color:#94A3B8;">只读</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 分页 -->
        <div class="pagination" v-if="filteredPositions.length > pageSize">
          <button class="page-btn" :disabled="currentPage === 1" @click="goPage(currentPage - 1)">上一页</button>
          <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页（共 {{ filteredPositions.length }} 条）</span>
          <button class="page-btn" :disabled="currentPage === totalPages" @click="goPage(currentPage + 1)">下一页</button>
        </div>
      </div>
    </div>

    <!-- 岗位新增/编辑弹窗（合并配置需求） -->
    <div v-if="showPositionModal" class="modal-overlay" @click.self="showPositionModal = false">
      <div class="modal-content modal-content-large">
        <div class="modal-header">
          <h3>{{ editingPosition ? '编辑岗位' : '新增岗位' }}</h3>
          <button @click="showPositionModal = false" style="background:none; border:none; font-size:20px; cursor:pointer; color:#64748B;">&times;</button>
        </div>
        <div class="modal-body modal-body-scroll">
          <!-- 岗位基本信息 -->
          <div class="section-title">岗位基本信息</div>
          <div class="form-group">
            <label>所属公司</label>
            <select v-model="positionForm.company_id" :disabled="!!savedPositionId">
              <option :value="null">请选择公司</option>
              <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>岗位名称</label>
            <input v-model="positionForm.name" type="text" placeholder="如：高级数据分析师" />
          </div>
          <div class="form-group">
            <label>岗位描述</label>
            <textarea v-model="positionForm.description" rows="2" placeholder="岗位职责描述..."></textarea>
          </div>
          <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 12px;">
            <div class="form-group">
              <label>岗位状态</label>
              <select v-model="positionForm.status">
                <option value="招聘中">招聘中</option>
                <option value="暂停">暂停</option>
                <option value="已满岗">已满岗</option>
              </select>
            </div>
            <div class="form-group">
              <label>招聘人数</label>
              <input v-model.number="positionForm.headcount" type="number" min="1" />
            </div>
          </div>

          <!-- 配置需求区域（新增岗位时直接显示，草稿模式） -->
          <div class="section-title section-title-with-line">配置岗位需求（Schema）</div>

          <!-- Schema配置组件（新增岗位时为草稿模式，编辑岗位时为正式模式） -->
          <SchemaConfig
            ref="schemaConfigRef"
            :company-id="positionForm.company_id"
            :position-id="savedPositionId"
            :embedded="true"
          />
        </div>
        <!-- 保存成功提示 -->
        <div v-if="showSaveSuccess" class="save-success-tip">
          ✓ 保存成功！岗位信息和Schema配置已保存，系统正在后台自动匹配简历
        </div>
        <div class="modal-footer">
          <button class="btn-outline" @click="showPositionModal = false" :disabled="savingAll">取消</button>
          <button class="btn-primary" @click="saveAndClose" :disabled="savingAll">
            {{ savingAll ? '保存中...' : '完成配置' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  z-index: 1000;
  overflow-y: auto;
  padding: 40px 0;
}
.modal-content {
  background: #fff;
  border-radius: 12px;
  width: 480px;
  max-width: 90%;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.modal-content-large {
  width: 800px;
  max-width: 95%;
  max-height: 92vh;
}
.modal-body-scroll {
  overflow-y: auto;
  padding: 20px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
  margin-bottom: 12px;
  margin-top: 4px;
}
.section-title-with-line {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #E8ECF0;
}
.schema-placeholder {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 24px;
  background: #F8FAFC;
  border: 1px dashed #CBD5E1;
  border-radius: 10px;
}
.schema-placeholder-icon {
  font-size: 32px;
  flex-shrink: 0;
}
.schema-placeholder-text {
  flex: 1;
}
.config-modal-overlay {
  z-index: 1100;
  align-items: center;
}
.config-modal-content {
  width: 66.67vw !important;
  max-width: 96% !important;
  max-height: 95vh !important;
}
.config-modal-header {
  background: linear-gradient(135deg, #8B5CF6 0%, #6366F1 100%);
  color: #fff;
  border-bottom: none;
}
.config-modal-header h3 {
  color: #fff;
}
.config-modal-body {
  padding: 16px;
  overflow-y: auto;
}
.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid #E8ECF0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.modal-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1E293B;
  margin: 0;
}
.modal-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

/* 公司管理弹窗 */
.company-modal {
  width: 620px;
}
.company-modal-body {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.header-count {
  font-size: 12px;
  font-weight: normal;
  color: #94A3B8;
  margin-left: 8px;
}
.company-search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.company-search-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 13px;
}
.company-search-input:focus {
  outline: none;
  border-color: #4F46E5;
  box-shadow: 0 0 0 3px rgba(79,70,229,0.1);
}
.company-search-count {
  font-size: 12px;
  color: #94A3B8;
  white-space: nowrap;
}
.company-list-scroll {
  max-height: 280px;
  overflow-y: auto;
  border: 1px solid #F1F5F9;
  border-radius: 8px;
  background: #FAFBFC;
}
.company-list-scroll::-webkit-scrollbar {
  width: 6px;
}
.company-list-scroll::-webkit-scrollbar-thumb {
  background: #CBD5E1;
  border-radius: 3px;
}
.company-empty {
  padding: 32px;
  text-align: center;
  color: #94A3B8;
  font-size: 13px;
}
.company-list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid #F1F5F9;
  background: #fff;
}
.company-list-item:last-child {
  border-bottom: none;
}
.company-list-item:hover {
  background: #F8FAFC;
}
.company-info {
  flex: 1;
  min-width: 0;
}
.company-name {
  font-weight: 500;
  color: #1E293B;
  font-size: 13px;
}
.company-creator {
  font-size: 11px;
  color: #94A3B8;
  margin-left: 8px;
  font-weight: normal;
}
.company-desc {
  font-size: 12px;
  color: #64748B;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.company-actions {
  display: flex;
  gap: 10px;
  margin-left: 12px;
  flex-shrink: 0;
}
.company-btn-edit {
  background: none;
  border: none;
  color: #4F6EF7;
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
}
.company-btn-edit:hover {
  text-decoration: underline;
}
.company-btn-delete {
  background: none;
  border: none;
  color: #EF4444;
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
}
.company-btn-delete:hover {
  text-decoration: underline;
}
.company-readonly {
  font-size: 12px;
  color: #94A3B8;
}
.company-form-section {
  border-top: 1px solid #E8ECF0;
  padding-top: 14px;
}
.company-form-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
  color: #1E293B;
}
.company-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.company-meta {
  display: flex;
  gap: 12px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.company-city {
  font-size: 11px;
  color: #059669;
}
.company-email {
  font-size: 11px;
  color: #4F6EF7;
}
.form-group {
  margin-bottom: 16px;
}
.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  margin-bottom: 6px;
}
.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  font-size: 13px;
  color: #1E293B;
  background: #fff;
  font-family: inherit;
}
.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #4F6EF7;
}
.save-success-tip {
  margin: 0 20px 10px;
  padding: 10px 14px;
  background: #ECFDF5;
  border: 1px solid #A7F3D0;
  border-radius: 8px;
  font-size: 13px;
  color: #065F46;
  font-weight: 500;
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-5px); }
  to { opacity: 1; transform: translateY(0); }
}
.modal-footer {
  padding: 14px 20px;
  border-top: 1px solid #E8ECF0;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 搜索筛选栏 */
.filter-bar { display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.filter-item { display: flex; flex-direction: column; gap: 4px; }
.filter-item label { font-size: 12px; color: #64748B; font-weight: 500; }
.filter-select { padding: 7px 12px; border: 1px solid #E2E8F0; border-radius: 6px; font-size: 13px; color: #1E293B; background: #fff; min-width: 140px; cursor: pointer; }
.filter-select:focus { outline: none; border-color: #4F6EF7; }
.btn-reset-filter { padding: 7px 14px; border: 1px solid #E2E8F0; border-radius: 6px; background: #F8FAFC; color: #64748B; font-size: 12px; cursor: pointer; }
.btn-reset-filter:hover { background: #E2E8F0; }
/* 分页 */
.pagination { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 16px; padding-top: 16px; border-top: 1px solid #F1F5F9; }
.page-btn { padding: 6px 14px; border: 1px solid #E2E8F0; border-radius: 6px; background: #fff; color: #475569; font-size: 12px; cursor: pointer; }
.page-btn:hover:not(:disabled) { border-color: #4F6EF7; color: #4F6EF7; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 12px; color: #64748B; }

.btn-batch-import {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 6px 16px; font-size: 13px; font-weight: 600;
  background: #EEF2FF; color: #4F46E5;
  border: 1px solid #C7D2FE; border-radius: 6px;
  cursor: pointer; transition: all 0.2s;
}
.btn-batch-import:hover { background: #E0E7FF; }
</style>