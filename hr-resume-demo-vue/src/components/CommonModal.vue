<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '提示'
  },
  message: {
    type: String,
    default: ''
  },
  type: {
    type: String,
    default: 'info', // info, success, warning, error, confirm, prompt
    validator: (val) => ['info', 'success', 'warning', 'error', 'confirm', 'prompt'].includes(val)
  },
  showCancel: {
    type: Boolean,
    default: false
  },
  confirmText: {
    type: String,
    default: '确定'
  },
  cancelText: {
    type: String,
    default: '取消'
  },
  placeholder: {
    type: String,
    default: '请输入'
  },
  defaultValue: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['confirm', 'cancel', 'update:visible'])

const isShow = ref(props.visible)
const inputValue = ref(props.defaultValue)

watch(() => props.visible, (val) => {
  isShow.value = val
  if (val) {
    inputValue.value = props.defaultValue
  }
})

function handleConfirm() {
  emit('confirm', inputValue.value)
  close()
}

function handleCancel() {
  emit('cancel')
  close()
}

function close() {
  isShow.value = false
  emit('update:visible', false)
}

// 图标和颜色配置
const typeConfig = {
  info: { icon: 'ℹ️', color: '#3B82F6', bg: '#EFF6FF' },
  success: { icon: '✓', color: '#10B981', bg: '#ECFDF5' },
  warning: { icon: '⚠️', color: '#F59E0B', bg: '#FFFBEB' },
  error: { icon: '✕', color: '#EF4444', bg: '#FEF2F2' },
  confirm: { icon: '❓', color: '#6366F1', bg: '#EEF2FF' },
  prompt: { icon: '✏️', color: '#8B5CF6', bg: '#F5F3FF' }
}

const config = {
  get icon() { return typeConfig[props.type]?.icon || 'ℹ️' },
  get color() { return typeConfig[props.type]?.color || '#3B82F6' },
  get bg() { return typeConfig[props.type]?.bg || '#EFF6FF' }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="isShow" class="common-modal-overlay" @click.self="handleCancel">
      <div class="common-modal">
        <div class="common-modal-header">
          <div class="common-modal-icon" :style="{ background: config.bg, color: config.color }">
            {{ config.icon }}
          </div>
          <div class="common-modal-title">{{ title }}</div>
          <button class="common-modal-close" @click="close">&times;</button>
        </div>
        <div class="common-modal-body">
          <div class="common-modal-message">{{ message }}</div>
          <input
            v-if="type === 'prompt'"
            v-model="inputValue"
            class="common-modal-input"
            :placeholder="placeholder"
            @keyup.enter="handleConfirm"
          />
        </div>
        <div class="common-modal-footer">
          <button v-if="showCancel" class="common-modal-btn common-modal-btn-cancel" @click="handleCancel">
            {{ cancelText }}
          </button>
          <button class="common-modal-btn common-modal-btn-confirm" :style="{ background: config.color }" @click="handleConfirm">
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.common-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.common-modal {
  background: #fff;
  border-radius: 16px;
  width: 400px;
  max-width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.25s ease;
  overflow: hidden;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.common-modal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 20px 12px;
}

.common-modal-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
  flex-shrink: 0;
}

.common-modal-title {
  font-size: 16px;
  font-weight: 600;
  color: #1E293B;
  flex: 1;
}

.common-modal-close {
  background: none;
  border: none;
  font-size: 22px;
  color: #94A3B8;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  line-height: 1;
}

.common-modal-close:hover {
  background: #F1F5F9;
  color: #64748B;
}

.common-modal-body {
  padding: 0 20px 20px;
}

.common-modal-message {
  font-size: 14px;
  color: #475569;
  line-height: 1.6;
  padding-left: 52px;
}

.common-modal-input {
  margin-top: 12px;
  margin-left: 52px;
  width: calc(100% - 52px);
  padding: 10px 12px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 14px;
  color: #1E293B;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  box-sizing: border-box;
}

.common-modal-input:focus {
  border-color: #8B5CF6;
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
}

.common-modal-input::placeholder {
  color: #94A3B8;
}

.common-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #F1F5F9;
  background: #FAFBFC;
}

.common-modal-btn {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
  min-width: 80px;
}

.common-modal-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.common-modal-btn:active {
  transform: translateY(0);
}

.common-modal-btn-cancel {
  background: #fff;
  color: #64748B;
  border: 1px solid #E2E8F0;
}

.common-modal-btn-cancel:hover {
  background: #F8FAFC;
  border-color: #CBD5E1;
}

.common-modal-btn-confirm {
  color: #fff;
}
</style>
