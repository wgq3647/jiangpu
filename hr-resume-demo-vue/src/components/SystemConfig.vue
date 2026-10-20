<script setup>
import { ref, onMounted, computed } from 'vue'
import { systemConfigApi } from '../api/index.js'

const loading = ref(false)
const saving = ref(false)
const configs = ref({})
const saveMessage = ref('')
const saveError = ref('')

// 表单数据
const form = ref({
  ai_enabled: 'true',
  ai_provider: 'doubao',
  doubao_api_key: '',
  doubao_base_url: '',
  doubao_model: '',
  qwen_api_key: '',
  qwen_base_url: '',
  qwen_model: '',
  openai_api_key: '',
  openai_base_url: '',
  openai_model: '',
  custom_api_key: '',
  custom_base_url: '',
  custom_model: '',
  ai_temperature: '0.1',
  ai_max_tokens: '4096',
  ai_timeout: '60',
  ai_max_retries: '2',
  smtp_enabled: 'false',
  smtp_host: '',
  smtp_port: '465',
  smtp_user: '',
  smtp_password: '',
  smtp_from_name: 'HR智能招聘系统',
  smtp_use_ssl: 'true',
  pdf_image_recognition_enabled: 'false',
})

const providerOptions = [
  { value: 'doubao', label: '豆包 (Doubao)' },
  { value: 'qwen', label: '千问 (Qwen)' },
  { value: 'openai', label: 'GPT (OpenAI)' },
  { value: 'custom', label: '自定义 (兼容OpenAI格式)' },
]

const currentProviderConfig = computed(() => {
  const p = form.value.ai_provider
  return {
    api_key: form.value[p + '_api_key'],
    base_url: form.value[p + '_base_url'],
    model: form.value[p + '_model'],
  }
})

const currentApiKey = computed({
  get: () => form.value[form.value.ai_provider + '_api_key'],
  set: (v) => { form.value[form.value.ai_provider + '_api_key'] = v }
})
const currentBaseUrl = computed({
  get: () => form.value[form.value.ai_provider + '_base_url'],
  set: (v) => { form.value[form.value.ai_provider + '_base_url'] = v }
})
const currentModel = computed({
  get: () => form.value[form.value.ai_provider + '_model'],
  set: (v) => { form.value[form.value.ai_provider + '_model'] = v }
})

const isConfigured = computed(() => {
  return form.value.ai_enabled === 'true' &&
    currentProviderConfig.value.api_key &&
    currentProviderConfig.value.base_url
})

async function loadConfigs() {
  loading.value = true
  saveError.value = ''
  try {
    const data = await systemConfigApi.getAll()
    configs.value = data
    for (const key of Object.keys(form.value)) {
      if (data[key] && data[key].value !== undefined) {
        form.value[key] = data[key].value
      }
    }
  } catch (e) {
    saveError.value = '加载配置失败: ' + (e.message || e)
  } finally {
    loading.value = false
  }
}

async function saveConfigs() {
  saving.value = true
  saveMessage.value = ''
  saveError.value = ''
  try {
    // 强制保持PDF/图片识别功能为关闭状态（系统级锁定，不可开启）
    form.value.pdf_image_recognition_enabled = 'false'
    const result = await systemConfigApi.update(form.value)
    saveMessage.value = result.message || '保存成功'
    setTimeout(() => { saveMessage.value = '' }, 3000)
  } catch (e) {
    saveError.value = '保存失败: ' + (e.message || e)
  } finally {
    saving.value = false
  }
}

onMounted(() => loadConfigs())
</script>

<template>
  <div class="system-config-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">系统配置</h2>
        <p class="page-desc">AI服务配置，修改后立即生效，无需重启服务</p>
      </div>
      <div class="header-status">
        <span class="status-badge" :class="isConfigured ? 'status-ok' : 'status-warn'">
          {{ isConfigured ? 'AI已配置' : 'AI未配置' }}
        </span>
      </div>
    </div>

    <div v-if="loading" class="loading-state">加载中...</div>
    <div v-else class="config-content">
      <!-- AI开关 -->
      <div class="config-card">
        <div class="card-title">AI服务总开关</div>
        <div class="switch-row">
          <label class="switch-label">
            <input type="checkbox" v-model="form.ai_enabled" true-value="true" false-value="false" class="switch-input" />
            <span class="switch-text">{{ form.ai_enabled === 'true' ? '已启用AI' : '已禁用AI（使用规则引擎降级）' }}</span>
          </label>
        </div>
      </div>

      <!-- 提供商选择 -->
      <div class="config-card">
        <div class="card-title">AI提供商</div>
        <div class="provider-grid">
          <div
            v-for="p in providerOptions"
            :key="p.value"
            class="provider-card"
            :class="{ active: form.ai_provider === p.value }"
            @click="form.ai_provider = p.value"
          >
            <div class="provider-name">{{ p.label }}</div>
            <div class="provider-check" v-if="form.ai_provider === p.value">✓</div>
          </div>
        </div>
      </div>

      <!-- 当前提供商配置 -->
      <div class="config-card">
        <div class="card-title">{{ providerOptions.find(p => p.value === form.ai_provider)?.label }} 配置</div>
        <div class="form-grid">
          <div class="form-item">
            <label>API Key</label>
            <input type="password" v-model="currentApiKey" placeholder="请输入API Key" class="form-input" />
          </div>
          <div class="form-item">
            <label>Base URL</label>
            <input type="text" v-model="currentBaseUrl" placeholder="https://..." class="form-input" />
          </div>
          <div class="form-item">
            <label>模型名称</label>
            <input type="text" v-model="currentModel" placeholder="如 doubao-1-5-pro-32k" class="form-input" />
          </div>
        </div>
      </div>

      <!-- 通用配置 -->
      <div class="config-card">
        <div class="card-title">通用参数</div>
        <div class="form-grid">
          <div class="form-item">
            <label>采样温度 (Temperature)</label>
            <input type="number" step="0.1" v-model="form.ai_temperature" class="form-input" />
            <div class="form-hint">解析任务建议用低温度（0.1）保证稳定性</div>
          </div>
          <div class="form-item">
            <label>最大输出 Token</label>
            <input type="number" v-model="form.ai_max_tokens" class="form-input" />
          </div>
          <div class="form-item">
            <label>请求超时 (秒)</label>
            <input type="number" v-model="form.ai_timeout" class="form-input" />
          </div>
          <div class="form-item">
            <label>最大重试次数</label>
            <input type="number" v-model="form.ai_max_retries" class="form-input" />
          </div>
        </div>
      </div>

      <!-- SMTP邮件配置 -->
      <div class="config-card">
        <div class="card-title">
          SMTP 邮件发送配置
          <span class="card-subtitle" style="font-size:12px;font-weight:normal;color:#94A3B8;margin-left:8px;">配置后可将匹配结果真实发送到公司邮箱</span>
        </div>
        <div style="margin-bottom:16px;">
          <label class="switch-label">
            <input type="checkbox" v-model="form.smtp_enabled" true-value="true" false-value="false" class="switch-input" />
            <span class="switch-text">{{ form.smtp_enabled === 'true' ? '已启用SMTP邮件发送' : '已禁用（仅记录发送状态）' }}</span>
          </label>
        </div>
        <div class="form-grid">
          <div class="form-item">
            <label>SMTP服务器地址</label>
            <input v-model="form.smtp_host" type="text" placeholder="如 smtp.qq.com / smtp.163.com" class="form-input" />
          </div>
          <div class="form-item">
            <label>端口</label>
            <input v-model="form.smtp_port" type="number" placeholder="465" class="form-input" />
            <div class="form-hint">465=SSL, 587=TLS, 25=普通</div>
          </div>
          <div class="form-item">
            <label>发件人邮箱</label>
            <input v-model="form.smtp_user" type="email" placeholder="your@email.com" class="form-input" />
          </div>
          <div class="form-item">
            <label>邮箱授权码/密码</label>
            <input v-model="form.smtp_password" type="password" placeholder="SMTP授权码" class="form-input" />
          </div>
          <div class="form-item">
            <label>发件人显示名称</label>
            <input v-model="form.smtp_from_name" type="text" placeholder="HR智能招聘系统" class="form-input" />
          </div>
          <div class="form-item">
            <label>加密方式</label>
            <select v-model="form.smtp_use_ssl" class="form-input">
              <option value="true">SSL加密（推荐，端口465）</option>
              <option value="false">TLS/普通（端口587/25）</option>
            </select>
          </div>
        </div>
        <div style="margin-top:12px;padding:10px 14px;background:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;font-size:12px;color:#92400E;">
          <strong>提示：</strong>QQ邮箱/163邮箱需在邮箱设置中开启SMTP服务并获取「授权码」（非登录密码）。企业邮箱请咨询IT部门获取SMTP信息。
        </div>
      </div>

      <!-- PDF和图片识别开关（当前版本已禁用，不可开启） -->
      <div class="config-card" style="opacity:0.85;">
        <div class="card-title">
          PDF和图片简历识别
          <span class="card-subtitle" style="font-size:12px;font-weight:normal;color:#94A3B8;margin-left:8px;">当前版本已禁用此功能</span>
        </div>
        <div class="switch-row">
          <label class="switch-label" style="cursor:not-allowed;opacity:0.7;">
            <input
              type="checkbox"
              v-model="form.pdf_image_recognition_enabled"
              true-value="true"
              false-value="false"
              class="switch-input"
              disabled
              style="cursor:not-allowed;"
            />
            <span class="switch-text">{{ form.pdf_image_recognition_enabled === 'true' ? '已启用PDF/图片识别' : '已禁用（仅支持Word和文本格式简历）' }}</span>
          </label>
        </div>
        <div style="margin-top:14px;padding:10px 14px;background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;font-size:12px;color:#991B1B;">
          <strong>说明：</strong>当前版本已关闭PDF和图片简历的识别功能，上传PDF或图片格式简历将被拒绝。此功能为系统级锁定，不可通过配置开启。如需启用，请联系系统管理员升级版本。
        </div>
      </div>

      <!-- 保存按钮 -->
      <div class="save-bar">
        <div v-if="saveMessage" class="save-success">{{ saveMessage }}</div>
        <div v-if="saveError" class="save-error">{{ saveError }}</div>
        <button class="btn-save" @click="saveConfigs" :disabled="saving">
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.system-config-page { padding: 24px; max-width: 900px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-title { font-size: 20px; font-weight: 700; color: #1E293B; margin: 0; }
.page-desc { font-size: 13px; color: #64748B; margin-top: 4px; }
.status-badge { padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.status-ok { background: #ECFDF5; color: #059669; }
.status-warn { background: #FEF3C7; color: #D97706; }
.loading-state { text-align: center; padding: 60px; color: #94A3B8; }
.config-content { display: flex; flex-direction: column; gap: 20px; }
.config-card { background: #fff; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; }
.card-title { font-size: 15px; font-weight: 600; color: #1E293B; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #F1F5F9; }
.switch-row { display: flex; align-items: center; }
.switch-label { display: flex; align-items: center; gap: 12px; cursor: pointer; }
.switch-input { width: 44px; height: 24px; accent-color: #4F46E5; cursor: pointer; }
.switch-text { font-size: 14px; color: #334155; font-weight: 500; }
.provider-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.provider-card { position: relative; padding: 14px 16px; border: 2px solid #E2E8F0; border-radius: 10px; cursor: pointer; transition: all 0.15s; }
.provider-card:hover { border-color: #A5B4FC; }
.provider-card.active { border-color: #4F46E5; background: #EEF2FF; }
.provider-name { font-size: 13px; font-weight: 600; color: #1E293B; }
.provider-check { position: absolute; top: 10px; right: 12px; color: #4F46E5; font-weight: 700; }
.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.form-item { display: flex; flex-direction: column; gap: 6px; }
.form-item label { font-size: 12px; font-weight: 500; color: #64748B; }
.form-input { padding: 9px 12px; border: 1px solid #E2E8F0; border-radius: 8px; font-size: 13px; color: #1E293B; }
.form-input:focus { outline: none; border-color: #4F46E5; box-shadow: 0 0 0 3px rgba(79,70,229,0.1); }
.form-hint { font-size: 11px; color: #94A3B8; }
.save-bar { display: flex; align-items: center; gap: 16px; padding: 16px 0; }
.btn-save { padding: 10px 28px; background: #4F46E5; color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-save:hover:not(:disabled) { background: #4338CA; }
.btn-save:disabled { opacity: 0.6; cursor: not-allowed; }
.save-success { color: #059669; font-size: 13px; font-weight: 500; }
.save-error { color: #DC2626; font-size: 13px; }
</style>
