<script setup>
import { ref, computed, inject, nextTick } from 'vue'
import CompanyManageView from './CompanyManageView.vue'
import SchemaManageView from './SchemaManageView.vue'
import PositionLibraryView from './PositionLibraryView.vue'
import ResumeFilterView from './ResumeFilterView.vue'
import MatchResultView from './MatchResultView.vue'
import FeedbackView from './FeedbackView.vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  userRole: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:visible', 'close'])

const navigateTo = inject('navigateTo', () => {})

// 工作流步骤定义
const allSteps = [
  {
    label: '完善公司信息',
    desc: '维护公司基础资料与接收邮箱',
    component: CompanyManageView,
    icon: '🏢',
    color: '#3B82F6',
    roles: ['super_admin', 'maintainer', 'recruiter'],
    tip: '添加或完善招聘公司的基础信息，包括公司名称、所在城市、联系邮箱等。'
  },
  {
    label: '配置岗位Schema',
    desc: '设置Schema字段与权重',
    component: SchemaManageView,
    icon: '⚙️',
    color: '#F59E0B',
    roles: ['super_admin', 'maintainer'],
    tip: '配置岗位匹配的维度字段（如学历、工作年限、技能等），设置各字段的权重和是否为硬性条件。'
  },
  {
    label: '配置岗位需求',
    desc: '创建招聘岗位与需求描述',
    component: PositionLibraryView,
    icon: '📋',
    color: '#8B5CF6',
    roles: ['super_admin', 'maintainer', 'recruiter'],
    tip: '新增招聘岗位，选择所属公司，配置每个岗位的具体招聘需求和匹配要求。'
  },
  {
    label: '上传简历和匹配',
    desc: '批量上传简历并执行AI匹配',
    component: ResumeFilterView,
    icon: '📄',
    color: '#06B6D4',
    roles: ['super_admin', 'maintainer', 'recruiter'],
    tip: '批量上传候选人简历，系统自动解析后可选择全量匹配所有岗位或定向匹配指定岗位。'
  },
  {
    label: '查看匹配结果',
    desc: '查看AI匹配结果与详细评分',
    component: MatchResultView,
    icon: '🎯',
    color: '#10B981',
    roles: ['super_admin', 'maintainer', 'recruiter'],
    tip: '查看简历与岗位的匹配评分、硬性条件满足情况、各维度得分详情，可按公司/岗位/坐席筛选。'
  },
  {
    label: '反馈优化',
    desc: '人工评价与AI自迭代优化',
    component: FeedbackView,
    icon: '📈',
    color: '#EC4899',
    roles: ['super_admin', 'maintainer', 'recruiter'],
    tip: '对匹配结果进行人工反馈（准确/不准确），系统根据反馈持续优化匹配算法。'
  }
]

// 根据用户角色过滤步骤
const steps = computed(() => {
  if (!props.userRole) return allSteps
  return allSteps.filter(s => s.roles.includes(props.userRole))
})

const currentStepIndex = ref(0)
const currentStep = computed(() => steps.value[currentStepIndex.value])
const isFirstStep = computed(() => currentStepIndex.value === 0)
const isLastStep = computed(() => currentStepIndex.value === steps.value.length - 1)
const stepProgress = computed(() => ((currentStepIndex.value + 1) / steps.value.length) * 100)

// 已完成的步骤（用于显示对勾）
const completedSteps = ref(new Set())

function goNext() {
  if (!isLastStep.value) {
    completedSteps.value.add(currentStepIndex.value)
    currentStepIndex.value++
    nextTick(() => {
      const contentEl = document.querySelector('.wizard-content')
      if (contentEl) contentEl.scrollTop = 0
    })
  }
}

function goPrev() {
  if (!isFirstStep.value) {
    currentStepIndex.value--
    nextTick(() => {
      const contentEl = document.querySelector('.wizard-content')
      if (contentEl) contentEl.scrollTop = 0
    })
  }
}

function skipStep() {
  goNext()
}

function goToStep(index) {
  if (index < currentStepIndex.value) {
    currentStepIndex.value = index
  }
}

function finishWizard() {
  emit('update:visible', false)
  emit('close')
  // 跳转到工作台
  navigateTo('工作台')
}

function closeWizard() {
  emit('update:visible', false)
  emit('close')
}
</script>

<template>
  <div v-if="visible" class="wizard-overlay" @click.self="closeWizard">
    <div class="wizard-container">
      <!-- 顶部标题栏 -->
      <div class="wizard-header">
        <div class="wizard-title">
          <span class="wizard-title-icon">🚀</span>
          <span>招聘工作流向导</span>
        </div>
        <button class="wizard-close" @click="closeWizard">✕</button>
      </div>

      <!-- 步骤指示器 -->
      <div class="wizard-steps">
        <div class="wizard-progress-bar">
          <div class="wizard-progress-fill" :style="{ width: stepProgress + '%' }"></div>
        </div>
        <div class="wizard-steps-list">
          <div
            v-for="(step, idx) in steps"
            :key="step.label"
            class="wizard-step-item"
            :class="{
              active: idx === currentStepIndex,
              completed: completedSteps.has(idx) || idx < currentStepIndex,
              clickable: idx < currentStepIndex
            }"
            @click="goToStep(idx)"
          >
            <div class="wizard-step-circle" :style="{ '--step-color': step.color }">
              <span v-if="completedSteps.has(idx) || idx < currentStepIndex" class="step-check">✓</span>
              <span v-else class="step-number">{{ idx + 1 }}</span>
            </div>
            <div class="wizard-step-label">{{ step.label }}</div>
          </div>
        </div>
      </div>

      <!-- 当前步骤提示 -->
      <div class="wizard-tip">
        <span class="wizard-tip-icon">💡</span>
        <span class="wizard-tip-text">{{ currentStep.tip }}</span>
      </div>

      <!-- 内容区域 -->
      <div class="wizard-content">
        <component :is="currentStep.component" :key="currentStep.label" />
      </div>

      <!-- 底部按钮区 -->
      <div class="wizard-footer">
        <button class="wizard-btn wizard-btn-secondary" @click="closeWizard">
          退出向导
        </button>
        <div class="wizard-footer-right">
          <button
            v-if="!isFirstStep"
            class="wizard-btn wizard-btn-outline"
            @click="goPrev"
          >
            ← 上一步
          </button>
          <button
            v-if="!isLastStep"
            class="wizard-btn wizard-btn-outline"
            @click="skipStep"
          >
            跳过此步
          </button>
          <button
            v-if="!isLastStep"
            class="wizard-btn wizard-btn-primary"
            @click="goNext"
          >
            下一步 →
          </button>
          <button
            v-else
            class="wizard-btn wizard-btn-success"
            @click="finishWizard"
          >
            🎉 完成配置，开始使用
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wizard-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  backdrop-filter: blur(4px);
}

.wizard-container {
  width: 92vw;
  max-width: 1280px;
  height: 92vh;
  max-height: 860px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 顶部标题栏 */
.wizard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: linear-gradient(135deg, #4F6EF7 0%, #6366F1 100%);
  color: #fff;
  flex-shrink: 0;
}

.wizard-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
}

.wizard-title-icon {
  font-size: 22px;
}

.wizard-close {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: #fff;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.wizard-close:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* 步骤指示器 */
.wizard-steps {
  padding: 16px 24px 12px;
  background: #F8FAFC;
  border-bottom: 1px solid #E2E8F0;
  flex-shrink: 0;
}

.wizard-progress-bar {
  height: 4px;
  background: #E2E8F0;
  border-radius: 2px;
  margin-bottom: 14px;
  overflow: hidden;
}

.wizard-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4F6EF7, #6366F1);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.wizard-steps-list {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.wizard-step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.wizard-step-item.clickable {
  cursor: pointer;
}

.wizard-step-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  background: #E2E8F0;
  color: #94A3B8;
  transition: all 0.3s;
  flex-shrink: 0;
}

.wizard-step-item.active .wizard-step-circle {
  background: var(--step-color, #4F6EF7);
  color: #fff;
  box-shadow: 0 0 0 4px rgba(79, 110, 247, 0.2);
}

.wizard-step-item.completed .wizard-step-circle {
  background: #10B981;
  color: #fff;
}

.step-check {
  font-size: 14px;
}

.wizard-step-label {
  font-size: 11px;
  color: #94A3B8;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
  transition: color 0.3s;
}

.wizard-step-item.active .wizard-step-label {
  color: #1E293B;
  font-weight: 600;
}

.wizard-step-item.completed .wizard-step-label {
  color: #10B981;
}

/* 步骤提示 */
.wizard-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  background: #FFFBEB;
  border-bottom: 1px solid #FDE68A;
  flex-shrink: 0;
}

.wizard-tip-icon {
  font-size: 16px;
}

.wizard-tip-text {
  font-size: 13px;
  color: #92400E;
  line-height: 1.5;
}

/* 内容区域 */
.wizard-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  background: #F1F5F9;
}

/* 底部按钮区 */
.wizard-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  background: #fff;
  border-top: 1px solid #E2E8F0;
  flex-shrink: 0;
}

.wizard-footer-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.wizard-btn {
  padding: 9px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  display: flex;
  align-items: center;
  gap: 6px;
}

.wizard-btn-primary {
  background: linear-gradient(135deg, #4F6EF7 0%, #6366F1 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(79, 110, 247, 0.3);
}

.wizard-btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 110, 247, 0.4);
}

.wizard-btn-success {
  background: linear-gradient(135deg, #10B981 0%, #059669 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
}

.wizard-btn-success:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
}

.wizard-btn-outline {
  background: #fff;
  color: #475569;
  border: 1px solid #CBD5E1;
}

.wizard-btn-outline:hover {
  background: #F8FAFC;
  border-color: #94A3B8;
  color: #1E293B;
}

.wizard-btn-secondary {
  background: transparent;
  color: #94A3B8;
  border: none;
  padding: 9px 12px;
}

.wizard-btn-secondary:hover {
  color: #EF4444;
  background: #FEF2F2;
}
</style>
