<script setup>
import { ref, onMounted } from 'vue'
import StatsRow from './StatsRow.vue'
import PipelineFlow from './PipelineFlow.vue'
import { statsApi, getStoredUser } from '../api/index.js'

const currentUser = getStoredUser()
const userRole = currentUser?.role || ''

const systemStats = ref({
  total_resumes: 0,
  match_accuracy: 0,
  avg_score: 0
})

onMounted(async () => {
  try {
    const data = await statsApi.dashboard()
    systemStats.value = {
      total_resumes: data.total_resumes || 0,
      match_accuracy: data.match_accuracy || 0,
      avg_score: data.avg_score || 0
    }
  } catch (e) {
    console.error('获取统计数据失败:', e)
  }
})
</script>

<template>
  <div class="dashboard-page">
    <StatsRow />

    <PipelineFlow :user-role="userRole" />

    <div class="content-grid">
      <div class="content-left">
        <div class="card">
          <div class="card-header">
            <span class="card-title">系统运行概览</span>
          </div>
          <div class="card-body">
            <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
              <div style="text-align: center; padding: 20px; background: #F8FAFC; border-radius: 10px;">
                <div style="font-size: 32px; font-weight: 700; color: #4F6EF7;">{{ systemStats.total_resumes }}</div>
                <div style="font-size: 13px; color: #64748B; margin-top: 4px;">累计处理简历</div>
              </div>
              <div style="text-align: center; padding: 20px; background: #F8FAFC; border-radius: 10px;">
                <div style="font-size: 32px; font-weight: 700; color: #22C55E;">{{ systemStats.match_accuracy }}%</div>
                <div style="font-size: 13px; color: #64748B; margin-top: 4px;">匹配通过率</div>
              </div>
              <div style="text-align: center; padding: 20px; background: #F8FAFC; border-radius: 10px;">
                <div style="font-size: 32px; font-weight: 700; color: #F59E0B;">{{ systemStats.avg_score }}</div>
                <div style="font-size: 13px; color: #64748B; margin-top: 4px;">平均匹配分</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
