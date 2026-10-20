<script setup>
import { ref, onMounted } from 'vue'
import { statsApi } from '../api/index.js'

const stats = ref([
  { icon: 'users', color: 'green', value: '0', label: '在招岗位' },
  { icon: 'file', color: 'orange', value: '0', label: '待筛选简历' },
  { icon: 'alert', color: 'red', value: '0', label: '本轮淘汰' },
  { icon: 'bolt', color: 'blue', value: '0', label: '匹配结果' }
])

onMounted(async () => {
  try {
    const data = await statsApi.dashboard()
    stats.value = [
      { icon: 'users', color: 'green', value: String(data.open_positions || 0), label: '在招岗位' },
      { icon: 'file', color: 'orange', value: String(data.parsed_resumes || 0), label: '待筛选简历' },
      { icon: 'alert', color: 'red', value: String(data.rejected_matches || 0), label: '本轮淘汰' },
      { icon: 'bolt', color: 'blue', value: String(data.total_matches || 0), label: '匹配结果' }
    ]
  } catch (e) {
    console.error('获取统计数据失败:', e)
  }
})

const iconPaths = {
  users: '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/>',
  file: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
  alert: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  bolt: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'
}
</script>

<template>
  <div class="stats-row">
    <div v-for="stat in stats" :key="stat.label" class="stat-card">
      <div class="stat-icon" :class="stat.color">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" v-html="iconPaths[stat.icon]"></svg>
      </div>
      <div class="stat-info">
        <div class="stat-value">{{ stat.value }}</div>
        <div class="stat-label">{{ stat.label }}</div>
      </div>
    </div>
  </div>
</template>
