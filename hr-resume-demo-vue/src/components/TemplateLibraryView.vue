<script setup>
import { ref, onMounted, computed, inject } from 'vue'
import { positionTemplateApi, factorApi } from '../api/index.js'
import { getStoredUser } from '../api/index.js'

const navigateTo = inject('navigateTo')
const showAlert = inject('showAlert')
const showConfirm = inject('showConfirm')
const currentUser = getStoredUser()
const canEdit = currentUser?.role === 'super_admin' || currentUser?.role === 'maintainer'

const templates = ref([])
const allFactors = ref([])
const fieldTypes = ref([])
const loading = ref(false)
const selectedTemplateId = ref(null)
const showModal = ref(false)
const editingTemplate = ref(null)
const form = ref({ name: '', description: '', factor_ids: [] })
const showFactorPicker = ref(false)

const selectedTemplate = computed(() => templates.value.find(t => t.id === selectedTemplateId.value))

async function loadData() {
  loading.value = true
  try {
    const [tpls, factors, types] = await Promise.all([
      positionTemplateApi.list(),
      factorApi.list(),
      factorApi.fieldTypes()
    ])
    templates.value = tpls
    allFactors.value = factors
    fieldTypes.value = types
    if (tpls.length > 0 && !selectedTemplateId.value) {
      selectedTemplateId.value = tpls[0].id
    }
  } catch (e) {
    showAlert('加载失败: ' + e.message, 'error')
  } finally {
    loading.value = false
  }
}

function getFieldTypeLabel(type) {
  const found = fieldTypes.value.find(t => t.value === type)
  return found ? found.label : type
}

function openAdd() {
  editingTemplate.value = null
  form.value = { name: '', description: '', factor_ids: [] }
  showModal.value = true
}

function openEdit(tpl) {
  editingTemplate.value = tpl
  form.value = {
    name: tpl.name,
    description: tpl.description || '',
    factor_ids: tpl.factors.map(f => f.id)
  }
  showModal.value = true
}

async function save() {
  if (!form.value.name.trim()) {
    showAlert('请输入模板名称', 'warning')
    return
  }
  try {
    if (editingTemplate.value) {
      await positionTemplateApi.update(editingTemplate.value.id, form.value)
    } else {
      await positionTemplateApi.create(form.value)
    }
    showModal.value = false
    await loadData()
  } catch (e) {
    showAlert('保存失败: ' + e.message, 'error')
  }
}

async function remove(tpl) {
  if (tpl.is_default) {
    showAlert('系统默认模板不可删除', 'warning')
    return
  }
  const confirmed = await showConfirm(`确定删除模板「${tpl.name}」吗？`, '删除确认', 'warning')
  if (!confirmed) return
  try {
    await positionTemplateApi.delete(tpl.id)
    if (selectedTemplateId.value === tpl.id) {
      selectedTemplateId.value = null
    }
    await loadData()
  } catch (e) {
    showAlert('删除失败: ' + e.message, 'error')
  }
}

// 因子选择器
const availableFactors = computed(() => {
  const selectedIds = form.value.factor_ids
  return allFactors.value.filter(f => !selectedIds.includes(f.id))
})

function toggleFactor(factorId) {
  const idx = form.value.factor_ids.indexOf(factorId)
  if (idx >= 0) {
    form.value.factor_ids.splice(idx, 1)
  } else {
    form.value.factor_ids.push(factorId)
  }
}

function removeFactorFromTemplate(factorId) {
  const idx = form.value.factor_ids.indexOf(factorId)
  if (idx >= 0) {
    form.value.factor_ids.splice(idx, 1)
  }
}

onMounted(loadData)
</script>

<template>
  <div class="page-view">
    <div class="card">
      <div class="card-header">
        <span class="card-title">岗位模板库</span>
        <span class="card-subtitle">由因子组合而成，可快速应用到岗位Schema配置</span>
        <button v-if="canEdit" class="btn-primary" style="margin-left: auto;" @click="openAdd">
          + 新建模板
        </button>
      </div>
      <div class="card-body">
        <div v-if="loading" class="loading-tip">加载中...</div>
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
                <span v-if="tpl.is_default" class="default-badge">系统默认</span>
                <span class="factor-count">{{ tpl.factor_count }}个因子</span>
              </div>
              <div class="template-item-desc">{{ tpl.description || '暂无说明' }}</div>
              <div class="template-item-actions" v-if="canEdit">
                <button class="btn-link" @click.stop="openEdit(tpl)">编辑</button>
                <button v-if="!tpl.is_default" class="btn-link btn-danger" @click.stop="remove(tpl)">删除</button>
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

    <!-- 新建/编辑模板弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3>{{ editingTemplate ? '编辑模板' : '新建模板' }}</h3>
          <button class="modal-close" @click="showModal = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>模板名称 <span class="required">*</span></label>
            <input v-model="form.name" class="form-input" placeholder="如：技术岗通用模板、产品经理模板" />
          </div>
          <div class="form-group">
            <label>模板说明</label>
            <textarea v-model="form.description" class="form-input" rows="2" placeholder="模板适用场景说明（可选）"></textarea>
          </div>
          <div class="form-group">
            <label>选择因子（已选 {{ form.factor_ids.length }} 个）</label>
            <div class="factor-picker">
              <div class="picker-selected">
                <div class="picker-title">已选因子</div>
                <div v-if="form.factor_ids.length === 0" class="empty-hint-small">从右侧选择因子</div>
                <div v-else class="factor-chips">
                  <div v-for="fid in form.factor_ids" :key="fid" class="factor-chip selected">
                    <span class="factor-name">{{ allFactors.find(f => f.id === fid)?.name }}</span>
                    <button class="chip-remove" @click="removeFactorFromTemplate(fid)">×</button>
                  </div>
                </div>
              </div>
              <div class="picker-available">
                <div class="picker-title">可选因子（{{ availableFactors.length }}个）</div>
                <div class="factor-list-scroll">
                  <div
                    v-for="f in availableFactors"
                    :key="f.id"
                    class="factor-list-item"
                    @click="toggleFactor(f.id)"
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
          <button class="btn-outline" @click="showModal = false">取消</button>
          <button class="btn-primary" @click="save">{{ editingTemplate ? '保存修改' : '确认创建' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-view { padding: 20px; }
.card { background: #fff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px; }
.card-header { display: flex; align-items: center; padding: 16px 20px; border-bottom: 1px solid #F1F5F9; gap: 12px; }
.card-title { font-size: 16px; font-weight: 700; color: #1E293B; }
.card-subtitle { font-size: 13px; color: #94A3B8; }
.card-body { padding: 20px; }
.btn-primary { padding: 8px 18px; background: #4F46E5; color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-primary:hover { background: #4338CA; }
.btn-outline { padding: 8px 18px; background: #fff; color: #475569; border: 1px solid #CBD5E1; border-radius: 8px; font-size: 14px; cursor: pointer; }
.btn-link { background: none; border: none; color: #4F46E5; cursor: pointer; font-size: 13px; margin-right: 8px; padding: 0; }
.btn-link:hover { text-decoration: underline; }
.btn-danger { color: #EF4444; }
.loading-tip, .empty-hint { text-align: center; padding: 40px; color: #94A3B8; font-size: 14px; }
.empty-hint-small { text-align: center; padding: 20px; color: #94A3B8; font-size: 13px; }

.template-layout { display: flex; gap: 20px; min-height: 400px; }
.template-list { width: 280px; flex-shrink: 0; border-right: 1px solid #F1F5F9; padding-right: 16px; max-height: 600px; overflow-y: auto; }
.template-item { padding: 12px; border-radius: 8px; cursor: pointer; margin-bottom: 8px; border: 1px solid transparent; transition: all 0.2s; }
.template-item:hover { background: #F8FAFC; }
.template-item.active { background: #EEF2FF; border-color: #C7D2FE; }
.template-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.template-item-header strong { font-size: 14px; color: #1E293B; }
.factor-count { font-size: 11px; color: #4F46E5; background: #EEF2FF; padding: 2px 8px; border-radius: 10px; }
.default-badge { font-size: 11px; color: #fff; background: linear-gradient(135deg, #F59E0B, #D97706); padding: 2px 8px; border-radius: 10px; font-weight: 600; }
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

.factor-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.factor-chip { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; background: #F1F5F9; border-radius: 16px; font-size: 13px; }
.factor-chip.selected { background: #EEF2FF; }
.factor-name { color: #1E293B; font-weight: 500; }
.factor-type { font-size: 11px; color: #64748B; background: #fff; padding: 1px 6px; border-radius: 8px; }
.chip-remove { background: none; border: none; color: #94A3B8; cursor: pointer; font-size: 16px; padding: 0 2px; line-height: 1; }
.chip-remove:hover { color: #EF4444; }

.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 12px; width: 480px; max-width: 90vw; max-height: 90vh; overflow-y: auto; }
.modal-large { width: 720px; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #F1F5F9; }
.modal-header h3 { margin: 0; font-size: 16px; }
.modal-close { background: none; border: none; font-size: 24px; cursor: pointer; color: #94A3B8; }
.modal-body { padding: 20px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 20px; border-top: 1px solid #F1F5F9; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 6px; }
.required { color: #EF4444; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #CBD5E1; border-radius: 8px; font-size: 14px; box-sizing: border-box; }
.form-input:focus { outline: none; border-color: #4F46E5; }

.factor-picker { display: flex; gap: 12px; border: 1px solid #E2E8F0; border-radius: 8px; overflow: hidden; }
.picker-selected, .picker-available { flex: 1; padding: 12px; }
.picker-selected { background: #F8FAFC; border-right: 1px solid #E2E8F0; }
.picker-title { font-size: 12px; font-weight: 600; color: #64748B; margin-bottom: 8px; }
.factor-list-scroll { max-height: 200px; overflow-y: auto; }
.factor-list-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; transition: background 0.15s; }
.factor-list-item:hover { background: #EEF2FF; }
.factor-list-item .factor-add { margin-left: auto; color: #4F46E5; font-weight: bold; }
</style>
