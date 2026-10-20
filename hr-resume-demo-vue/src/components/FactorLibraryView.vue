<script setup>
import { ref, onMounted, inject } from 'vue'
import { factorApi } from '../api/index.js'
import { getStoredUser } from '../api/index.js'

const navigateTo = inject('navigateTo')
const showAlert = inject('showAlert')
const showConfirm = inject('showConfirm')
const currentUser = getStoredUser()
const canEdit = currentUser?.role === 'super_admin' || currentUser?.role === 'maintainer'

const factors = ref([])
const fieldTypes = ref([])
const loading = ref(false)
const showModal = ref(false)
const editingFactor = ref(null)
const form = ref({ name: '', field_type: '', description: '' })

async function loadData() {
  loading.value = true
  try {
    const [list, types] = await Promise.all([factorApi.list(), factorApi.fieldTypes()])
    factors.value = list
    fieldTypes.value = types
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
  editingFactor.value = null
  form.value = { name: '', field_type: 'skill', description: '' }
  showModal.value = true
}

function openEdit(factor) {
  editingFactor.value = factor
  form.value = { name: factor.name, field_type: factor.field_type, description: factor.description || '' }
  showModal.value = true
}

async function save() {
  if (!form.value.name.trim()) {
    showAlert('请输入因子名称', 'warning')
    return
  }
  if (!form.value.field_type) {
    showAlert('请选择字段类型', 'warning')
    return
  }
  try {
    if (editingFactor.value) {
      await factorApi.update(editingFactor.value.id, form.value)
    } else {
      await factorApi.create(form.value)
    }
    showModal.value = false
    loadData()
  } catch (e) {
    showAlert('保存失败: ' + e.message, 'error')
  }
}

async function remove(factor) {
  const confirmed = await showConfirm(`确定删除因子「${factor.name}」吗？`, '删除确认', 'warning')
  if (!confirmed) return
  try {
    await factorApi.delete(factor.id)
    loadData()
  } catch (e) {
    showAlert('删除失败: ' + e.message, 'error')
  }
}

onMounted(loadData)
</script>

<template>
  <div class="page-view">
    <div class="card">
      <div class="card-header">
        <span class="card-title">岗位要求因子库</span>
        <span class="card-subtitle">维护组预定义字段和类型，可组合成岗位模板</span>
        <button v-if="canEdit" class="btn-primary btn-header" @click="openAdd">
          + 新增因子
        </button>
      </div>
      <div class="card-body">
        <div v-if="loading" class="loading-tip">加载中...</div>
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
                  <button v-if="canEdit" class="btn-action btn-edit" @click="openEdit(f)">编辑</button>
                  <button v-if="canEdit" class="btn-action btn-delete" @click="remove(f)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingFactor ? '编辑因子' : '新增因子' }}</h3>
          <button class="modal-close" @click="showModal = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>因子名称 <span class="required">*</span></label>
            <input v-model="form.name" class="form-input" placeholder="如：学历、工作年限、Python技能" />
          </div>
          <div class="form-group">
            <label>字段类型 <span class="required">*</span></label>
            <select v-model="form.field_type" class="form-input">
              <option v-for="t in fieldTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>说明</label>
            <textarea v-model="form.description" class="form-input" rows="3" placeholder="因子的用途说明（可选）"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-outline" @click="showModal = false">取消</button>
          <button class="btn-primary" @click="save">{{ editingFactor ? '保存修改' : '确认新增' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-view { padding: 16px 24px; }
.card { background: #fff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px; }
.card-header { display: flex; align-items: center; padding: 16px 20px; border-bottom: 1px solid #F1F5F9; gap: 12px; }
.card-title { font-size: 16px; font-weight: 700; color: #1E293B; }
.card-subtitle { font-size: 13px; color: #94A3B8; }
.card-body { padding: 20px; }
.btn-primary { padding: 8px 18px; background: #4F46E5; color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-primary:hover { background: #4338CA; }
.btn-header { margin-left: auto; padding: 8px 20px; font-size: 13px; }
.btn-outline { padding: 8px 18px; background: #fff; color: #475569; border: 1px solid #CBD5E1; border-radius: 8px; font-size: 14px; cursor: pointer; }
.btn-link { background: none; border: none; color: #4F46E5; cursor: pointer; font-size: 13px; margin-right: 8px; padding: 0; }
.btn-link:hover { text-decoration: underline; }
.btn-danger { color: #EF4444; }
.action-btns { display: flex; gap: 8px; align-items: center; }
.btn-action { padding: 4px 14px; border-radius: 6px; font-size: 12px; font-weight: 500; cursor: pointer; border: 1px solid transparent; transition: all 0.15s; }
.btn-edit { background: #EEF2FF; color: #4F46E5; border-color: #C7D2FE; }
.btn-edit:hover { background: #E0E7FF; }
.btn-delete { background: #FEF2F2; color: #EF4444; border-color: #FECACA; }
.btn-delete:hover { background: #FEE2E2; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { text-align: left; padding: 10px 12px; background: #F8FAFC; font-size: 13px; color: #64748B; border-bottom: 1px solid #E2E8F0; }
.data-table td { padding: 12px; border-bottom: 1px solid #F1F5F9; font-size: 14px; color: #334155; }
.tag { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }
.tag-soft { background: #F1F5F9; color: #64748B; }
.loading-tip, .empty-hint { text-align: center; padding: 40px; color: #94A3B8; font-size: 14px; }
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 12px; width: 480px; max-width: 90vw; max-height: 90vh; overflow-y: auto; }
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
</style>
