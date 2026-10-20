<script setup>
import { ref, onMounted, computed, inject } from 'vue'
import { feedbackApi } from '../api/index.js'
import { getStoredUser } from '../api/index.js'

const showAlert = inject('showAlert')
const showConfirm = inject('showConfirm')
const currentUser = getStoredUser()
const canOptimize = computed(() => ['super_admin', 'maintainer'].includes(currentUser?.role))

// 统计数据
const stats = ref({
  total_matches: 0,
  reviewed_count: 0,
  pending_review: 0,
  interview_count: 0,
  interview_pass: 0,
  interview_fail: 0,
  interview_pending: 0,
  interview_pass_rate: 0,
  optimization_count: 0,
  current_accuracy: 0,
  true_positive: 0,
  false_positive: 0,
  true_negative: 0,
  false_negative: 0,
})

// 优化日志
const optimizationLogs = ref([])
const loadingLogs = ref(false)

// 准确率趋势
const accuracyTrend = ref({
  dates: [],
  accuracy: [],
  precision: [],
  recall: [],
})
const loadingTrend = ref(false)

// 触发优化
const optimizing = ref(false)
const optimizeResult = ref(null)

// 加载统计
async function loadStats() {
  try {
    const data = await feedbackApi.stats()
    stats.value = data
  } catch (e) {
    console.error('加载统计失败', e)
  }
}

// 加载优化日志
async function loadLogs() {
  loadingLogs.value = true
  try {
    const data = await feedbackApi.getOptimizationLogs({ limit: 20 })
    optimizationLogs.value = data
  } catch (e) {
    console.error('加载优化日志失败', e)
  } finally {
    loadingLogs.value = false
  }
}

// 加载准确率趋势
async function loadTrend() {
  loadingTrend.value = true
  try {
    const data = await feedbackApi.getAccuracyTrend({ days: 30 })
    accuracyTrend.value = data
  } catch (e) {
    console.error('加载准确率趋势失败', e)
  } finally {
    loadingTrend.value = false
  }
}

// 触发AI自学习优化
async function runOptimization() {
  const confirmed = await showConfirm('确定要触发AI自学习优化吗？系统将分析所有有面试结果的样本，自动调整Schema匹配权重。', '优化确认', 'info')
  if (!confirmed) {
    return
  }
  optimizing.value = true
  optimizeResult.value = null
  try {
    const result = await feedbackApi.runOptimization({ triggered_by: '手动触发' })
    optimizeResult.value = result
    showAlert(result.message, 'success', '优化完成')
    // 刷新数据
    await loadStats()
    await loadLogs()
    await loadTrend()
  } catch (e) {
    showAlert('优化失败: ' + (e.message || '未知错误'), 'error')
  } finally {
    optimizing.value = false
  }
}

// 格式化时间
function formatTime(timeStr) {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// 解析优化详情
function parseAdjustments(afterData) {
  if (!afterData) return []
  try {
    const data = JSON.parse(afterData)
    if (Array.isArray(data)) {
      return data.flatMap(pos => Object.entries(pos.adjustments || {}).map(([field, adj]) => ({
        field,
        old: adj.old,
        new: adj.new,
      })))
    }
    return []
  } catch {
    return []
  }
}

// SVG折线图计算
const chartWidth = 600
const chartHeight = 220
const padding = { top: 20, right: 20, bottom: 40, left: 50 }

const chartData = computed(() => {
  const dates = accuracyTrend.value.dates
  const accuracy = accuracyTrend.value.accuracy
  if (dates.length === 0) return { points: '', labels: [], yLabels: [] }

  const innerW = chartWidth - padding.left - padding.right
  const innerH = chartHeight - padding.top - padding.bottom
  const maxY = 100
  const minY = 0

  const points = accuracy.map((v, i) => {
    const x = padding.left + (i / Math.max(dates.length - 1, 1)) * innerW
    const y = padding.top + innerH - ((v - minY) / (maxY - minY)) * innerH
    return `${x},${y}`
  }).join(' ')

  const labels = dates.map((d, i) => {
    const x = padding.left + (i / Math.max(dates.length - 1, 1)) * innerW
    return { x, label: d.slice(5) }
  })

  const yLabels = [0, 25, 50, 75, 100].map(v => {
    const y = padding.top + innerH - (v / 100) * innerH
    return { y, label: v + '%' }
  })

  return { points, labels, yLabels, innerW, innerH }
})

onMounted(() => {
  loadStats()
  loadLogs()
  loadTrend()
})
</script>

<template>
  <div class="feedback-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">反馈优化</h2>
        <p class="page-subtitle">人工评价 + 面试反馈 → AI自学习优化 → 越用越精准</p>
      </div>
      <button v-if="canOptimize" class="btn-optimize" @click="runOptimization" :disabled="optimizing">
        <span v-if="optimizing">优化中...</span>
        <span v-else>⚡ 触发AI自学习优化</span>
      </button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card stat-blue">
        <div class="stat-icon">📋</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.pending_review }}</div>
          <div class="stat-label">待人工评价</div>
        </div>
      </div>
      <div class="stat-card stat-green">
        <div class="stat-icon">✅</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.reviewed_count }}</div>
          <div class="stat-label">已人工评价</div>
        </div>
      </div>
      <div class="stat-card stat-orange">
        <div class="stat-icon">🎯</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.interview_pass_rate }}%</div>
          <div class="stat-label">面试通过率</div>
        </div>
      </div>
      <div class="stat-card stat-purple">
        <div class="stat-icon">🔄</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.optimization_count }}</div>
          <div class="stat-label">AI优化次数</div>
        </div>
      </div>
      <div class="stat-card stat-cyan">
        <div class="stat-icon">📊</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.current_accuracy }}%</div>
          <div class="stat-label">当前匹配准确率</div>
        </div>
      </div>
    </div>

    <!-- 混淆矩阵 -->
    <div v-if="stats.interview_count > 0" class="confusion-section">
      <h3 class="section-title">AI预测 vs 面试结果（混淆矩阵）</h3>
      <div class="confusion-grid">
        <div class="confusion-cell tp">
          <div class="cell-value">{{ stats.true_positive }}</div>
          <div class="cell-label">真阳性<br/><small>AI通过 + 面试通过</small></div>
        </div>
        <div class="confusion-cell fp">
          <div class="cell-value">{{ stats.false_positive }}</div>
          <div class="cell-label">假阳性<br/><small>AI通过 + 面试不通过</small></div>
        </div>
        <div class="confusion-cell fn">
          <div class="cell-value">{{ stats.false_negative }}</div>
          <div class="cell-label">假阴性<br/><small>AI不通过 + 面试通过</small></div>
        </div>
        <div class="confusion-cell tn">
          <div class="cell-value">{{ stats.true_negative }}</div>
          <div class="cell-label">真阴性<br/><small>AI不通过 + 面试不通过</small></div>
        </div>
      </div>
      <p class="confusion-tip">
        <strong>优化重点：</strong>假阳性（AI高估）案例会触发相关维度权重下调；假阴性（AI低估）案例会触发相关维度权重上调。
      </p>
    </div>

    <div class="content-grid">
      <!-- 准确率趋势图 -->
      <div class="chart-card">
        <h3 class="section-title">匹配准确率变化趋势</h3>
        <div v-if="loadingTrend" class="loading">加载中...</div>
        <div v-else-if="accuracyTrend.dates.length === 0" class="empty-state">
          <p>暂无准确率数据</p>
          <p class="empty-tip">录入面试反馈后，系统将自动记录准确率变化</p>
        </div>
        <svg v-else :width="chartWidth" :height="chartHeight" class="trend-chart">
          <!-- 网格线 -->
          <line v-for="yl in chartData.yLabels" :key="yl.y"
            :x1="padding.left" :y1="yl.y" :x2="chartWidth - padding.right" :y2="yl.y"
            stroke="#E2E8F0" stroke-dasharray="4,4" />
          <!-- Y轴标签 -->
          <text v-for="yl in chartData.yLabels" :key="'y'+yl.y"
            :x="padding.left - 8" :y="yl.y + 4" text-anchor="end" font-size="11" fill="#94A3B8">{{ yl.label }}</text>
          <!-- X轴标签 -->
          <text v-for="(lbl, i) in chartData.labels" :key="'x'+i"
            :x="lbl.x" :y="chartHeight - padding.bottom + 20" text-anchor="middle" font-size="10" fill="#94A3B8">{{ lbl.label }}</text>
          <!-- 折线 -->
          <polyline :points="chartData.points" fill="none" stroke="#4F6EF7" stroke-width="2.5" stroke-linejoin="round" />
          <!-- 数据点 -->
          <g v-for="(v, i) in accuracyTrend.accuracy" :key="'p'+i">
            <circle :cx="padding.left + (i / Math.max(accuracyTrend.dates.length - 1, 1)) * (chartWidth - padding.left - padding.right)"
              :cy="padding.top + (chartHeight - padding.top - padding.bottom) - (v / 100) * (chartHeight - padding.top - padding.bottom)"
              r="4" fill="#4F6EF7" stroke="#fff" stroke-width="2" />
            <text :x="padding.left + (i / Math.max(accuracyTrend.dates.length - 1, 1)) * (chartWidth - padding.left - padding.right)"
              :cy="padding.top + (chartHeight - padding.top - padding.bottom) - (v / 100) * (chartHeight - padding.top - padding.bottom) - 10"
              text-anchor="middle" font-size="10" fill="#4F6EF7" font-weight="600">{{ v }}%</text>
          </g>
        </svg>
      </div>

      <!-- 优化日志 -->
      <div class="log-card">
        <h3 class="section-title">AI优化日志</h3>
        <div v-if="loadingLogs" class="loading">加载中...</div>
        <div v-else-if="optimizationLogs.length === 0" class="empty-state">
          <p>暂无优化记录</p>
          <p class="empty-tip">点击右上角"触发AI自学习优化"按钮开始第一次优化</p>
        </div>
        <div v-else class="log-timeline">
          <div v-for="log in optimizationLogs" :key="log.id" class="log-item">
            <div class="log-dot"></div>
            <div class="log-content">
              <div class="log-header">
                <span class="log-type">{{ log.optimization_type }}</span>
                <span class="log-time">{{ formatTime(log.created_at) }}</span>
              </div>
              <p class="log-desc">{{ log.description }}</p>
              <div v-if="log.accuracy_before !== null" class="log-meta">
                <span>样本数: {{ log.sample_count }}</span>
                <span>准确率: {{ log.accuracy_before }}%</span>
                <span>触发: {{ log.triggered_by }}</span>
              </div>
              <div v-if="parseAdjustments(log.after_data).length > 0" class="log-adjustments">
                <div v-for="adj in parseAdjustments(log.after_data)" :key="adj.field" class="adj-item">
                  <span class="adj-field">{{ adj.field }}</span>
                  <span class="adj-change">{{ adj.old }} → {{ adj.new }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 优化原理说明 -->
    <div class="principle-card">
      <h3 class="section-title">AI自学习优化原理</h3>
      <div class="principle-steps">
        <div class="step-item">
          <div class="step-num">1</div>
          <div class="step-content">
            <h4>数据收集</h4>
            <p>收集HR人工评价（星级打分+偏差标注）和面试结果（通过/不通过+失败原因），形成带标签的训练样本</p>
          </div>
        </div>
        <div class="step-item">
          <div class="step-num">2</div>
          <div class="step-content">
            <h4>偏差分析</h4>
            <p>分析假阳性（AI高分但面试不通过）和假阴性（AI低分但面试通过）案例，定位AI高估/低估的维度</p>
          </div>
        </div>
        <div class="step-item">
          <div class="step-num">3</div>
          <div class="step-content">
            <h4>权重微调</h4>
            <p>自动调整Schema各维度匹配权重（±15%范围内）：高估维度降权，低估维度升权，真阳性维度加权</p>
          </div>
        </div>
        <div class="step-item">
          <div class="step-num">4</div>
          <div class="step-content">
            <h4>持续迭代</h4>
            <p>每次优化记录完整日志，准确率变化趋势全程可追溯，随着反馈数据积累，匹配精准度持续提升</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.feedback-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #1E293B;
  margin: 0 0 4px 0;
}
.page-subtitle {
  font-size: 13px;
  color: #64748B;
  margin: 0;
}

.btn-optimize {
  padding: 10px 20px;
  background: linear-gradient(135deg, #4F6EF7, #7C3AED);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(79, 110, 247, 0.3);
}
.btn-optimize:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 110, 247, 0.4);
}
.btn-optimize:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid #E2E8F0;
}
.stat-icon {
  font-size: 28px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
}
.stat-blue .stat-icon { background: #EFF6FF; }
.stat-green .stat-icon { background: #ECFDF5; }
.stat-orange .stat-icon { background: #FFF7ED; }
.stat-purple .stat-icon { background: #F5F3FF; }
.stat-cyan .stat-icon { background: #ECFEFF; }
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #1E293B;
  line-height: 1.2;
}
.stat-label {
  font-size: 12px;
  color: #64748B;
  margin-top: 2px;
}

/* 混淆矩阵 */
.confusion-section {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #E2E8F0;
  padding: 18px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
  margin: 0 0 14px 0;
}
.confusion-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.confusion-cell {
  padding: 16px;
  border-radius: 8px;
  text-align: center;
}
.confusion-cell.tp { background: #ECFDF5; border: 1px solid #A7F3D0; }
.confusion-cell.fp { background: #FEF2F2; border: 1px solid #FECACA; }
.confusion-cell.fn { background: #FFFBEB; border: 1px solid #FDE68A; }
.confusion-cell.tn { background: #F1F5F9; border: 1px solid #CBD5E1; }
.cell-value {
  font-size: 28px;
  font-weight: 700;
  color: #1E293B;
}
.cell-label {
  font-size: 12px;
  color: #475569;
  margin-top: 6px;
  line-height: 1.4;
}
.cell-label small { color: #94A3B8; }
.confusion-tip {
  margin-top: 12px;
  font-size: 12px;
  color: #64748B;
  padding: 10px 12px;
  background: #F8FAFC;
  border-radius: 6px;
  line-height: 1.6;
}

/* 内容网格 */
.content-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 16px;
}
.chart-card, .log-card {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #E2E8F0;
  padding: 18px;
}
.loading, .empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #94A3B8;
  font-size: 13px;
}
.empty-tip { font-size: 11px; margin-top: 6px; color: #CBD5E1; }
.trend-chart { width: 100%; height: auto; }

/* 优化日志时间线 */
.log-timeline {
  max-height: 400px;
  overflow-y: auto;
  padding-right: 8px;
}
.log-item {
  display: flex;
  gap: 12px;
  padding-bottom: 16px;
  position: relative;
}
.log-item:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 5px;
  top: 16px;
  bottom: 0;
  width: 2px;
  background: #E2E8F0;
}
.log-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #4F6EF7;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px #4F6EF7;
  flex-shrink: 0;
  margin-top: 3px;
}
.log-content { flex: 1; }
.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.log-type {
  font-size: 12px;
  font-weight: 600;
  color: #4F6EF7;
  background: #EEF2FF;
  padding: 2px 8px;
  border-radius: 4px;
}
.log-time { font-size: 11px; color: #94A3B8; }
.log-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  margin: 4px 0;
}
.log-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #94A3B8;
  margin-top: 4px;
}
.log-adjustments {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.adj-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 3px 8px;
  background: #F0FDF4;
  border-radius: 4px;
}
.adj-field { color: #166534; font-weight: 500; }
.adj-change { color: #65A30D; font-family: monospace; }

/* 优化原理 */
.principle-card {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #E2E8F0;
  padding: 18px;
}
.principle-steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.step-item {
  display: flex;
  gap: 12px;
}
.step-num {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4F6EF7, #7C3AED);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}
.step-content h4 {
  font-size: 13px;
  font-weight: 600;
  color: #1E293B;
  margin: 0 0 4px 0;
}
.step-content p {
  font-size: 11px;
  color: #64748B;
  line-height: 1.6;
  margin: 0;
}
</style>
