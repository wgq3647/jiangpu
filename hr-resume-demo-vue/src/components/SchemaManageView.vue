<script setup>
import { ref, onMounted, computed, inject } from 'vue'
import { factorApi, positionTemplateApi } from '../api/index.js'
import { getStoredUser } from '../api/index.js'

const navigateTo = inject('navigateTo')
const showAlert = inject('showAlert')
const showConfirm = inject('showConfirm')
const currentUser = getStoredUser()
const canEdit = currentUser?.role === 'super_admin' || currentUser?.role === 'maintainer'

const activeTab = ref('factors') // 'factors' | 'templates'

// ========== 因子库相关 ==========
const factors = ref([])
const fieldTypes = ref([])
const factorsLoading = ref(false)
const showFactorModal = ref(false)
const editingFactor = ref(null)
const factorForm = ref({ name: '', field_type: '', description: '' })

async function loadFactors() {
  factorsLoading.value = true
  try {
    const [list, types] = await Promise.all([factorApi.list(), factorApi.fieldTypes()])
    factors.value = list
    fieldTypes.value = types
  } catch (e) {
    showAlert('加载因子失败: ' + e.message, 'error')
  } finally {
    factorsLoading.value = false
  }
}

function getFieldTypeLabel(type) {
  const found = fieldTypes.value.find(t => t.value === type)
  return found ? found.label : type
}

function openAddFactor() {
  editingFactor.value = null
  factorForm.value = { name: '', field_type: '枚举', description: '' }
  showFactorModal.value = true
}

function openEditFactor(factor) {
  editingFactor.value = factor
  factorForm.value = { name: factor.name, field_type: factor.field_type, description: factor.description || '' }
  showFactorModal.value = true
}

async function saveFactor() {
  if (!factorForm.value.name.trim()) {
    showAlert('请输入因子名称', 'warning')
    return
  }
  if (!factorForm.value.field_type) {
    showAlert('请选择字段类型', 'warning')
    return
  }
  try {
    if (editingFactor.value) {
      await factorApi.update(editingFactor.value.id, factorForm.value)
    } else {
      await factorApi.create(factorForm.value)
    }
    showFactorModal.value = false
    loadFactors()
  } catch (e) {
    showAlert('保存失败: ' + e.message, 'error')
  }
}

async function deleteFactor(factor) {
  const confirmed = await showConfirm(`确定删除因子「${factor.name}」吗？`, '删除确认', 'warning')
  if (!confirmed) return
  try {
    await factorApi.delete(factor.id)
    loadFactors()
  } catch (e) {
    showAlert('删除失败: ' + e.message, 'error')
  }
}

// ========== 模板库相关 ==========
const templates = ref([])
const templatesLoading = ref(false)
const selectedTemplateId = ref(null)
const showTemplateModal = ref(false)
const editingTemplate = ref(null)
const templateForm = ref({ name: '', description: '', factor_ids: [] })
const factorSearchKeyword = ref('')

const selectedTemplate = computed(() => templates.value.find(t => t.id === selectedTemplateId.value))
const availableFactors = computed(() => {
  const selectedIds = templateForm.value.factor_ids
  const kw = factorSearchKeyword.value.trim().toLowerCase()
  return factors.value.filter(f => {
    if (selectedIds.includes(f.id)) return false
    if (kw && !f.name.toLowerCase().includes(kw)) return false
    return true
  })
})

async function loadTemplates() {
  templatesLoading.value = true
  try {
    templates.value = await positionTemplateApi.list()
    if (templates.value.length > 0 && !selectedTemplateId.value) {
      selectedTemplateId.value = templates.value[0].id
    }
  } catch (e) {
    showAlert('加载模板失败: ' + e.message, 'error')
  } finally {
    templatesLoading.value = false
  }
}

function openAddTemplate() {
  editingTemplate.value = null
  templateForm.value = { name: '', description: '', factor_ids: [] }
  showTemplateModal.value = true
}

function openEditTemplate(tpl) {
  editingTemplate.value = tpl
  templateForm.value = {
    name: tpl.name,
    description: tpl.description || '',
    factor_ids: tpl.factors.map(f => f.id)
  }
  showTemplateModal.value = true
}

async function saveTemplate() {
  if (!templateForm.value.name.trim()) {
    showAlert('请输入模板名称', 'warning')
    return
  }
  try {
    if (editingTemplate.value) {
      await positionTemplateApi.update(editingTemplate.value.id, templateForm.value)
    } else {
      await positionTemplateApi.create(templateForm.value)
    }
    showTemplateModal.value = false
    await loadTemplates()
  } catch (e) {
    showAlert('保存失败: ' + e.message, 'error')
  }
}

async function deleteTemplate(tpl) {
  const confirmed = await showConfirm(`确定删除模板「${tpl.name}」吗？`, '删除确认', 'warning')
  if (!confirmed) return
  try {
    await positionTemplateApi.delete(tpl.id)
    if (selectedTemplateId.value === tpl.id) {
      selectedTemplateId.value = null
    }
    await loadTemplates()
  } catch (e) {
    showAlert('删除失败: ' + e.message, 'error')
  }
}

function toggleFactorInForm(factorId) {
  const idx = templateForm.value.factor_ids.indexOf(factorId)
  if (idx >= 0) {
    templateForm.value.factor_ids.splice(idx, 1)
  } else {
    templateForm.value.factor_ids.push(factorId)
  }
}

function removeFactorFromForm(factorId) {
  const idx = templateForm.value.factor_ids.indexOf(factorId)
  if (idx >= 0) {
    templateForm.value.factor_ids.splice(idx, 1)
  }
}

// Tab切换时加载对应数据
function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'factors' && factors.value.length === 0) {
    loadFactors()
  }
  if (tab === 'templates' && templates.value.length === 0) {
    loadTemplates()
  }
}

onMounted(() => {
  loadFactors()
})
</script>

<template>
  <div class="schema-manage-page">
    <!-- 页面标题 + Tab切换 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">配置岗位Schema</h2>
        <p class="page-desc">维护Schema因子库，组合成岗位模板，快速应用到岗位配置</p>
      </div>
      <div class="tab-switcher">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'factors' }"
          @click="switchTab('factors')"
        >
          Schema因子
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'templates' }"
          @click="switchTab('templates')"
        >
          模板库
        </button>
      </div>
    </div>

    <!-- ========== Tab1: Schema因子 ========== -->
    <div v-if="activeTab === 'factors'" class="tab-content">
      <div class="card">
        <div class="card-header">
          <span class="card-title">岗位要求因子库</span>
          <span class="card-subtitle">维护组预定义字段和类型，可组合成岗位模板</span>
          <button v-if="canEdit" class="btn-primary btn-header" @click="openAddFactor">
            + 新增因子
          </button>
        </div>
        <div class="card-body">
          <div v-if="factorsLoading" class="loading-tip">加载中...</div>
          <div v-else-if="factors.length === 0" class="empty-hint">
            暂无因子，点击右上角「新增因子」开始维护
          </div>
          <table v-else class="data-table">
            <thead>
              <tr>
                <th style="width: 60px;">ID</th>
                <th>因子名称</th>
                <th style="width: 120px;">字段类型</th>
                <th>说明</th>
                <th style="width: 120px;">创建者</th>
                <th style="width: 160px;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="f in factors" :key="f.id">
                <td>{{ f.id }}</td>
                <td><strong>{{ f.name }}</strong></td>
                <td><span class="tag tag-soft">{{ getFieldTypeLabel(f.field_type) }}</span></td>
                <td>{{ f.description || '-' }}</td>
                <td>{{ f.creator_name || '-' }}</td>
                <td>
                  <div class="action-btns">
                    <button v-if="canEdit" class="btn-action btn-edit" @click="openEditFactor(f)">编辑</button>
                    <button v-if="canEdit" class="btn-action btn-delete" @click="deleteFactor(f)">删除</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ========== Tab2: 模板库 ========== -->
    <div v-if="activeTab === 'templates'" class="tab-content">
      <div class="card">
        <div class="card-header">
          <span class="card-title">岗位模板库</span>
          <span class="card-subtitle">由因子组合而成，可快速应用到岗位Schema配置</span>
          <button v-if="canEdit" class="btn-primary btn-header" @click="openAddTemplate">
            + 新建模板
          </button>
        </div>
        <div class="card-body">
          <div v-if="templatesLoading" class="loading-tip">加载中...</div>
          <div v-else-if="templates.length === 0" class="empty-hint">
            暂无模板，点击右上角「新建模板」开始创建
          </div>
          <div v-else class="template-layout">
            <!-- 左侧模板列表 -->
            <div class="template-list">
              <div
                v-for="tpl in templates"
                :key="tpl.id"
                class="template-item"
                :class="{ active: selectedTemplateId === tpl.id }"
                @click="selectedTemplateId = tpl.id"
              >
                <div class="template-item-header">
                  <strong>{{ tpl.name }}</strong>
                  <span class="factor-count">{{ tpl.factor_count }}个因子</span>
                </div>
                <div class="template-item-desc">{{ tpl.description || '暂无说明' }}</div>
                <div class="template-item-actions" v-if="canEdit">
                  <button class="btn-link" @click.stop="openEditTemplate(tpl)">编辑</button>
                  <button class="btn-link btn-danger" @click.stop="deleteTemplate(tpl)">删除</button>
                </div>
              </div>
            </div>

            <!-- 右侧模板详情 -->
            <div class="template-detail" v-if="selectedTemplate">
              <div class="detail-header">
                <h3>{{ selectedTemplate.name }}</h3>
                <span class="detail-desc">{{ selectedTemplate.description || '暂无说明' }}</span>
              </div>
              <div class="detail-section">
                <h4>包含的因子（{{ selectedTemplate.factors.length }}个）</h4>
                <div v-if="selectedTemplate.factors.length === 0" class="empty-hint-small">
                  此模板暂未添加因子
                </div>
                <div v-else class="factor-chips">
                  <div v-for="f in selectedTemplate.factors" :key="f.id" class="factor-chip">
                    <span class="factor-name">{{ f.name }}</span>
                    <span class="factor-type">{{ getFieldTypeLabel(f.field_type) }}</span>
                  </div>
                </div>
              </div>
              <div class="detail-tip">
                💡 在「JD岗位配置」页面选择岗位后，可直接应用此模板快速填充Schema字段
              </div>
            </div>
            <div v-else class="template-detail empty-detail">
              请选择左侧模板查看详情
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ========== 因子新增/编辑弹窗 ========== -->
    <div v-if="showFactorModal" class="modal-overlay" @click.self="showFactorModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingFactor ? '编辑因子' : '新增因子' }}</h3>
          <button class="modal-close" @click="showFactorModal = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>因子名称 <span class="required">*</span></label>
            <input v-model="factorForm.name" class="form-input" placeholder="如：学历、工作年限、Python技能" />
          </div>
          <div class="form-group">
            <label>字段类型 <span class="required">*</span></label>
            <select v-model="factorForm.field_type" class="form-input">
              <option v-for="t in fieldTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>说明</label>
            <textarea v-model="factorForm.description" class="form-input" rows="3" placeholder="因子的用途说明（可选）"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-outline" @click="showFactorModal = false">取消</button>
          <button class="btn-primary" @click="saveFactor">{{ editingFactor ? '保存修改' : '确认新增' }}</button>
        </div>
      </div>
    </div>

    <!-- ========== 模板新增/编辑弹窗 ========== -->
    <div v-if="showTemplateModal" class="modal-overlay" @click.self="showTemplateModal = false">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3>{{ editingTemplate ? '编辑模板' : '新建模板' }}</h3>
          <button class="modal-close" @click="showTemplateModal = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>模板名称 <span class="required">*</span></label>
            <input v-model="templateForm.name" class="form-input" placeholder="如：技术岗通用模板、产品经理模板" />
          </div>
          <div class="form-group">
            <label>模板说明</label>
            <textarea v-model="templateForm.description" class="form-input" rows="2" placeholder="模板适用场景说明（可选）"></textarea>
          </div>
          <div class="form-group">
            <label>选择因子（已选 {{ templateForm.factor_ids.length }} 个）</label>
            <div class="factor-picker">
              <div class="picker-selected">
                <div class="picker-title">已选因子</div>
                <div v-if="templateForm.factor_ids.length === 0" class="empty-hint-small">从右侧选择因子</div>
                <div v-else class="factor-chips">
                  <div v-for="fid in templateForm.factor_ids" :key="fid" class="factor-chip selected">
                    <span class="factor-name">{{ factors.find(f => f.id === fid)?.name }}</span>
                    <button class="chip-remove" @click="removeFactorFromForm(fid)">×</button>
                  </div>
                </div>
              </div>
              <div class="picker-available">
                <div class="picker-title">可选因子（{{ availableFactors.length }}个）</div>
                <input v-model="factorSearchKeyword" class="factor-search-input" placeholder="🔍 搜索因子名称..." />
                <div class="factor-list-scroll">
                  <div
                    v-for="f in availableFactors"
                    :key="f.id"
                    class="factor-list-item"
                    @click="toggleFactorInForm(f.id)"
                  >
                    <span class="factor-name">{{ f.name }}</span>
                    <span class="factor-type">{{ getFieldTypeLabel(f.field_type) }}</span>
                    <span class="factor-add">+</span>
                  </div>
                  <div v-if="availableFactors.length === 0" class="empty-hint-small">
                    所有因子都已添加
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-outline" @click="showTemplateModal = false">取消</button>
          <button class="btn-primary" @click="saveTemplate">{{ editingTemplate ? '保存修改' : '确认创建' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.schema-manage-page { padding: 16px 24px; }

/* 页面头部 */
.page-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 16px; }
.page-title { font-size: 20px; font-weight: 700; color: #1E293B; margin: 0 0 4px 0; }
.page-desc { font-size: 13px; color: #94A3B8; margin: 0; }

/* Tab切换器 */
.tab-switcher { display: flex; background: #EEF2FF; border-radius: 10px; padding: 5px; gap: 4px; border: 2px solid #C7D2FE; }
.tab-btn { padding: 10px 28px; border: none; background: transparent; color: #6366F1; font-size: 14px; font-weight: 600; border-radius: 7px; cursor: pointer; transition: all 0.2s; }
.tab-btn:hover { background: rgba(255,255,255,0.6); }
.tab-btn.active { background: linear-gradient(135deg, #6366F1, #4F46E5); color: #fff; font-weight: 700; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.4); }

.tab-content { min-height: 400px; }

/* 卡片 */
.card { background: #fff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px; }
.card-header { display: flex; align-items: center; padding: 16px 20px; border-bottom: 1px solid #F1F5F9; gap: 12px; }
.card-title { font-size: 16px; font-weight: 700; color: #1E293B; }
.card-subtitle { font-size: 13px; color: #94A3B8; }
.card-body { padding: 20px; }

/* 按钮 */
.btn-primary { padding: 8px 18px; background: #4F46E5; color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-primary:hover { background: #4338CA; }
.btn-header { margin-left: auto; padding: 8px 20px; font-size: 13px; }
.btn-outline { padding: 8px 18px; background: #fff; color: #475569; border: 1px solid #CBD5E1; border-radius: 8px; font-size: 14px; cursor: pointer; }
.btn-link { background: none; border: none; color: #4F46E5; cursor: pointer; font-size: 13px; margin-right: 8px; padding: 0; }
.btn-link:hover { text-decoration: underline; }
.btn-danger { color: #EF4444; }

/* 操作按钮 */
.action-btns { display: flex; gap: 8px; align-items: center; }
.btn-action { padding: 4px 14px; border-radius: 6px; font-size: 12px; font-weight: 500; cursor: pointer; border: 1px solid transparent; transition: all 0.15s; }
.btn-edit { background: #EEF2FF; color: #4F46E5; border-color: #C7D2FE; }
.btn-edit:hover { background: #E0E7FF; }
.btn-delete { background: #FEF2F2; color: #EF4444; border-color: #FECACA; }
.btn-delete:hover { background: #FEE2E2; }

/* 表格 */
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { text-align: left; padding: 10px 12px; background: #F8FAFC; font-size: 13px; color: #64748B; border-bottom: 1px solid #E2E8F0; }
.data-table td { padding: 12px; border-bottom: 1px solid #F1F5F9; font-size: 14px; color: #334155; }
.tag { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }
.tag-soft { background: #F1F5F9; color: #64748B; }

/* 状态提示 */
.loading-tip, .empty-hint { text-align: center; padding: 40px; color: #94A3B8; font-size: 14px; }
.empty-hint-small { text-align: center; padding: 20px; color: #94A3B8; font-size: 13px; }

/* 模板布局 */
.template-layout { display: flex; gap: 20px; min-height: 400px; }
.template-list { width: 280px; flex-shrink: 0; border-right: 1px solid #F1F5F9; padding-right: 16px; max-height: 600px; overflow-y: auto; }
.template-item { padding: 12px; border-radius: 8px; cursor: pointer; margin-bottom: 8px; border: 1px solid transparent; transition: all 0.2s; }
.template-item:hover { background: #F8FAFC; }
.template-item.active { background: #EEF2FF; border-color: #C7D2FE; }
.template-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.template-item-header strong { font-size: 14px; color: #1E293B; }
.factor-count { font-size: 11px; color: #4F46E5; background: #EEF2FF; padding: 2px 8px; border-radius: 10px; }
.template-item-desc { font-size: 12px; color: #94A3B8; margin-bottom: 6px; }
.template-item-actions { display: flex; gap: 4px; }

.template-detail { flex: 1; padding-left: 8px; }
.detail-header { margin-bottom: 20px; }
.detail-header h3 { margin: 0 0 4px 0; font-size: 18px; color: #1E293B; }
.detail-desc { font-size: 13px; color: #94A3B8; }
.detail-section { margin-bottom: 20px; }
.detail-section h4 { font-size: 14px; color: #334155; margin-bottom: 12px; }
.detail-tip { background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 8px; padding: 12px 16px; font-size: 13px; color: #92400E; }
.empty-detail { display: flex; align-items: center; justify-content: center; color: #94A3B8; }

/* 因子标签 */
.factor-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.factor-chip { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; background: #F1F5F9; border-radius: 16px; font-size: 13px; }
.factor-chip.selected { background: #EEF2FF; }
.factor-name { color: #1E293B; font-weight: 500; }
.factor-type { font-size: 11px; color: #64748B; background: #fff; padding: 1px 6px; border-radius: 8px; }
.chip-remove { background: none; border: none; color: #94A3B8; cursor: pointer; font-size: 16px; padding: 0 2px; line-height: 1; }
.chip-remove:hover { color: #EF4444; }

/* 弹窗 - 修复透明问题 */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(15, 23, 42, 0.6) !important;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999 !important;
  backdrop-filter: blur(2px);
}
.modal {
  background: #fff !important;
  border-radius: 12px;
  width: 480px;
  max-width: 90vw;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  z-index: 10000;
}
.modal-large { width: 720px; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #F1F5F9; }
.modal-header h3 { margin: 0; font-size: 16px; color: #1E293B; }
.modal-close { background: none; border: none; font-size: 24px; cursor: pointer; color: #94A3B8; }
.modal-body { padding: 20px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 20px; border-top: 1px solid #F1F5F9; }

/* 表单 */
.form-group { margin-bottom: 16px; }
.form-group label { display: block; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 6px; }
.required { color: #EF4444; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #CBD5E1; border-radius: 8px; font-size: 14px; box-sizing: border-box; }
.form-input:focus { outline: none; border-color: #4F46E5; }

/* 因子选择器 */
.factor-picker { display: flex; gap: 12px; border: 1px solid #E2E8F0; border-radius: 8px; overflow: hidden; }
.picker-selected, .picker-available { flex: 1; padding: 12px; }
.picker-selected { background: #F8FAFC; border-right: 1px solid #E2E8F0; }
.picker-title { font-size: 12px; font-weight: 600; color: #64748B; margin-bottom: 8px; }
.factor-search-input { width: 100%; padding: 6px 10px; border: 1px solid #E2E8F0; border-radius: 6px; font-size: 12px; margin-bottom: 8px; box-sizing: border-box; }
.factor-search-input:focus { outline: none; border-color: #4F46E5; }
.factor-list-scroll { max-height: 200px; overflow-y: auto; }
.factor-list-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; transition: background 0.15s; }
.factor-list-item:hover { background: #EEF2FF; }
.factor-list-item .factor-add { margin-left: auto; color: #4F46E5; font-weight: bold; }
</style>
