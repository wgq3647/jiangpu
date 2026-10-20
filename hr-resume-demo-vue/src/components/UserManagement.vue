<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { userApi, getStoredUser } from '../api/index.js'

const showAlert = inject('showAlert')
const showConfirm = inject('showConfirm')
const showPrompt = inject('showPrompt')
const currentUser = getStoredUser()
const users = ref([])
const loading = ref(false)
const error = ref('')
const currentPage = ref(1)
const pageSize = 10
const totalPages = computed(() => Math.max(1, Math.ceil(users.value.length / pageSize)))
const pagedUsers = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return users.value.slice(start, start + pageSize)
})
function goPage(p) {
  if (p < 1 || p > totalPages.value) return
  currentPage.value = p
}

async function loadUsers() {
  loading.value = true
  error.value = ''
  try {
    users.value = await userApi.list()
  } catch (e) {
    error.value = '加载用户列表失败: ' + e.message
  } finally {
    loading.value = false
  }
}

async function changeRole(u) {
  const role = await showPrompt(`修改用户 ${u.name || u.phone} 的角色（maintainer / recruiter）：`, u.role, '请输入角色', '修改角色')
  if (!role) return
  if (!['maintainer', 'recruiter'].includes(role)) {
    showAlert('角色只能是 maintainer 或 recruiter', 'warning')
    return
  }
  try {
    await userApi.updateRole(u.id, role)
    await loadUsers()
  } catch (e) {
    showAlert('修改失败: ' + e.message, 'error')
  }
}

async function toggleStatus(u) {
  const next = u.status === 'active' ? 'disabled' : 'active'
  const confirmed = await showConfirm(`确定要${next === 'disabled' ? '禁用' : '启用'}用户 ${u.name || u.phone} 吗？`, '操作确认', 'warning')
  if (!confirmed) return
  try {
    await userApi.updateStatus(u.id, next)
    await loadUsers()
  } catch (e) {
    showAlert('操作失败: ' + e.message, 'error')
  }
}

async function approve(u) {
  const confirmed = await showConfirm(`确定审核通过用户 ${u.name || u.phone} 吗？`, '审核确认', 'info')
  if (!confirmed) return
  try {
    await userApi.approve(u.id)
    await loadUsers()
  } catch (e) {
    showAlert('操作失败: ' + e.message, 'error')
  }
}

function roleLabel(r) {
  return { super_admin: '超级管理员', maintainer: '维护人员', recruiter: '招聘人员' }[r] || r
}
function roleClass(r) {
  return { super_admin: 'tag-hard', maintainer: 'tag-soft', recruiter: 'tag-soft' }[r] || 'tag-soft'
}
function statusLabel(s) {
  return { active: '正常', pending: '待审核', disabled: '已禁用' }[s] || s
}
function statusClass(s) {
  return { active: 'tag-hard', pending: 'tag-soft', disabled: 'tag-soft' }[s] || 'tag-soft'
}

onMounted(() => loadUsers())
</script>

<template>
  <div class="page-view">
    <div class="card">
      <div class="card-header">
        <span class="card-title">用户管理</span>
        <span class="card-subtitle">系统账号与角色权限配置</span>
      </div>
      <div class="card-body">
        <div v-if="error" style="color:#EF4444; margin-bottom:12px; padding:8px; background:#FEF2F2; border-radius:6px;">
          {{ error }}
        </div>
        <div v-if="loading" style="text-align:center; padding:40px; color:#94A3B8;">加载中...</div>
        <table v-else class="schema-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>手机号</th>
              <th>姓名</th>
              <th>角色</th>
              <th>状态</th>
              <th>注册时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in pagedUsers" :key="u.id">
              <td>{{ u.id }}</td>
              <td>{{ u.phone }}</td>
              <td>{{ u.name || '-' }}</td>
              <td><span :class="roleClass(u.role)">{{ roleLabel(u.role) }}</span></td>
              <td><span :class="statusClass(u.status)">{{ statusLabel(u.status) }}</span></td>
              <td>{{ new Date(u.created_at).toLocaleDateString() }}</td>
              <td style="white-space:nowrap;">
                <button
                  v-if="u.id !== currentUser.id && u.role !== 'super_admin'"
                  @click="changeRole(u)"
                  style="background:none; border:none; color:#4F6EF7; font-size:12px; cursor:pointer; margin-right:8px;"
                >修改角色</button>
                <button
                  v-if="u.id !== currentUser.id"
                  @click="toggleStatus(u)"
                  :style="{
                    background: 'none', border: 'none', fontSize: '12px', cursor: 'pointer', marginRight: '8px',
                    color: u.status === 'active' ? '#EF4444' : '#22C55E'
                  }"
                >{{ u.status === 'active' ? '禁用' : '启用' }}</button>
                <button
                  v-if="u.status === 'pending'"
                  @click="approve(u)"
                  style="background:none; border:none; color:#22C55E; font-size:12px; cursor:pointer;"
                >审核通过</button>
                <span v-if="u.id === currentUser.id" style="font-size:12px; color:#94A3B8;">（本人）</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="pagination" v-if="users.length > pageSize">
          <button class="page-btn" :disabled="currentPage === 1" @click="goPage(currentPage - 1)">上一页</button>
          <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页（共 {{ users.length }} 条）</span>
          <button class="page-btn" :disabled="currentPage === totalPages" @click="goPage(currentPage + 1)">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>


<style scoped>
.pagination { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 16px; padding-top: 16px; border-top: 1px solid #F1F5F9; }
.page-btn { padding: 6px 14px; border: 1px solid #E2E8F0; border-radius: 6px; background: #fff; color: #475569; font-size: 12px; cursor: pointer; }
.page-btn:hover:not(:disabled) { border-color: #4F6EF7; color: #4F6EF7; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 12px; color: #64748B; }
</style>