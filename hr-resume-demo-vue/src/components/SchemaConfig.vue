<script setup>
import { ref, onMounted, computed, watch, inject } from 'vue'
import { companyApi, positionApi, schemaApi, positionTemplateApi, factorApi } from '../api/index.js'
import { getStoredUser } from '../api/index.js'

const showAlert = inject('showAlert')
const showConfirm = inject('showConfirm')

const props = defineProps({
  companyId: {
    type: Number,
    default: null
  },
  positionId: {
    type: Number,
    default: null
  },
  embedded: {
    type: Boolean,
    default: false
  }
})

const currentUser = getStoredUser()

// 当前选中岗位的完整信息
const currentPosition = computed(() => {
  if (!selectedPosition.value) return null
  return positions.value.find(p => p.id === selectedPosition.value) || null
})

// 是否只读：超管/维护人员可编辑所有；招聘人员只能编辑自己创建的岗位
const isReadOnly = computed(() => {
  if (!currentUser) return true
  if (currentUser.role === 'super_admin') return false
  if (currentUser.role === 'maintainer') return false
  if (!currentPosition.value) return true
  return currentPosition.value.creator_id !== currentUser.id
})

// 权限判断：超管/维护人员可编辑所有；招聘人员只能编辑自己创建的
function canEdit(item) {
  if (!currentUser) return false
  if (currentUser.role === 'super_admin') return true
  if (currentUser.role === 'maintainer') return true
  if (currentUser.role === 'recruiter') {
    // 新添加的字段（未保存）允许编辑
    if (item._isNew) return true
    return item.creator_id === currentUser.id
  }
  return false
}

// 数据状态
const companies = ref([])
const positions = ref([])
const schemaFields = ref([])

// 选中状态
const selectedCompany = ref(null)
const selectedPosition = ref(null)

// 加载状态
const loading = ref(false)
const saving = ref(false)
const error = ref('')

// 草稿状态：是否有未保存的修改
const isDirty = ref(false)

// 岗位模板相关
const templates = ref([])
const showTemplateModal = ref(false)
const selectedTemplateForApply = ref(null)
const templateSearchKeyword = ref('')

// Schema因子选择相关
const showFactorModal = ref(false)
const allFactors = ref([])
const selectedFactorIds = ref([])
const factorSearchKeyword = ref('')
const filteredFactors = computed(() => {
  const kw = factorSearchKeyword.value.trim().toLowerCase()
  if (!kw) return allFactors.value
  return allFactors.value.filter(f => f.name.toLowerCase().includes(kw))
})

const filteredTemplates = computed(() => {
  const kw = templateSearchKeyword.value.trim().toLowerCase()
  if (!kw) return templates.value
  return templates.value.filter(t => t.name.toLowerCase().includes(kw))
})

async function loadTemplates() {
  try {
    templates.value = await positionTemplateApi.list()
  } catch (e) {
    console.error('加载模板失败:', e)
  }
}

async function loadFactors() {
  try {
    allFactors.value = await factorApi.list()
  } catch (e) {
    console.error('加载因子库失败:', e)
  }
}

function openFactorModal() {
  selectedFactorIds.value = []
  factorSearchKeyword.value = ''
  showFactorModal.value = true
}

function toggleFactor(factorId) {
  const idx = selectedFactorIds.value.indexOf(factorId)
  if (idx >= 0) {
    selectedFactorIds.value.splice(idx, 1)
  } else {
    selectedFactorIds.value.push(factorId)
  }
}

function isFactorSelected(factorId) {
  return selectedFactorIds.value.includes(factorId)
}

// 确认添加选中的因子为Schema字段（追加到现有字段后面）
function confirmAddFactors() {
  if (selectedFactorIds.value.length === 0) {
    showAlert('请至少选择一个因子', 'warning')
    return
  }
  const selectedFactors = allFactors.value.filter(f => selectedFactorIds.value.includes(f.id))
  const startOrder = schemaFields.value.length + 1
  const newFields = selectedFactors.map((f, i) => ({
    field_name: f.name,
    field_type: f.field_type || '文本',
    requirement: '',
    is_hard: false,
    weight: 10,
    sort_order: startOrder + i,
    creator_id: currentUser?.id,
    _isNew: true
  }))
  schemaFields.value = [...schemaFields.value, ...newFields]
  isDirty.value = true
  showFactorModal.value = false
  showAlert(`已添加 ${newFields.length} 个因子到岗位需求，请填写匹配要求和权重后保存`, 'success')
}

// 全选当前搜索过滤后的因子
function selectAllFiltered() {
  const filteredIds = filteredFactors.value.map(f => f.id)
  filteredIds.forEach(id => {
    if (!selectedFactorIds.value.includes(id)) {
      selectedFactorIds.value.push(id)
    }
  })
}

// 取消所有选择
function clearAllSelection() {
  selectedFactorIds.value = []
}

// 应用模板：将模板中的因子转换为Schema字段
async function applyTemplate(tpl) {
  if (!tpl || !tpl.factors || tpl.factors.length === 0) {
    showAlert('该模板没有包含任何因子', 'warning')
    return
  }
  if (isDirty.value) {
    const confirmed = await showConfirm('当前有未保存的修改，应用模板将覆盖所有字段，确定继续吗？', '应用模板确认', 'warning')
    if (!confirmed) return
  }
  // 将因子转换为Schema字段（要求和权重由用户自己填写）
  schemaFields.value = tpl.factors.map((f, i) => ({
    field_name: f.name,
    field_type: f.field_type || '文本',
    requirement: '',
    is_hard: false,
    weight: 10,
    sort_order: i + 1,
    creator_id: currentUser?.id,
    _isNew: true
  }))
  isDirty.value = true
  showTemplateModal.value = false
  selectedTemplateForApply.value = null
  templateSearchKeyword.value = ''
}

// 编辑弹窗状态
const showEditModal = ref(false)
const editingField = ref(null)
const editForm = ref({
  field_name: '',
  field_type: '枚举',
  requirement: '',
  is_hard: false,
  weight: 10,
  sort_order: 0
})

// 默认模板
const DEFAULT_TEMPLATE = [{'field_name': '学历', 'field_type': '枚举', 'requirement': '本科及以上', 'is_hard': true, 'weight': 20, 'sort_order': 1}, {'field_name': '工作年限', 'field_type': '数字', 'requirement': '3年以上', 'is_hard': false, 'weight': 15, 'sort_order': 2}, {'field_name': '核心技能', 'field_type': '多选', 'requirement': 'Python, SQL', 'is_hard': false, 'weight': 25, 'sort_order': 3}, {'field_name': '行业经验', 'field_type': '单选', 'requirement': '互联网 / 金融', 'is_hard': false, 'weight': 10, 'sort_order': 4}, {'field_name': '项目经历', 'field_type': '多选', 'requirement': '数据平台, 用户增长', 'is_hard': false, 'weight': 20, 'sort_order': 5}, {'field_name': '证书', 'field_type': '多选', 'requirement': 'NPDP, PMP', 'is_hard': false, 'weight': 10, 'sort_order': 6}]

// 是否为草稿模式（embedded且没有positionId，新增岗位时的临时配置）
const isDraftMode = computed(() => props.embedded && !props.positionId)

// 加载公司列表
async function loadCompanies() {
  try {
    companies.value = await companyApi.list()
    if (props.embedded && props.companyId) {
      // embedded模式：自动选中传入的公司
      selectedCompany.value = props.companyId
      if (props.positionId) {
        // 有positionId：加载岗位列表并选中对应岗位
        await loadPositions()
        selectedPosition.value = props.positionId
        await loadSchemaFields()
      } else {
        // 草稿模式（没有positionId）：不加载岗位列表，直接默认加载所有因子
        positions.value = []
        selectedPosition.value = null
        await loadAllFactorsAsDefault()
      }
    } else if (companies.value.length > 0) {
      selectedCompany.value = companies.value[0].id
      await loadPositions()
    }
  } catch (e) {
    error.value = '加载公司列表失败: ' + e.message
  }
}

// 草稿模式：加载所有因子作为默认岗位需求
async function loadAllFactorsAsDefault() {
  try {
    if (allFactors.value.length === 0) {
      allFactors.value = await factorApi.list()
    }
    if (allFactors.value.length > 0) {
      // 获取当前选中公司的所在城市，用于工作地区因子的默认值
      const currentCompany = companies.value.find(c => c.id === selectedCompany.value)
      const companyCity = currentCompany?.city || '上海'

      schemaFields.value = allFactors.value.map((f, i) => {
        // 工作地区因子：默认填充公司所在城市
        const isWorkLocation = f.name && (f.name.includes('工作地区') || f.name.includes('地区') || f.name.includes('城市'))
        return {
          field_name: f.name,
          field_type: f.field_type || '文本',
          requirement: isWorkLocation ? companyCity : '',
          is_hard: false,
          weight: 10,
          sort_order: i + 1,
          creator_id: currentUser?.id,
          _isNew: true
        }
      })
      isDirty.value = true
    }
  } catch (e) {
    console.error('加载默认因子失败:', e)
  }
}

// 加载岗位列表
async function loadPositions() {
  if (!selectedCompany.value) return
  try {
    positions.value = await positionApi.list({ company_id: selectedCompany.value })
    if (positions.value.length > 0) {
      selectedPosition.value = positions.value[0].id
      await loadSchemaFields()
    } else {
      positions.value = []
      schemaFields.value = []
      isDirty.value = false
    }
  } catch (e) {
    error.value = '加载岗位列表失败: ' + e.message
  }
}

// 加载Schema字段
async function loadSchemaFields() {
  if (!selectedPosition.value) return
  loading.value = true
  error.value = ''
  try {
    schemaFields.value = await schemaApi.list(selectedPosition.value)
    isDirty.value = false
  } catch (e) {
    error.value = '加载Schema字段失败: ' + e.message
  } finally {
    loading.value = false
  }
}

// 检查是否有未保存修改，有则提示
async function checkDirtyBeforeSwitch() {
  if (isDirty.value) {
    return await showConfirm('当前有未保存的修改，切换将丢失这些修改，确定继续吗？', '切换确认', 'warning')
  }
  return true
}

// 公司切换
async function onCompanyChange() {
  if (!(await checkDirtyBeforeSwitch())) {
    // 恢复原选中值
    return
  }
  selectedPosition.value = null
  schemaFields.value = []
  isDirty.value = false
  await loadPositions()
}

// 岗位切换
async function onPositionChange() {
  if (!(await checkDirtyBeforeSwitch())) return
  await loadSchemaFields()
}

// 新增字段（打开弹窗）
function openAddModal() {
  editingField.value = null
  editForm.value = {
    field_name: '',
    field_type: '枚举',
    requirement: '',
    is_hard: false,
    weight: 10,
    sort_order: schemaFields.value.length + 1
  }
  showEditModal.value = true
}

// 编辑字段（打开弹窗）
function openEditModal(field) {
  editingField.value = field
  editForm.value = { ...field }
  showEditModal.value = true
}

// 弹窗确定：保存到本地草稿（不提交后端）
function saveField() {
  if (!editForm.value.field_name || !editForm.value.requirement) {
    showAlert('请填写字段名称和匹配要求', 'warning')
    return
  }
  if (editingField.value) {
    // 编辑：更新本地数组中对应项
    const idx = schemaFields.value.findIndex(f => f === editingField.value || f.id === editingField.value.id)
    if (idx >= 0) {
      schemaFields.value[idx] = { ...schemaFields.value[idx], ...editForm.value }
    }
  } else {
    // 新增：push到本地数组（无id，标记为新增）
    schemaFields.value.push({ ...editForm.value, creator_id: currentUser?.id, _isNew: true })
  }
  isDirty.value = true
  showEditModal.value = false
}

// 切换硬性/柔性
function toggleHard(field) {
  field.is_hard = !field.is_hard
  isDirty.value = true
}

// 删除字段（仅从本地草稿移除）
async function deleteField(field) {
  const confirmed = await showConfirm(`确定删除字段"${field.field_name}"吗？`, '删除确认', 'warning')
  if (!confirmed) return
  const idx = schemaFields.value.findIndex(f => f === field || f.id === field.id)
  if (idx >= 0) {
    schemaFields.value.splice(idx, 1)
    isDirty.value = true
  }
}

// 初始化默认模板（替换本地草稿，不提交后端）
async function initDefaults() {
  if (!selectedPosition.value) return
  if (isDirty.value) {
    const confirmed = await showConfirm('当前有未保存的修改，初始化默认模板将覆盖所有字段，确定继续吗？', '初始化确认', 'warning')
    if (!confirmed) return
  }
  const confirmed2 = await showConfirm('确定要为当前岗位初始化默认Schema模板吗？', '初始化确认', 'info')
  if (!confirmed2) return
  schemaFields.value = DEFAULT_TEMPLATE.map((f, i) => ({ ...f, creator_id: currentUser?.id, _isNew: true, sort_order: i + 1 }))
  isDirty.value = true
}

// 保存所有修改到后端
async function saveAll(showNotification = true) {
  if (!selectedPosition.value || !isDirty.value || saving.value) return { success: false, reason: 'no_changes' }
  if (schemaFields.value.length === 0) {
    const confirmed = await showConfirm('当前没有任何Schema字段，保存后将删除所有现有字段，确定继续吗？', '保存确认', 'warning')
    if (!confirmed) return { success: false, reason: 'cancelled' }
  }
  saving.value = true
  error.value = ''
  try {
    // 构造提交数据：去掉前端标记字段，保留id（有id的是更新，无id的是新增）
    const fields = schemaFields.value.map(f => {
      const item = {
        field_name: f.field_name,
        field_type: f.field_type,
        requirement: f.requirement,
        is_hard: f.is_hard,
        weight: f.weight,
        sort_order: f.sort_order
      }
      if (f.id && !f._isNew) item.id = f.id
      return item
    })
    const result = await schemaApi.batchSave(selectedPosition.value, fields)
    schemaFields.value = result
    isDirty.value = false
    if (showNotification) {
      showAlert('保存成功！系统正在后台自动匹配所有简历，请稍后在匹配结果页面查看。', 'success', '保存成功')
    }
    return { success: true }
  } catch (e) {
    error.value = '保存失败: ' + e.message
    if (showNotification) {
      showAlert('保存失败: ' + e.message, 'error')
    }
    return { success: false, reason: e.message }
  } finally {
    saving.value = false
  }
}

// 暴露给父组件的方法
defineExpose({
  saveAll,
  isDirty: () => isDirty.value,
  hasFields: () => schemaFields.value.length > 0,
  allRequirementsFilled: () => allRequirementsFilled.value,
  getUnfilledFieldNames: () => unfilledFields.value.map(f => f.field_name)
})

// 计算总权重
function totalWeight() {
  return schemaFields.value.reduce((sum, item) => sum + (item.weight || 0), 0)
}

// 检查所有字段的要求是否都填写完整
const allRequirementsFilled = computed(() => {
  if (schemaFields.value.length === 0) return false
  return schemaFields.value.every(item => item.requirement && item.requirement.trim() !== '')
})

// 获取未填写要求的字段列表
const unfilledFields = computed(() => {
  return schemaFields.value.filter(item => !item.requirement || item.requirement.trim() === '')
})

// 计算权重百分比
function weightPercent(weight) {
  const total = totalWeight()
  if (total === 0) return '0%'
  return (weight / total * 100).toFixed(1) + '%'
}

// 权重颜色
const weightColors = ['#4F6EF7', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16', '#F97316', '#6366F1', '#14B8A6', '#A855F7']
function weightColor(index) {
  return weightColors[index % weightColors.length]
}

// 权重滑块变化
function onWeightSliderChange(e) {
  editForm.value.weight = parseInt(e.target.value)
}

onMounted(() => {
  loadCompanies()
  loadTemplates()
  loadFactors()
})

// embedded模式下，监听外部传入的positionId变化，自动切换岗位
// 记录上一次的positionId，用于区分"草稿转正式"和"切换岗位"
let lastPositionId = null
watch(() => props.positionId, (newId) => {
  if (!props.embedded || !newId || newId === selectedPosition.value) return
  const wasDraft = !lastPositionId  // 之前是草稿模式（没有positionId）
  lastPositionId = newId
  selectedPosition.value = newId
  if (wasDraft) {
    // 草稿转正式：保留用户在草稿中配置的字段，不加载后端数据
    // isDirty保持为true，这样保存时会把草稿中的字段保存到后端
    isDirty.value = schemaFields.value.length > 0
  } else {
    // 切换岗位：加载新岗位的Schema字段
    loadSchemaFields()
  }
})

// embedded模式下，监听companyId变化，草稿模式下切换公司时重新加载默认因子
watch(() => props.companyId, (newCompanyId) => {
  if (!props.embedded || props.positionId || !newCompanyId) return
  // 草稿模式下切换公司：更新selectedCompany，重新加载默认因子（工作地区默认值会更新）
  selectedCompany.value = newCompanyId
  loadAllFactorsAsDefault()
})
</script>

<template>
  <div class="card" :class="{ 'card-embedded': embedded }">
    <div v-if="!embedded" class="card-header">
      <span class="step-num">1</span>
      <span class="card-title">JD Schema 手工配置</span>
      <span class="card-subtitle">定义岗位字段、硬性规则和匹配权重</span>
    </div>
    <div class="card-body">
      <!-- 错误提示 -->
      <div v-if="error" style="color:#EF4444; font-size:12px; margin-bottom:10px; padding:8px; background:#FEF2F2; border-radius:6px;">
        {{ error }}
      </div>

      <!-- 选择器工具栏 -->
      <div class="schema-toolbar">
        <template v-if="!embedded">
          <select class="schema-select" v-model="selectedCompany" @change="onCompanyChange">
            <option :value="null">选择公司</option>
            <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <select class="schema-select" v-model="selectedPosition" @change="onPositionChange">
            <option :value="null">选择岗位</option>
            <option v-for="p in positions" :key="p.id" :value="p.id">
              {{ p.name }}（{{ p.status }}）
            </option>
          </select>
        </template>
        <button v-if="!isReadOnly" class="btn-gradient btn-gradient-purple" @click="showTemplateModal = true">
          📋 应用模板
        </button>
        <button v-if="!isReadOnly" class="btn-gradient btn-gradient-blue" @click="openFactorModal">
          🧩 选择Schema因子
        </button>
        <button v-if="!isReadOnly" class="btn-gradient btn-gradient-cyan" @click="openAddModal">
          + 新增字段
        </button>
        <!-- 保存按钮：有修改且所有要求填写完整时高亮可点击，否则灰色禁用；embedded模式下隐藏，由父组件统一保存 -->
        <button
          v-if="!isReadOnly && !embedded"
          class="toolbar-btn btn-save"
          :class="{ 'btn-save-active': isDirty && allRequirementsFilled, 'btn-save-disabled': !(isDirty && allRequirementsFilled) }"
          :disabled="!(isDirty && allRequirementsFilled) || saving"
          @click="saveAll"
          :title="!isDirty ? '暂无修改' : (!allRequirementsFilled ? '还有字段未填写匹配要求' : '保存配置')"
        >
          {{ saving ? '保存中...' : (!isDirty ? '无修改' : (!allRequirementsFilled ? '待填写要求' : '保存配置')) }}
        </button>
      </div>

      <!-- 未保存提示 -->
      <div v-if="isDirty && !isReadOnly" class="dirty-tip" :class="{ 'dirty-tip-warning': !allRequirementsFilled }">
        <span class="dirty-dot"></span>
        <template v-if="!allRequirementsFilled">
          还有 <strong>{{ unfilledFields.length }}</strong> 个字段未填写匹配要求（{{ unfilledFields.map(f => f.field_name).join('、') }}），填写完整后才能保存
        </template>
        <template v-else>
          有未保存的修改，点击下方「保存全部」后生效并自动触发匹配
        </template>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" style="text-align:center; padding:40px; color:#94A3B8;">
        加载中...
      </div>

      <!-- 空状态 -->
      <div v-else-if="schemaFields.length === 0" style="text-align:center; padding:40px; color:#94A3B8;">
        {{ isDraftMode ? '暂无配置，可点击上方「应用模板」或「选择Schema因子」开始配置' : '暂无Schema字段，请新增字段或选择Schema因子' }}
      </div>

      <!-- Schema表格 -->
      <table v-else class="schema-table">
        <thead>
          <tr>
            <th>字段</th>
            <th>类型</th>
            <th>要求</th>
            <th>是否硬性</th>
            <th>权重</th>
            <th>创建者</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in schemaFields" :key="item.id || ('new_' + index)">
            <td>
              {{ item.field_name }}
              <span v-if="item._isNew" class="tag-new">新</span>
            </td>
            <td>{{ item.field_type }}</td>
            <td>
              <input
                v-if="canEdit(item)"
                v-model="item.requirement"
                class="inline-edit-input"
                placeholder="请输入匹配要求"
                @input="isDirty = true"
              />
              <span v-else>{{ item.requirement }}</span>
            </td>
            <td>
              <label v-if="canEdit(item)" class="inline-hard-toggle" @click="toggleHard(item)">
                <input type="checkbox" :checked="item.is_hard" class="hard-checkbox" />
                <span :class="item.is_hard ? 'tag-hard' : 'tag-soft'">
                  {{ item.is_hard ? '硬性' : '柔性' }}
                </span>
              </label>
              <span v-else :class="item.is_hard ? 'tag-hard' : 'tag-soft'">
                {{ item.is_hard ? '硬性' : '柔性' }}
              </span>
            </td>
            <td>
              <div v-if="canEdit(item)" class="inline-weight-edit">
                <input
                  type="number"
                  v-model.number="item.weight"
                  class="weight-input"
                  min="0"
                  max="100"
                  @input="isDirty = true"
                />
              </div>
              <div v-else>
                {{ item.weight }}
              </div>
            </td>
            <td style="font-size:12px; color:#64748B;">{{ item.creator_name || (item._isNew ? '待保存' : '系统') }}</td>
            <td style="white-space:nowrap;">
              <template v-if="canEdit(item)">
                <button @click="deleteField(item)" style="background:none; border:none; color:#EF4444; font-size:12px; cursor:pointer;">
                  删除
                </button>
              </template>
              <span v-else style="font-size:12px; color:#94A3B8;">只读</span>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 权重说明与可视化 -->
      <div v-if="schemaFields.length > 0" class="weight-explain-card">
        <div class="weight-explain-header">
          <span class="weight-explain-title">权重说明与占比分析</span>
          <span class="weight-explain-tip">权重决定各维度在总分中的占比，权重越高该维度越重要</span>
        </div>
        <div class="formula-box">
          <div class="formula-label">匹配总分计算公式：</div>
          <div class="formula-content">
            <span class="formula-math">总分 = Σ ( 各维度得分 × 该维度权重 ÷ 总权重 ) × 100</span>
          </div>
          <div class="formula-example">
            <strong>示例：</strong>学历权重20、技能权重30、经验权重25、项目权重25（总权重100）。
            若某候选人学历得80分、技能得90分、经验得70分、项目得85分，
            则总分 = (80×20 + 90×30 + 70×25 + 85×25) ÷ 100 = <strong>82.25分</strong>
          </div>
        </div>
        <div class="weight-visualization">
          <div class="weight-viz-title">各维度权重占比（总权重：{{ totalWeight() }}）</div>
          <div class="weight-bars">
            <div v-for="(item, index) in schemaFields" :key="item.id || ('viz_' + index)" class="weight-row">
              <div class="weight-row-label">
                <span class="weight-dot" :style="{ background: weightColor(index) }"></span>
                <span class="weight-field-name">{{ item.field_name }}</span>
                <span :class="item.is_hard ? 'tag-hard-mini' : 'tag-soft-mini'">{{ item.is_hard ? '硬性' : '柔性' }}</span>
              </div>
              <div class="weight-row-bar">
                <div class="weight-row-fill" :style="{ width: weightPercent(item.weight), background: weightColor(index) }"></div>
              </div>
              <div class="weight-row-value">
                <span class="weight-num">{{ item.weight }}</span>
                <span class="weight-pct">{{ weightPercent(item.weight) }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="hard-rule-tip">
          <strong>硬性规则：</strong>勾选"硬性淘汰"的字段，若候选人不满足要求将直接被淘汰（总分记0），不再参与权重计算。
          建议将学历、工作年限等基础门槛设为硬性条件，将技能、项目经验等设为柔性条件参与打分。
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ editingField ? '编辑字段' : '新增字段' }}</h3>
          <button @click="showEditModal = false" style="background:none; border:none; font-size:20px; cursor:pointer; color:#64748B;">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>字段名称</label>
            <input v-model="editForm.field_name" type="text" placeholder="如：学历、工作年限、核心技能" />
          </div>
          <div class="form-group">
            <label>字段类型</label>
            <select v-model="editForm.field_type">
              <option value="文本">文本</option>
              <option value="枚举">枚举</option>
              <option value="数字">数字</option>
              <option value="多选">多选</option>
              <option value="单选">单选</option>
            </select>
          </div>
          <div class="form-group">
            <label>匹配要求</label>
            <input v-model="editForm.requirement" type="text" placeholder="如：本科及以上、3年以上、Python, SQL" />
          </div>
          <div class="form-group">
            <label>是否硬性淘汰</label>
            <label style="display:inline-flex; align-items:center; gap:6px; cursor:pointer;">
              <input v-model="editForm.is_hard" type="checkbox" />
              不满足则直接淘汰
            </label>
          </div>
          <div class="form-group">
            <label>匹配权重（1-100）</label>
            <div class="weight-input-group">
              <input v-model.number="editForm.weight" type="range" min="1" max="100" class="weight-slider" @input="onWeightSliderChange" />
              <input v-model.number="editForm.weight" type="number" min="1" max="100" class="weight-number-input" />
            </div>
            <div class="weight-input-tip">
              当前权重 <strong>{{ editForm.weight }}</strong>，
              占总权重比例约 <strong>{{ weightPercent(editForm.weight) }}</strong>
              <span v-if="totalWeight() > 0">（总权重 {{ totalWeight() }}）</span>
            </div>
            <div class="weight-input-hint">
              权重越高，该维度在匹配总分中占比越大。建议核心维度（如技能、经验）设较高权重，辅助维度设较低权重。
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-outline" @click="showEditModal = false">取消</button>
          <button class="btn-primary" @click="saveField">确定</button>
        </div>
      </div>
    </div>

  </div>

  <!-- 模板选择弹窗 -->
  <div v-if="showTemplateModal" class="modal-overlay" @click.self="showTemplateModal = false">
    <div class="modal apply-template-modal">
      <div class="modal-header">
        <h3>选择岗位模板</h3>
        <button class="modal-close" @click="showTemplateModal = false">×</button>
      </div>
      <div class="modal-body">
        <div v-if="templates.length === 0" style="text-align:center; padding:30px; color:#94A3B8;">
          暂无可用模板，请先在「Schema配置」→「模板库」中创建模板
        </div>
        <template v-else>
          <div class="template-search-bar">
            <input v-model="templateSearchKeyword" class="template-search-input" placeholder="🔍 搜索模板名称..." />
            <span class="template-count">共 {{ filteredTemplates.length }} 个模板</span>
          </div>
          <div v-if="filteredTemplates.length === 0" class="template-no-result">
            未找到匹配的模板
          </div>
          <div v-else class="template-select-list">
            <div
              v-for="tpl in filteredTemplates"
              :key="tpl.id"
              class="template-select-item"
              :class="{ selected: selectedTemplateForApply === tpl.id }"
              @click="selectedTemplateForApply = tpl.id"
            >
              <div class="tpl-select-header">
                <strong>{{ tpl.name }}</strong>
                <span class="tpl-factor-count">{{ tpl.factor_count }}个因子</span>
              </div>
              <div class="tpl-select-desc">{{ tpl.description || '暂无说明' }}</div>
              <div class="tpl-select-factors">
                <span v-for="f in tpl.factors.slice(0, 5)" :key="f.id" class="tpl-factor-tag">{{ f.name }}</span>
                <span v-if="tpl.factors.length > 5" class="tpl-factor-more">+{{ tpl.factors.length - 5 }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>
      <div class="modal-footer">
        <button class="btn-outline" @click="showTemplateModal = false">取消</button>
        <button
          class="btn-primary"
          :disabled="!selectedTemplateForApply"
          :style="{ opacity: selectedTemplateForApply ? 1 : 0.5, cursor: selectedTemplateForApply ? 'pointer' : 'not-allowed' }"
          @click="applyTemplate(templates.find(t => t.id === selectedTemplateForApply))"
        >
          应用此模板
        </button>
      </div>
    </div>
  </div>

  <!-- Schema因子选择弹窗 -->
  <div v-if="showFactorModal" class="modal-overlay" @click.self="showFactorModal = false">
    <div class="modal factor-select-modal">
      <div class="modal-header">
        <h3>选择Schema因子</h3>
        <button class="modal-close" @click="showFactorModal = false">×</button>
      </div>
      <div class="modal-body">
        <div class="factor-search-bar">
          <input v-model="factorSearchKeyword" class="factor-search-input" placeholder="🔍 搜索因子名称..." />
          <span class="factor-count">已选 {{ selectedFactorIds.length }} / {{ allFactors.length }} 个</span>
        </div>
        <div v-if="allFactors.length > 0" class="factor-actions-bar">
          <button class="factor-action-btn" @click="selectAllFiltered">全选当前结果</button>
          <button class="factor-action-btn" @click="clearAllSelection">取消全选</button>
        </div>
        <div v-if="allFactors.length === 0" style="text-align:center; padding:30px; color:#94A3B8;">
          暂无可用因子，请先在「Schema配置」→「Schema因子」中创建因子
        </div>
        <div v-else-if="filteredFactors.length === 0" class="factor-no-result">
          未找到匹配的因子
        </div>
        <div v-else class="factor-select-grid">
          <div
            v-for="f in filteredFactors"
            :key="f.id"
            class="factor-select-card"
            :class="{ selected: isFactorSelected(f.id) }"
            @click="toggleFactor(f.id)"
          >
            <div class="factor-card-check">
              <span v-if="isFactorSelected(f.id)">✓</span>
            </div>
            <div class="factor-card-info">
              <div class="factor-card-name">{{ f.name }}</div>
              <div class="factor-card-type">{{ f.field_type }}</div>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-outline" @click="showFactorModal = false">取消</button>
        <button
          class="btn-primary"
          :disabled="selectedFactorIds.length === 0"
          :style="{ opacity: selectedFactorIds.length > 0 ? 1 : 0.5, cursor: selectedFactorIds.length > 0 ? 'pointer' : 'not-allowed' }"
          @click="confirmAddFactors"
        >
          添加选中的 {{ selectedFactorIds.length }} 个因子
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed !important;
  top: 0 !important; left: 0 !important; right: 0 !important; bottom: 0 !important;
  background: rgba(15, 23, 42, 0.6) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  z-index: 9999 !important;
  backdrop-filter: blur(2px);
}
.modal-content, .modal {
  background: #fff !important;
  border-radius: 12px;
  width: 480px;
  max-width: 90%;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3) !important;
  z-index: 10000 !important;
}
.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid #E8ECF0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
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
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  font-size: 13px;
  color: #1E293B;
  background: #fff;
}
.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #4F6EF7;
}
.modal-footer {
  padding: 14px 20px;
  border-top: 1px solid #E8ECF0;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-shrink: 0;
}

/* 权重说明卡片 */
.weight-explain-card {
  margin-top: 20px;
  padding: 16px;
  background: #F8FAFC;
  border-radius: 10px;
  border: 1px solid #E2E8F0;
}
.weight-explain-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.weight-explain-title {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
}
.weight-explain-tip {
  font-size: 12px;
  color: #64748B;
}

/* 计算公式 */
.formula-box {
  background: #fff;
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 14px;
  border: 1px solid #E2E8F0;
}
.formula-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
}
.formula-content {
  text-align: center;
  padding: 10px;
  background: #F1F5F9;
  border-radius: 6px;
  margin-bottom: 10px;
}
.formula-math {
  font-family: 'Courier New', monospace;
  font-size: 14px;
  font-weight: 600;
  color: #4F6EF7;
}
.formula-example {
  font-size: 12px;
  color: #64748B;
  line-height: 1.7;
}
.formula-example strong {
  color: #1E293B;
}

/* 权重可视化 */
.weight-visualization {
  background: #fff;
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 14px;
  border: 1px solid #E2E8F0;
}
.weight-viz-title {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 12px;
}
.weight-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.weight-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.weight-row-label {
  width: 140px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.weight-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.weight-field-name {
  font-size: 12px;
  color: #334155;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tag-hard-mini {
  font-size: 10px;
  padding: 1px 5px;
  background: #FEF2F2;
  color: #EF4444;
  border-radius: 3px;
  flex-shrink: 0;
}
.tag-soft-mini {
  font-size: 10px;
  padding: 1px 5px;
  background: #F0FDF4;
  color: #10B981;
  border-radius: 3px;
  flex-shrink: 0;
}
.weight-row-bar {
  flex: 1;
  height: 18px;
  background: #F1F5F9;
  border-radius: 4px;
  overflow: hidden;
}
.weight-row-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
  min-width: 2px;
}
.weight-row-value {
  width: 90px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  flex-shrink: 0;
}
.weight-num {
  font-size: 13px;
  font-weight: 600;
  color: #1E293B;
  min-width: 24px;
  text-align: right;
}
.weight-pct {
  font-size: 11px;
  color: #64748B;
  min-width: 42px;
  text-align: right;
}

/* 硬性规则提示 */
.hard-rule-tip {
  font-size: 12px;
  color: #64748B;
  line-height: 1.7;
  padding: 10px 12px;
  background: #FFFBEB;
  border-radius: 6px;
  border-left: 3px solid #F59E0B;
}
.hard-rule-tip strong {
  color: #92400E;
}

/* 权重输入组 */
.weight-input-group {
  display: flex;
  align-items: center;
  gap: 10px;
}
.weight-slider {
  flex: 1;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: #E2E8F0;
  border-radius: 3px;
  outline: none;
  cursor: pointer;
}
.weight-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #4F6EF7;
  cursor: pointer;
  border: 2px solid #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.weight-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #4F6EF7;
  cursor: pointer;
  border: 2px solid #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.weight-number-input {
  width: 70px;
  padding: 6px 8px;
  border: 1px solid #CBD5E1;
  border-radius: 6px;
  font-size: 13px;
  text-align: center;
}
.weight-input-tip {
  font-size: 12px;
  color: #475569;
  margin-top: 8px;
  padding: 8px 10px;
  background: #EEF2FF;
  border-radius: 6px;
}
.weight-input-tip strong {
  color: #4F6EF7;
}
.weight-input-hint {
  font-size: 11px;
  color: #94A3B8;
  margin-top: 6px;
  line-height: 1.5;
}

/* 保存按钮 */
.btn-save {
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-save-active {
  background: linear-gradient(135deg, #10B981, #059669);
  color: #fff;
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
}
.btn-save-active:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
}
.btn-save-disabled {
  background: #F1F5F9;
  color: #94A3B8;
  cursor: not-allowed;
}

/* 未保存提示 */
.dirty-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  margin: 12px 0;
  background: #FFFBEB;
  border: 1px solid #FDE68A;
  border-radius: 6px;
  font-size: 13px;
  color: #92400E;
}
.dirty-tip-warning {
  background: #FEF2F2;
  border-color: #FECACA;
  color: #991B1B;
}
.dirty-tip-warning .dirty-dot {
  background: #EF4444;
}
.dirty-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #F59E0B;
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 新增字段标记 */
.tag-new {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  background: #DBEAFE;
  color: #1D4ED8;
  font-size: 10px;
  border-radius: 3px;
  font-weight: 600;
}

/* 表格内联编辑样式 */
.inline-edit-input {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid #E2E8F0;
  border-radius: 4px;
  font-size: 12px;
  color: #1E293B;
  background: #fff;
  outline: none;
  transition: border-color 0.2s;
}
.inline-edit-input:focus {
  border-color: #4F6EF7;
  box-shadow: 0 0 0 2px rgba(79, 110, 247, 0.1);
}
.inline-hard-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
}
.hard-checkbox {
  width: 14px;
  height: 14px;
  cursor: pointer;
  accent-color: #4F6EF7;
}
.inline-weight-edit {
  display: flex;
  align-items: center;
  gap: 8px;
}
.weight-input {
  width: 50px;
  padding: 3px 6px;
  border: 1px solid #E2E8F0;
  border-radius: 4px;
  font-size: 12px;
  color: #1E293B;
  background: #fff;
  outline: none;
  text-align: center;
  transition: border-color 0.2s;
}
.weight-input:focus {
  border-color: #4F6EF7;
  box-shadow: 0 0 0 2px rgba(79, 110, 247, 0.1);
}
.weight-input::-webkit-inner-spin-button,
.weight-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

/* 模板选择弹窗 */
.template-select-list { max-height: 400px; overflow-y: auto; }
.template-select-item { padding: 14px; border: 2px solid #E2E8F0; border-radius: 10px; margin-bottom: 10px; cursor: pointer; transition: all 0.2s; }
.template-select-item:hover { border-color: #C7D2FE; background: #F8FAFC; }
.template-select-item.selected { border-color: #4F46E5; background: #EEF2FF; }
.tpl-select-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.tpl-select-header strong { font-size: 15px; color: #1E293B; }
.tpl-factor-count { font-size: 12px; color: #4F46E5; background: #fff; padding: 2px 10px; border-radius: 10px; font-weight: 600; }
.tpl-select-desc { font-size: 13px; color: #64748B; margin-bottom: 8px; }
.tpl-select-factors { display: flex; flex-wrap: wrap; gap: 6px; }
.tpl-factor-tag { font-size: 12px; background: #fff; color: #475569; padding: 2px 8px; border-radius: 8px; border: 1px solid #E2E8F0; }
.tpl-factor-more { font-size: 12px; color: #94A3B8; }

/* 应用模板弹窗 */
.apply-template-modal { width: 600px !important; max-height: 80vh !important; }
.template-search-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.template-search-input { flex: 1; padding: 9px 14px; border: 1px solid #E2E8F0; border-radius: 8px; font-size: 13px; }
.template-search-input:focus { outline: none; border-color: #4F46E5; }
.template-count { font-size: 12px; color: #94A3B8; white-space: nowrap; }
.template-no-result { text-align: center; padding: 30px; color: #94A3B8; font-size: 13px; }
.template-select-list { max-height: 380px; overflow-y: auto; padding-right: 4px; }


/* Schema因子选择弹窗 */
.factor-select-modal { width: 640px !important; max-height: 80vh !important; }
.factor-search-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.factor-search-input { flex: 1; padding: 9px 14px; border: 1px solid #E2E8F0; border-radius: 8px; font-size: 13px; }
.factor-search-input:focus { outline: none; border-color: #4F46E5; }
.factor-count { font-size: 12px; color: #4F46E5; background: #EEF2FF; padding: 4px 12px; border-radius: 10px; font-weight: 600; white-space: nowrap; }
.factor-no-result { text-align: center; padding: 30px; color: #94A3B8; font-size: 13px; }
.factor-actions-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.factor-action-btn {
  padding: 5px 12px;
  background: #F1F5F9;
  color: #475569;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.factor-action-btn:hover { background: #EEF2FF; color: #4F46E5; border-color: #C7D2FE; }
.factor-select-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  max-height: 400px;
  overflow-y: auto;
  padding-right: 4px;
}
.factor-select-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 2px solid #E2E8F0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
  background: #fff;
}
.factor-select-card:hover { border-color: #C7D2FE; background: #F8FAFC; }
.factor-select-card.selected { border-color: #4F46E5; background: #EEF2FF; }
.factor-card-check {
  width: 22px; height: 22px;
  border-radius: 6px;
  border: 2px solid #CBD5E1;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700; color: #fff;
  flex-shrink: 0;
  transition: all 0.15s;
}
.factor-select-card.selected .factor-card-check {
  background: #4F46E5;
  border-color: #4F46E5;
}
.factor-card-info { flex: 1; min-width: 0; }
.factor-card-name { font-size: 13px; font-weight: 600; color: #1E293B; margin-bottom: 2px; }
.factor-card-type { font-size: 11px; color: #64748B; background: #F1F5F9; padding: 1px 8px; border-radius: 4px; display: inline-block; }

@media (max-width: 1279px) {
  .factor-select-grid { grid-template-columns: repeat(2, 1fr); }
  .factor-select-modal { width: 90% !important; max-width: 560px !important; }
}
@media (max-width: 1023px) {
  .factor-select-grid { grid-template-columns: repeat(2, 1fr); max-height: 300px; }
  .factor-select-modal { width: 95% !important; max-width: 480px !important; }
}
/* 工具栏统一按钮样式已移至全局 style.css */

</style>