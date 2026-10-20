<script setup>
import { ref, computed } from 'vue'
import { authApi, setAuth } from '../api/index.js'

const emit = defineEmits(['register-success', 'go-login'])

const phone = ref('')
const name = ref('')
const password = ref('')
const confirmPassword = ref('')
const role = ref('recruiter')  // recruiter | maintainer
const loading = ref(false)
const error = ref('')
const successMsg = ref('')

const isMaintainer = computed(() => role.value === 'maintainer')

async function onSubmit() {
  error.value = ''
  successMsg.value = ''
  if (!/^1\d{10}$/.test(phone.value.trim())) {
    error.value = '手机号格式不正确，应为11位数字且以1开头'
    return
  }
  if (password.value.length < 6) {
    error.value = '密码至少6位'
    return
  }
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    const res = await authApi.register({
      phone: phone.value.trim(),
      name: name.value.trim(),
      password: password.value,
      confirm_password: confirmPassword.value,
      role: role.value
    })
    // 维护人员注册：需审核，不自动登录
    if (res.requires_approval) {
      successMsg.value = res.message || '注册申请已提交，请等待管理员审核'
      // 清空表单
      phone.value = ''
      password.value = ''
      confirmPassword.value = ''
      return
    }
    // 招聘人员：自动登录
    setAuth(res.access_token, res.user)
    emit('register-success', res.user)
  } catch (e) {
    error.value = e.message || '注册失败'
  } finally {
    loading.value = false
  }
}

function backToLogin() {
  emit('go-login')
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="36" height="36">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
        </svg>
        <h1>创建账号</h1>
        <p class="auth-subtitle">注册新账号</p>
      </div>

      <div v-if="error" class="auth-error">{{ error }}</div>
      <div v-if="successMsg" class="auth-success">
        {{ successMsg }}
        <div style="margin-top:10px;">
          <a href="javascript:;" @click="backToLogin" style="color:#4F6EF7;font-weight:600;cursor:pointer;">返回登录页</a>
        </div>
      </div>

      <form v-if="!successMsg" @submit.prevent="onSubmit">
        <div class="form-group">
          <label>注册身份</label>
          <div class="role-options">
            <label class="role-option" :class="{ active: role === 'recruiter' }">
              <input type="radio" value="recruiter" v-model="role" />
              <div>
                <div class="role-title">招聘人员</div>
                <div class="role-desc">注册后直接开通，可立即使用</div>
              </div>
            </label>
            <label class="role-option" :class="{ active: role === 'maintainer' }">
              <input type="radio" value="maintainer" v-model="role" />
              <div>
                <div class="role-title">维护人员</div>
                <div class="role-desc">注册后需等待超级管理员审核</div>
              </div>
            </label>
          </div>
          <div v-if="isMaintainer" class="role-tip">
            提示：维护人员可配置JD岗位和Schema字段，但需管理员审核开通
          </div>
        </div>

        <div class="form-group">
          <label>手机号（登录账号）</label>
          <input v-model="phone" type="text" placeholder="请输入11位手机号" maxlength="11" />
        </div>
        <div class="form-group">
          <label>姓名</label>
          <input v-model="name" type="text" placeholder="请输入姓名（选填）" />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="至少6位" />
        </div>
        <div class="form-group">
          <label>确认密码</label>
          <input v-model="confirmPassword" type="password" placeholder="再次输入密码" />
        </div>
        <button type="submit" class="btn-auth" :disabled="loading">
          {{ loading ? '注册中...' : '注 册' }}
        </button>
      </form>

      <div v-if="!successMsg" class="auth-footer">
        已有账号？
        <a href="javascript:;" @click="emit('go-login')">返回登录</a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #EEF1FE 0%, #F0F2F5 100%);
}
.auth-card {
  background: #fff;
  border-radius: 16px;
  padding: 40px 36px;
  width: 420px;
  max-width: 90%;
  box-shadow: 0 20px 60px rgba(79, 110, 247, 0.12);
}
.auth-logo {
  text-align: center;
  margin-bottom: 24px;
  color: #4F6EF7;
}
.auth-logo h1 {
  font-size: 18px;
  font-weight: 700;
  color: #1E293B;
  margin-top: 10px;
}
.auth-subtitle {
  font-size: 13px;
  color: #64748B;
  margin-top: 4px;
}
.auth-error {
  background: #FEF2F2;
  color: #DC2626;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 16px;
}
.auth-success {
  background: #ECFDF5;
  color: #059669;
  padding: 20px 14px;
  border-radius: 8px;
  font-size: 14px;
  text-align: center;
  margin-bottom: 16px;
  line-height: 1.6;
}
.form-group {
  margin-bottom: 14px;
}
.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  margin-bottom: 6px;
}
.form-group input[type="text"],
.form-group input[type="password"] {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.15s;
}
.form-group input[type="text"]:focus,
.form-group input[type="password"]:focus {
  outline: none;
  border-color: #4F6EF7;
  box-shadow: 0 0 0 3px rgba(79, 110, 247, 0.1);
}
.role-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.role-option {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 10px 12px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.role-option.active {
  border-color: #4F6EF7;
  background: #EEF1FE;
}
.role-option input {
  margin-top: 3px;
}
.role-title {
  font-size: 13px;
  font-weight: 600;
  color: #1E293B;
}
.role-desc {
  font-size: 11px;
  color: #64748B;
  margin-top: 2px;
}
.role-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #D97706;
  background: #FFFBEB;
  padding: 8px 10px;
  border-radius: 6px;
}
.btn-auth {
  width: 100%;
  background: #4F6EF7;
  color: #fff;
  padding: 12px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  margin-top: 8px;
  transition: background 0.15s;
}
.btn-auth:hover:not(:disabled) { background: #3B5BE5; }
.btn-auth:disabled { opacity: 0.6; cursor: not-allowed; }
.auth-footer {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: #64748B;
}
.auth-footer a {
  color: #4F6EF7;
  font-weight: 600;
  cursor: pointer;
}
</style>
