<script setup>
import { ref, onMounted, computed } from 'vue'
import { statsApi } from '../api/index.js'

const props = defineProps({
  activeNav: {
    type: String,
    default: '工作台'
  },
  user: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['nav-change'])

const resumeCount = ref(0)

onMounted(async () => {
  try {
    const stats = await statsApi.dashboard()
    resumeCount.value = stats.parsed_resumes || 0
  } catch (e) {
    console.error('获取统计数据失败:', e)
  }
})

const allNavItems = [
  {
    section: '核心功能',
    items: [
      { icon: 'grid', label: '工作台', roles: ['super_admin', 'maintainer', 'recruiter'] },
      { icon: 'folder', label: '完善公司信息', roles: ['super_admin', 'maintainer', 'recruiter'] },
      { icon: 'settings', label: '配置岗位Schema', roles: ['super_admin', 'maintainer'] },
      { icon: 'file', label: '配置岗位需求', roles: ['super_admin', 'maintainer', 'recruiter'] },
      { icon: 'chat', label: '上传简历和匹配', roles: ['super_admin', 'maintainer', 'recruiter'] },
    ]
  },
  {
    section: '匹配与优化',
    items: [
      { icon: 'search', label: '查看匹配结果', roles: ['super_admin', 'maintainer', 'recruiter'] },
      { icon: 'chart', label: '反馈优化', roles: ['super_admin', 'maintainer', 'recruiter'] },
    ]
  },
  {
    section: '系统管理',
    items: [
      { icon: 'users', label: '用户管理', roles: ['super_admin'] },
      { icon: 'settings', label: '系统配置', roles: ['super_admin'] },
      { icon: 'chart', label: '招聘数据', roles: ['super_admin', 'maintainer'] },
    ]
  }
]

const navItems = computed(() => {
  const role = props.user?.role
  return allNavItems.map(group => ({
    section: group.section,
    items: group.items.filter(it => !role || it.roles.includes(role))
  })).filter(g => g.items.length > 0)
})

const iconPaths = {
  grid: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
  file: '<path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/>',
  folder: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>',
  chat: '<path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>',
  chart: '<path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/>',
  users: '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/>',
  upload: '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3m8.66-12.5l-2.6 1.5m-8.12 4.68l-2.6 1.5m11.22 0l-2.6-1.5M6.34 7.5l-2.6-1.5M19.07 12h-3M7.93 12h-3"/>',
}

function setActive(label) {
  emit('nav-change', label)
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-logo">
      <div class="logo-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
        </svg>
        AI HR 智能体
      </div>
    </div>
    <nav class="sidebar-nav">
      <template v-for="group in navItems" :key="group.section">
        <div class="nav-section-label">{{ group.section }}</div>
        <div
          v-for="item in group.items"
          :key="item.label"
          class="nav-item"
          :class="{ active: activeNav === item.label }"
          @click="setActive(item.label)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" v-html="iconPaths[item.icon]"></svg>
          {{ item.label }}
          <span v-if="item.label === '上传简历和匹配' && resumeCount > 0" class="nav-badge">{{ resumeCount }}</span>
        </div>
      </template>
    </nav>
    <div class="sidebar-footer">V1.0 初版 Demo</div>
  </aside>
</template>
