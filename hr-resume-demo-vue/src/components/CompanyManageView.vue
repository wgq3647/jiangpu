<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { companyApi } from '../api/index.js'
import { getStoredUser } from '../api/index.js'

const navigateTo = inject('navigateTo')
const showAlert = inject('showAlert')
const showConfirm = inject('showConfirm')
const currentUser = getStoredUser()

const loading = ref(false)
const error = ref('')
const companies = ref([])
const deletedCompanies = ref([])
const currentTab = ref('normal') // 'normal' 或 'deleted'

// 公司表单状态
const editingCompany = ref(null)
const showForm = ref(false)
const companyForm = ref({
  name: '',
  description: '',
  status: '合作中',
  email: '',
  city: '',
  address: ''
})
const companySearchKeyword = ref('')

// 常用城市列表
const cityOptions = [
  '北京', '上海', '广州', '深圳', '杭州', '南京', '苏州', '成都', '武汉', '西安',
  '重庆', '天津', '长沙', '郑州', '青岛', '大连', '宁波', '厦门', '福州', '济南',
  '合肥', '南昌', '昆明', '贵阳', '南宁', '兰州', '太原', '石家庄', '沈阳', '长春',
  '哈尔滨', '海口', '三亚', '珠海', '佛山', '东莞', '无锡', '常州', '南通', '徐州',
  '温州', '绍兴', '嘉兴', '金华', '泉州', '漳州', '烟台', '潍坊', '淄博', '洛阳',
  '其他'
]

// 邮箱格式校验
function isValidEmail(email) {
  if (!email || !email.trim()) return true // 邮箱非必填
  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/
  return emailRegex.test(email.trim())
}

const filteredCompanies = computed(() => {
  const list = currentTab.value === 'deleted' ? deletedCompanies.value : companies.value
  const kw = companySearchKeyword.value.trim().toLowerCase()
  if (!kw) return list
  return list.filter(c =>
    c.name.toLowerCase().includes(kw) ||
    (c.description || '').toLowerCase().includes(kw)
  )
})

// 权限判断：超管/维护人员可编辑所有；招聘人员只能编辑自己创建的
function canEdit(item) {
  if (!currentUser) return false
  if (currentUser.role === 'super_admin') return true
  if (currentUser.role === 'maintainer') return true
  if (currentUser.role === 'recruiter') return item.creator_id === currentUser.id
  return false
}

// 加载数据
async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const data = await companyApi.list()
    // 按倒序排列，最新创建的在前面
    companies.value = data.sort((a, b) => (b.id || 0) - (a.id || 0))
    // 加载已删除公司（仅超管/维护人员可见）
    if (currentUser && (currentUser.role === 'super_admin' || currentUser.role === 'maintainer')) {
      try {
        const deletedData = await companyApi.listDeleted()
        deletedCompanies.value = deletedData.sort((a, b) => (b.id || 0) - (a.id || 0))
      } catch (e) {
        deletedCompanies.value = []
      }
    }
  } catch (e) {
    error.value = '加载数据失败: ' + e.message
  } finally {
    loading.value = false
  }
}

// ========== 公司管理 ==========
function openAddCompany() {
  editingCompany.value = null
  companyForm.value = {
    name: '',
    description: '',
    status: '合作中',
    email: '',
    city: '',
    address: ''
  }
  showForm.value = true
}

function openEditCompany(company) {
  editingCompany.value = company
  companyForm.value = {
    name: company.name,
    description: company.description || '',
    status: company.status,
    email: company.email || '',
    city: company.city || '',
    address: company.address || ''
  }
  showForm.value = true
}

function cancelForm() {
  showForm.value = false
  editingCompany.value = null
}

async function saveCompany() {
  if (!companyForm.value.name.trim()) {
    showAlert('请输入公司名称', 'warning')
    return
  }
  // 邮箱格式校验
  if (companyForm.value.email && !isValidEmail(companyForm.value.email)) {
    showAlert('邮箱格式不正确，请输入有效的邮箱地址，如：hr@company.com', 'warning')
    return
  }
  try {
    if (editingCompany.value) {
      await companyApi.update(editingCompany.value.id, companyForm.value)
    } else {
      await companyApi.create(companyForm.value)
    }
    showForm.value = false
    editingCompany.value = null
    await loadData()
  } catch (e) {
    showAlert('保存失败: ' + e.message, 'error')
  }
}

async function deleteCompany(company) {
  const confirmed = await showConfirm(`确定删除公司"${company.name}"吗？\n\n删除后公司将移入回收站，可随时恢复。\n注意：如果该公司下有招聘中岗位，需要先将岗位改为非招聘中状态才能删除。`, '删除确认', 'warning')
  if (!confirmed) return
  try {
    await companyApi.delete(company.id)
    showAlert('删除成功，公司已移入回收站', 'success')
    await loadData()
  } catch (e) {
    showAlert('删除失败: ' + e.message, 'error')
  }
}

// 恢复已删除公司
async function restoreCompany(company) {
  const confirmed = await showConfirm(`确定恢复公司"${company.name}"吗？`, '恢复确认', 'info')
  if (!confirmed) return
  try {
    await companyApi.restore(company.id)
    showAlert('公司恢复成功', 'success')
    await loadData()
  } catch (e) {
    showAlert('恢复失败: ' + e.message, 'error')
  }
}

// 切换tab
function switchTab(tab) {
  currentTab.value = tab
}

// 格式化日期
function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => loadData())
</script>

<template>
  <div class="page-view">
    <div class="card">
      <div class="card-header">
        <span class="card-title">完善公司信息</span>
        <span class="card-subtitle">录入和维护甲方公司信息</span>
        <button v-if="currentTab === 'normal'" class="btn-primary" style="margin-left: auto;" @click="openAddCompany">
          + 新增公司
        </button>
      </div>

      <!-- Tab 切换 -->
      <div class="company-tabs">
        <button class="company-tab" :class="{ active: currentTab === 'normal' }" @click="switchTab('normal')">
          正常公司 ({{ companies.length }})
        </button>
        <button v-if="currentUser && (currentUser.role === 'super_admin' || currentUser.role === 'maintainer')"
                class="company-tab" :class="{ active: currentTab === 'deleted' }" @click="switchTab('deleted')">
          回收站 ({{ deletedCompanies.length }})
        </button>
      </div>

      <div class="card-body">
        <div v-if="error" style="color:#EF4444; margin-bottom:12px; padding:8px; background:#FEF2F2; border-radius:6px;">
          {{ error }}
        </div>

        <!-- 搜索栏 -->
        <div class="company-search-bar" style="margin-bottom: 20px;">
          <input v-model="companySearchKeyword" type="text" :placeholder="currentTab === 'deleted' ? '搜索已删除公司名称或描述...' : '搜索公司名称或描述...'" class="company-search-input" />
          <span class="company-search-count">{{ filteredCompanies.length }} / {{ currentTab === 'deleted' ? deletedCompanies.length : companies.length }} 家</span>
        </div>

        <div v-if="loading" style="text-align:center; padding:40px; color:#94A3B8;">加载中...</div>
        <div v-else-if="filteredCompanies.length === 0" style="text-align:center; padding:40px; color:#94A3B8;">
          {{ companySearchKeyword ? '没有匹配的公司' : (currentTab === 'deleted' ? '回收站为空' : '暂无公司，点击右上角「新增公司」添加') }}
        </div>

        <!-- 公司列表（表格形式） -->
        <table v-else class="schema-table">
          <thead>
            <tr>
              <th style="width:60px">ID</th>
              <th>公司名称</th>
              <th style="width:100px">所在城市</th>
              <th style="width:180px">接收简历邮箱</th>
              <th>详细地址</th>
              <th style="width:100px">创建者</th>
              <th style="width:120px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="company in filteredCompanies" :key="company.id">
              <td>{{ company.id }}</td>
              <td style="font-weight: 500;">
                {{ company.name }}
                <div v-if="company.description" style="font-size:11px; color:#94A3B8; font-weight:normal; margin-top:2px;">{{ company.description }}</div>
              </td>
              <td>{{ company.city || '-' }}</td>
              <td style="font-size:12px;">{{ company.email || '-' }}</td>
              <td style="font-size:12px; color:#64748B;">{{ company.address || '-' }}</td>
              <td style="font-size:12px; color:#64748B;">{{ company.creator_name || '系统' }}</td>
              <td style="white-space:nowrap;">
                <!-- 回收站tab：显示恢复按钮 -->
                <template v-if="currentTab === 'deleted'">
                  <div class="table-action-btns">
                    <button class="table-btn table-btn-success" @click="restoreCompany(company)">恢复</button>
                  </div>
                  <div v-if="company.deleted_at" style="font-size:11px; color:#94A3B8; margin-top:4px;">
                    删除于 {{ formatDate(company.deleted_at) }}
                  </div>
                </template>
                <!-- 正常tab：显示编辑和删除按钮 -->
                <template v-else>
                  <template v-if="canEdit(company)">
                    <div class="table-action-btns">
                      <button class="table-btn table-btn-primary" @click="openEditCompany(company)">编辑</button>
                      <button class="table-btn table-btn-danger" @click="deleteCompany(company)">删除</button>
                    </div>
                  </template>
                  <span v-else style="font-size:12px; color:#94A3B8;">只读</span>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 新增/编辑公司弹窗 -->
    <div v-if="showForm" class="modal-overlay" @click.self="cancelForm">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ editingCompany ? '编辑公司' : '新增公司' }}</h3>
          <button @click="cancelForm" style="background:none; border:none; font-size:20px; cursor:pointer; color:#64748B;">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>公司名称 <span style="color:#EF4444">*</span></label>
            <input v-model="companyForm.name" type="text" placeholder="如：互联网公司D" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>所在城市</label>
              <select v-model="companyForm.city" class="form-select">
                <option value="">请选择城市</option>
                <option v-for="city in cityOptions" :key="city" :value="city">{{ city }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>接收简历邮箱</label>
              <input v-model="companyForm.email" type="email" placeholder="hr@company.com" />
              <div v-if="companyForm.email && !isValidEmail(companyForm.email)" style="color:#EF4444; font-size:11px; margin-top:4px;">
                邮箱格式不正确
              </div>
            </div>
          </div>
          <div class="form-group">
            <label>详细地址</label>
            <input v-model="companyForm.address" type="text" placeholder="如：浦东新区张江高科技园区..." />
          </div>
          <div class="form-group">
            <label>公司描述</label>
            <textarea v-model="companyForm.description" rows="3" placeholder="公司简介..."></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-outline" @click="cancelForm">取消</button>
          <button class="btn-primary" @click="saveCompany">
            {{ editingCompany ? '保存修改' : '新增公司' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.company-tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid #E2E8F0;
  padding: 0 20px;
  background: #F8FAFC;
}
.company-tab {
  padding: 12px 20px;
  background: none;
  border: none;
  font-size: 14px;
  font-weight: 500;
  color: #64748B;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}
.company-tab:hover {
  color: #4F6EF7;
}
.company-tab.active {
  color: #4F6EF7;
  border-bottom-color: #4F6EF7;
  font-weight: 600;
}
.company-search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.company-search-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  font-size: 13px;
}
.company-search-input:focus {
  outline: none;
  border-color: #4F6EF7;
}
.company-search-count {
  font-size: 12px;
  color: #94A3B8;
  white-space: nowrap;
}
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: #fff;
  border-radius: 12px;
  width: 520px;
  max-width: 90%;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
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
.modal-footer {
  padding: 16px 20px;
  border-top: 1px solid #E8ECF0;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
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
.form-group textarea,
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  font-size: 13px;
  box-sizing: border-box;
  background: #fff;
}
.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
  outline: none;
  border-color: #4F6EF7;
}
.form-row {
  display: flex;
  gap: 12px;
}
.form-row .form-group {
  flex: 1;
}
</style>
