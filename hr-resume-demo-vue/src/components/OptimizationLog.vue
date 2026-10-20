<script setup>
const logs = [
  {
    title: '反馈已记录：调整权重 +5',
    desc: '模型已更新 #4 · 技能匹配阈值更严格',
    showTrend: true,
    trend: '72% → 78% → 84%'
  },
  {
    title: '学历已记录：本科及以上 | 10',
    desc: '模型已更新 · 科技匹配阈值更严格',
    showTrend: false
  },
  {
    title: '模型自学习触发',
    desc: '本轮基于 21 条淘汰案例微调了语义识别规则',
    showTrend: false
  }
]
</script>

<template>
  <div class="card">
    <div class="card-header">
      <span class="step-num" style="background:#8B5CF6;">5</span>
      <span class="card-title">优化记录</span>
    </div>
    <div class="card-body">
      <div v-for="(log, idx) in logs" :key="idx" class="opt-log-item">
        <div class="opt-log-title">{{ log.title }}</div>
        <div class="opt-log-desc">{{ log.desc }}</div>
        <div v-if="log.showTrend" class="accuracy-trend">
          <span>准确率趋势：</span>
          <span class="trend-badge">{{ log.trend }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
