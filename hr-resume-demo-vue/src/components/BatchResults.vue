<script setup>
const results = [
  {
    name: '赵四',
    score: 91,
    level: 'high',
    status: '已推送公司A',
    position: '算法工程师',
    progressColor: 'green'
  },
  {
    name: '孙五',
    score: 82,
    level: 'high',
    status: '待确认',
    position: '开发工程师',
    tag: 'confirmed',
    progressColor: 'green'
  },
  {
    name: '周六',
    score: 70,
    level: 'mid',
    status: '备选',
    position: '数据分析师',
    tag: 'pending',
    progressColor: 'orange'
  },
  {
    name: '吴七',
    score: 43,
    level: 'low',
    status: '已淘汰',
    reason: '学历未达标',
    tag: 'rejected',
    progressColor: 'red'
  }
]
</script>

<template>
  <div class="card">
    <div class="card-header">
      <span class="card-title">本批简历结果</span>
    </div>
    <div class="card-body">
      <div v-for="item in results" :key="item.name" class="batch-result-item">
        <div class="batch-top">
          <span class="batch-name">{{ item.name }}</span>
          <div style="display:flex; align-items:center; gap:8px;">
            <span v-if="item.tag" class="batch-status-tag" :class="item.tag">{{ item.status }}</span>
            <span class="batch-score" :class="item.level">{{ item.score }}</span>
          </div>
        </div>
        <div class="batch-meta">
          <template v-if="item.reason">原因：{{ item.reason }}</template>
          <template v-else-if="item.tag">岗位：{{ item.position }}</template>
          <template v-else>状态：{{ item.status }} · {{ item.position }}</template>
        </div>
        <div class="batch-progress">
          <div class="batch-progress-fill" :class="item.progressColor" :style="{ width: item.score + '%' }"></div>
        </div>
      </div>
      <button class="btn-block" style="margin-top:14px; background:#EEF1FE; color:#4F6EF7;">
        开始新的筛选任务
      </button>
    </div>
  </div>
</template>
