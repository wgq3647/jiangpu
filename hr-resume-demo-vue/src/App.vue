<script setup>
import { ref, computed, provide, reactive } from 'vue'
import Sidebar from './components/Sidebar.vue'
import DashboardView from './components/DashboardView.vue'
import SchemaConfig from './components/SchemaConfig.vue'
import PositionLibraryView from './components/PositionLibraryView.vue'
import CompanyManageView from './components/CompanyManageView.vue'
import ResumeFilterView from './components/ResumeFilterView.vue'
import MatchResultView from './components/MatchResultView.vue'
import FeedbackView from './components/FeedbackView.vue'
import LoginView from './components/LoginView.vue'
import RegisterView from './components/RegisterView.vue'
import UserManagement from './components/UserManagement.vue'
import SystemConfig from './components/SystemConfig.vue'
import RecruiterStats from './components/RecruiterStats.vue'
import BatchImportView from './components/BatchImportView.vue'
import SchemaManageView from './components/SchemaManageView.vue'
import CommonModal from './components/CommonModal.vue'
import { getToken, getStoredUser, clearAuth, authApi } from './api/index.js'

// 全局弹窗状态
const globalModal = reactive({
  visible: false,
  title: '提示',
  message: '',
  type: 'info',
  showCancel: false,
  confirmText: '确定',
  cancelText: '取消',
  placeholder: '请输入',
  defaultValue: '',
  onConfirm: null,
  onCancel: null
})

// 全局提示方法
function showAlert(message, type = 'info', title = '提示') {
  globalModal.visible = true
  globalModal.title = title
  globalModal.message = message
  globalModal.type = type
  globalModal.showCancel = false
  globalModal.confirmText = '确定'
  globalModal.cancelText = '取消'
  globalModal.placeholder = '请输入'
  globalModal.defaultValue = ''
  globalModal.onConfirm = null
  globalModal.onCancel = null
}

// 全局确认方法（返回Promise）
function showConfirm(message, title = '确认', type = 'confirm') {
  return new Promise((resolve) => {
    globalModal.visible = true
    globalModal.title = title
    globalModal.message = message
    globalModal.type = type
    globalModal.showCancel = true
    globalModal.confirmText = '确定'
    globalModal.cancelText = '取消'
    globalModal.placeholder = '请输入'
    globalModal.defaultValue = ''
    globalModal.onConfirm = () => resolve(true)
    globalModal.onCancel = () => resolve(false)
  })
}

// 全局输入方法（返回Promise，resolve用户输入的值）
function showPrompt(message, defaultValue = '', placeholder = '请输入', title = '请输入') {
  return new Promise((resolve) => {
    globalModal.visible = true
    globalModal.title = title
    globalModal.message = message
    globalModal.type = 'prompt'
    globalModal.showCancel = true
    globalModal.confirmText = '确定'
    globalModal.cancelText = '取消'
    globalModal.placeholder = placeholder
    globalModal.defaultValue = defaultValue
    globalModal.onConfirm = (value) => resolve(value)
    globalModal.onCancel = () => resolve(null)
  })
}

function handleModalConfirm(inputValue) {
  if (globalModal.onConfirm) {
    globalModal.onConfirm(inputValue)
  }
  globalModal.visible = false
}

function handleModalCancel() {
  if (globalModal.onCancel) {
    globalModal.onCancel()
  }
  globalModal.visible = false
}

// 提供全局方法
provide('showAlert', showAlert)
provide('showConfirm', showConfirm)
provide('showPrompt', showPrompt)

// 页面状态：'login' | 'register' | 'main'
const pageMode = ref(getToken() ? 'main' : 'login')
const currentUser = ref(getStoredUser())
const activeNav = ref('工作台')
// 传递给匹配结果页面的筛选参数
const matchViewParams = ref(null)
const navigateTo = (label, params = null) => {
  activeNav.value = label
  if (label === '查看匹配结果') {
    matchViewParams.value = params
  }
}
provide('navigateTo', navigateTo)
provide('getMatchViewParams', () => matchViewParams.value)
provide('clearMatchViewParams', () => { matchViewParams.value = null })

function onLoginSuccess(user) {
  currentUser.value = user
  pageMode.value = 'main'
  activeNav.value = '工作台'
}

function onRegisterSuccess(user) {
  currentUser.value = user
  pageMode.value = 'main'
  activeNav.value = '工作台'
}

function onLogout() {
  authApi.logout()
  currentUser.value = null
  pageMode.value = 'login'
}

function onNavChange(label) {
  activeNav.value = label
}

const roleLabel = computed(() => {
  if (!currentUser.value) return ''
  return { super_admin: '超管', maintainer: '维护员', recruiter: '招聘员' }[currentUser.value.role] || currentUser.value.role
})
</script>

<template>
  <!-- 登录页 -->
  <LoginView v-if="pageMode === 'login'" @login-success="onLoginSuccess" @go-register="pageMode = 'register'" />

  <!-- 注册页 -->
  <RegisterView v-else-if="pageMode === 'register'" @register-success="onRegisterSuccess" @go-login="pageMode = 'login'" />

  <!-- 主界面 -->
  <div v-else class="app">
    <Sidebar :active-nav="activeNav" :user="currentUser" @nav-change="onNavChange" />
    <main class="main">
      <!-- 顶部用户栏 -->
      <div class="topbar">
        <div class="topbar-user">
          <span class="user-avatar">{{ (currentUser?.name || currentUser?.phone || 'U').charAt(0) }}</span>
          <span class="user-name">{{ currentUser?.name || currentUser?.phone }}</span>
          <span class="user-role">{{ roleLabel }}</span>
          <button class="btn-logout" @click="onLogout">退出登录</button>
        </div>
      </div>

      <!-- 工作台 -->
      <DashboardView v-if="activeNav === '工作台'" />

      <!-- 完善公司信息 -->
      <CompanyManageView v-else-if="activeNav === '完善公司信息'" />

      <!-- 配置岗位需求 -->
      <PositionLibraryView v-else-if="activeNav === '配置岗位需求'" />

      <!-- 配置岗位Schema -->
      <SchemaManageView v-else-if="activeNav === '配置岗位Schema'" />

      <!-- 上传简历和匹配 -->
      <ResumeFilterView v-else-if="activeNav === '上传简历和匹配'" />

      <!-- 查看匹配结果 -->
      <MatchResultView v-else-if="activeNav === '查看匹配结果'" />

      <!-- 反馈优化 -->
      <FeedbackView v-else-if="activeNav === '反馈优化'" />

      <!-- 用户管理 -->
      <UserManagement v-else-if="activeNav === '用户管理'" />

      <!-- 系统配置 -->
      <SystemConfig v-else-if="activeNav === '系统配置'" />
      <RecruiterStats v-else-if="activeNav === '招聘数据'" />
      <BatchImportView v-else-if="activeNav === '批量导入'" />
    </main>
  </div>

  <!-- 全局自定义弹窗 -->
  <CommonModal
    :visible="globalModal.visible"
    :title="globalModal.title"
    :message="globalModal.message"
    :type="globalModal.type"
    :show-cancel="globalModal.showCancel"
    :confirm-text="globalModal.confirmText"
    :cancel-text="globalModal.cancelText"
    :placeholder="globalModal.placeholder"
    :default-value="globalModal.defaultValue"
    @confirm="handleModalConfirm"
    @cancel="handleModalCancel"
  />
</template>

<style scoped>
.topbar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 4px 0 0;
}
.topbar-user {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  padding: 6px 14px;
  border-radius: 10px;
  border: 1px solid #E8ECF0;
}
.user-avatar {
  width: 30px; height: 30px;
  border-radius: 50%;
  background: #4F6EF7;
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700;
}
.user-name { font-size: 13px; font-weight: 600; color: #1E293B; }
.user-role {
  font-size: 11px;
  background: #EEF1FE;
  color: #4F6EF7;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}
.btn-logout {
  background: none;
  border: none;
  color: #EF4444;
  font-size: 12.5px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}
.btn-logout:hover { background: #FEF2F2; }
</style>
