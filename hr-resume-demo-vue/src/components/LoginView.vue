<script setup>
import { ref } from 'vue'
import { authApi, setAuth } from '../api/index.js'

const emit = defineEmits(['login-success', 'go-register'])

const phone = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function onSubmit() {
  error.value = ''
  if (!phone.value.trim()) { error.value = '请输入手机号'; return }
  if (!password.value) { error.value = '请输入密码'; return }
  loading.value = true
  try {
    const res = await authApi.login({ phone: phone.value.trim(), password: password.value })
    setAuth(res.access_token, res.user)
    emit('login-success', res.user)
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="36" height="36">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
        </svg>
        <h1>AI HR 智能简历平台</h1>
        <p class="auth-subtitle">登录以继续使用系统</p>
      </div>

      <div v-if="error" class="auth-error">{{ error }}</div>

      <form @submit.prevent="onSubmit">
        <div class="form-group">
          <label>手机号</label>
          <input v-model="phone" type="text" placeholder="请输入11位手机号" maxlength="11" />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="请输入密码" />
        </div>
        <button type="submit" class="btn-auth" :disabled="loading">
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>

      <div class="auth-footer">
        还没有账号？
        <a href="javascript:;" @click="emit('go-register')">立即注册</a>
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
  width: 400px;
  max-width: 90%;
  box-shadow: 0 20px 60px rgba(79, 110, 247, 0.12);
}
.auth-logo {
  text-align: center;
  margin-bottom: 28px;
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
.form-group input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.15s;
}
.form-group input:focus {
  outline: none;
  border-color: #4F6EF7;
  box-shadow: 0 0 0 3px rgba(79, 110, 247, 0.1);
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
