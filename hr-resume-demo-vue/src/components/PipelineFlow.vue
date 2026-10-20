<script setup>
import { inject, computed, ref } from 'vue'
import WorkflowWizard from './WorkflowWizard.vue'

const props = defineProps({
  userRole: {
    type: String,
    default: ''
  }
})

const navigateTo = inject('navigateTo', () => {})

const showWizard = ref(false)

function startWizard() {
  showWizard.value = true
}

const allSteps = [
  {
    label: '完善公司信息',
    desc: '维护公司基础资料与接收邮箱',
    nav: '完善公司信息',
    icon: '🏢',
    color: '#3B82F6',
    roles: ['super_admin', 'maintainer', 'recruiter']
  },
  {
    label: '配置岗位Schema',
    desc: '设置Schema字段与权重',
    nav: '配置岗位Schema',
    icon: '⚙️',
    color: '#F59E0B',
    roles: ['super_admin', 'maintainer']
  },
  {
    label: '配置岗位需求',
    desc: '创建招聘岗位与需求描述',
    nav: '配置岗位需求',
    icon: '📋',
    color: '#8B5CF6',
    roles: ['super_admin', 'maintainer', 'recruiter']
  },
  {
    label: '上传简历和匹配',
    desc: '批量上传简历并执行AI匹配',
    nav: '上传简历和匹配',
    icon: '📄',
    color: '#06B6D4',
    roles: ['super_admin', 'maintainer', 'recruiter']
  },
  {
    label: '查看匹配结果',
    desc: '查看AI匹配结果与详细评分',
    nav: '查看匹配结果',
    icon: '🎯',
    color: '#10B981',
    roles: ['super_admin', 'maintainer', 'recruiter']
  },
  {
    label: '反馈优化',
    desc: '人工评价与AI自迭代优化',
    nav: '反馈优化',
    icon: '📈',
    color: '#EC4899',
    roles: ['super_admin', 'maintainer', 'recruiter']
  }
]

const steps = computed(() => {
  if (!props.userRole) return allSteps
  return allSteps.filter(s => s.roles.includes(props.userRole))
})
</script>

<template>
  <div class="card workflow-card">
    <div class="card-header">
      <div class="workflow-header-left">
        <span class="card-title">招聘工作流</span>
        <span class="card-subtitle">点击节点快速跳转到对应页面</span>
      </div>
      <button class="btn-start-wizard" @click="startWizard">
        🚀 启动向导模式
      </button>
    </div>
    <div class="card-body">
      <div class="workflow">
        <template v-for="(step, idx) in steps" :key="step.label">
          <div class="workflow-step" @click="navigateTo(step.nav)" :style="{ '--step-color': step.color }">
            <div class="workflow-icon">{{ step.icon }}</div>
            <div class="workflow-info">
              <span class="workflow-label">{{ step.label }}</span>
              <span class="workflow-desc">{{ step.desc }}</span>
            </div>
            <div v-if="idx < steps.length - 1" class="workflow-arrow">→</div>
          </div>
        </template>
      </div>
    </div>

    <!-- 向导模式弹窗 -->
    <WorkflowWizard v-model:visible="showWizard" :user-role="userRole" />
  </div>
</template>

<style scoped>
.workflow-card { }
.workflow-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.btn-start-wizard {
  padding: 8px 16px;
  background: linear-gradient(135deg, #4F6EF7 0%, #6366F1 100%);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(79, 110, 247, 0.3);
}
.btn-start-wizard:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 110, 247, 0.4);
}
.workflow {
  display: flex;
  align-items: stretch;
  gap: 0;
  overflow-x: auto;
  padding: 8px 0;
}
.workflow-step {
  flex: 1;
  min-width: 140px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
  position: relative;
}
.workflow-step:hover {
  background: #F8FAFC;
  border-color: var(--step-color);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.workflow-icon {
  font-size: 28px;
  margin-bottom: 8px;
}
.workflow-info {
  text-align: center;
}
.workflow-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #1E293B;
  margin-bottom: 4px;
}
.workflow-desc {
  display: block;
  font-size: 11px;
  color: #94A3B8;
  line-height: 1.4;
}
.workflow-arrow {
  position: absolute;
  right: -8px;
  top: 50%;
  transform: translateY(-50%);
  color: #CBD5E1;
  font-size: 16px;
  font-weight: bold;
  z-index: 1;
}
</style>
