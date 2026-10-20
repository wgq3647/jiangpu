<script setup>
import { ref, computed, onMounted } from 'vue'
import { statsApi } from '../api/index.js'

const loading = ref(false)
const days = ref(30)
const statsData = ref(null)
const selectedRecruiterIds = ref([])
const showRecruiterFilter = ref(false)
// 获取本地日期字符串（避免UTC时区差一天的问题）
function getLocalDateStr() {
  const d = new Date()
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const selectedDate = ref(getLocalDateStr())
const showDatePicker = ref(false)
const viewMode = ref('single') // 'single' 单日模式 | 'range' 多天模式

// 初始化选中所有招聘人员
function initRecruiterFilter() {
  if (statsData.value && statsData.value.recruiters) {
    selectedRecruiterIds.value = statsData.value.recruiters.map(r => r.user_id)
  }
}

const dayOptions = [
  { value: 7, label: '近7天' },
  { value: 14, label: '近14天' },
  { value: 30, label: '近30天' },
]

async function loadData() {
  loading.value = true
  try {
    statsData.value = await statsApi.recruiterDaily(days.value)
    initRecruiterFilter()
  } catch (e) {
    console.error('加载统计数据失败', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => loadData())

// 汇总数据（根据模式：单日/多天）
const summary = computed(() => {
  if (!statsData.value) return null
  if (viewMode.value === 'single') {
    // 单日模式：取选中日期的数据
    const dateStr = selectedDate.value
    const dayTotal = statsData.value.daily_totals.find(d => d.date === dateStr) || {}
    return {
      uploaded: dayTotal.uploaded || 0,
      matched: dayTotal.matched || 0,
      unmatched: dayTotal.unmatched || 0,
      sent: dayTotal.sent || 0,
      interview: dayTotal.interview_scheduled || 0,
      passed: dayTotal.interview_passed || 0,
      failed: dayTotal.interview_failed || 0,
      companies_created: dayTotal.companies_created || 0,
      positions_created: dayTotal.positions_created || 0,
    }
  } else {
    // 多天模式：汇总所有天的数据
    const totals = { uploaded:0, matched:0, unmatched:0, sent:0, interview:0, passed:0, failed:0, companies_created:0, positions_created:0 }
    for (const d of statsData.value.daily_totals) {
      totals.uploaded += d.uploaded || 0
      totals.matched += d.matched || 0
      totals.unmatched += d.unmatched || 0
      totals.sent += d.sent || 0
      totals.interview += d.interview_scheduled || 0
      totals.passed += d.interview_passed || 0
      totals.failed += d.interview_failed || 0
      totals.companies_created += d.companies_created || 0
      totals.positions_created += d.positions_created || 0
    }
    return totals
  }
})

const matchRate = computed(() => {
  if (!summary.value) return 0
  const total = summary.value.matched + summary.value.unmatched
  if (total === 0) return 0
  return Math.round(summary.value.matched / total * 100)
})

// 饼图数据：招聘漏斗各阶段
const funnelData = computed(() => {
  if (!summary.value) return []
  const items = [
    { label: '上传简历', value: summary.value.uploaded, color: '#3B82F6' },
    { label: '成功匹配', value: summary.value.matched, color: '#10B981' },
    { label: '发送公司', value: summary.value.sent, color: '#F59E0B' },
    { label: '面试安排', value: summary.value.interview, color: '#8B5CF6' },
    { label: '面试通过', value: summary.value.passed, color: '#EC4899' },
  ]
  return items.filter(item => item.value > 0)
})

// 计算SVG饼图路径
const pieSlices = computed(() => {
  const data = funnelData.value
  const total = data.reduce((s, d) => s + d.value, 0)
  if (total === 0) return []
  const cx = 90, cy = 90, r = 70, innerR = 42
  let startAngle = -Math.PI / 2
  return data.map(d => {
    const angle = (d.value / total) * Math.PI * 2
    const endAngle = startAngle + angle
    const largeArc = angle > Math.PI ? 1 : 0
    // 外弧
    const x1 = cx + r * Math.cos(startAngle)
    const y1 = cy + r * Math.sin(startAngle)
    const x2 = cx + r * Math.cos(endAngle)
    const y2 = cy + r * Math.sin(endAngle)
    // 内弧
    const x3 = cx + innerR * Math.cos(endAngle)
    const y3 = cy + innerR * Math.sin(endAngle)
    const x4 = cx + innerR * Math.cos(startAngle)
    const y4 = cy + innerR * Math.sin(startAngle)
    const path = `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} L ${x3} ${y3} A ${innerR} ${innerR} 0 ${largeArc} 0 ${x4} ${y4} Z`
    const percent = ((d.value / total) * 100).toFixed(1)
    startAngle = endAngle
    return { ...d, path, percent }
  })
})

const pieTotal = computed(() => funnelData.value.reduce((s, d) => s + d.value, 0))

// 过滤后的招聘人员
const filteredRecruiters = computed(() => {
  if (!statsData.value) return []
  return statsData.value.recruiters.filter(r => selectedRecruiterIds.value.includes(r.user_id))
})

// 详细数据（根据模式：单日/多天）
const dailyDetail = computed(() => {
  if (!statsData.value) return []
  const dateStr = selectedDate.value
  return filteredRecruiters.value.map(r => {
    if (viewMode.value === 'single') {
      // 单日模式：取选中日期的数据
      const dayData = r.daily?.[dateStr] || {}
      return {
        user_id: r.user_id,
        name: r.name,
        phone: r.phone,
        companies_created: dayData.companies_created || 0,
        positions_created: dayData.positions_created || 0,
        uploaded: dayData.uploaded || 0,
        matched: dayData.matched || 0,
        unmatched: dayData.unmatched || 0,
        sent: dayData.sent || 0,
        interview_scheduled: dayData.interview_scheduled || 0,
        interview_passed: dayData.interview_passed || 0,
        interview_failed: dayData.interview_failed || 0,
      }
    } else {
      // 多天模式：汇总所有天的数据
      const totals = { user_id:r.user_id, name:r.name, phone:r.phone, companies_created:0, positions_created:0, uploaded:0, matched:0, unmatched:0, sent:0, interview_scheduled:0, interview_passed:0, interview_failed:0 }
      for (const d of Object.values(r.daily || {})) {
        totals.companies_created += d.companies_created || 0
        totals.positions_created += d.positions_created || 0
        totals.uploaded += d.uploaded || 0
        totals.matched += d.matched || 0
        totals.unmatched += d.unmatched || 0
        totals.sent += d.sent || 0
        totals.interview_scheduled += d.interview_scheduled || 0
        totals.interview_passed += d.interview_passed || 0
        totals.interview_failed += d.interview_failed || 0
      }
      return totals
    }
  })
})

function toggleRecruiter(id) {
  const idx = selectedRecruiterIds.value.indexOf(id)
  if (idx >= 0) selectedRecruiterIds.value.splice(idx, 1)
  else selectedRecruiterIds.value.push(id)
}
function selectAllRecruiters() {
  if (statsData.value) selectedRecruiterIds.value = statsData.value.recruiters.map(r => r.user_id)
}
function clearRecruiterFilter() {
  selectedRecruiterIds.value = []
}

// 图表数据
const maxDailyValue = computed(() => {
  if (!statsData.value) return 1
  let max = 1
  for (const d of statsData.value.daily_totals) {
    max = Math.max(max, d.uploaded, d.matched, d.sent, d.interview_scheduled)
  }
  return max
})

const maxRecruiterValue = computed(() => {
  if (!statsData.value) return 1
  let max = 1
  for (const r of statsData.value.recruiters) {
    const total = Object.values(r.daily).reduce((s, d) => s + d.uploaded, 0)
    max = Math.max(max, total)
  }
  return max
})

function recruiterTotal(recruiter, key) {
  return Object.values(recruiter.daily).reduce((s, d) => s + d[key], 0)
}

function barHeight(value) {
  return Math.max(2, (value / maxDailyValue.value) * 160) + 'px'
}

function recruiterBarHeight(value) {
  return Math.max(2, (value / maxRecruiterValue.value) * 140) + 'px'
}

function formatDate(dateStr) {
  const d = new Date(dateStr)
  return (d.getMonth() + 1) + '/' + d.getDate()
}

// 趋势图数据（根据模式：单日只展示选中日期，多天展示全部）
const trendData = computed(() => {
  if (!statsData.value) return []
  if (viewMode.value === 'single') {
    const day = statsData.value.daily_totals.find(d => d.date === selectedDate.value)
    return day ? [day] : []
  }
  return statsData.value.daily_totals
})

// 选择日期后切换到单日模式
function onDateChange() {
  showDatePicker.value = false
  viewMode.value = 'single'
  // 计算所选日期距离今天的天数，确保加载范围包含该日期
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const selected = new Date(selectedDate.value)
  selected.setHours(0, 0, 0, 0)
  const diffDays = Math.ceil((today - selected) / (1000 * 60 * 60 * 24))
  days.value = Math.max(30, diffDays + 1)
  loadData()
}

// 切换多天范围
function onRangeChange(dayVal) {
  viewMode.value = 'range'
  days.value = dayVal
  loadData()
}
</script>

<template>
  <div class="stats-page">
    <div class="stats-header">
      <div>
        <h2 class="stats-title">招聘数据</h2>
        <p class="stats-desc">按天统计各招聘人员的简历上传、匹配、发送、面试全流程数据</p>
      </div>
      <div class="days-selector">
        <div class="single-date-wrap">
          <button class="day-btn day-btn-single" :class="{ active: viewMode === 'single' }" @click="showDatePicker = !showDatePicker; viewMode = 'single'">
            📅 单日数据: {{ selectedDate }}
          </button>
          <div v-if="showDatePicker" class="date-picker-dropdown" @click.stop>
            <input type="date" v-model="selectedDate" class="date-input-large" :max="getLocalDateStr()" @change="onDateChange" />
            <div class="date-picker-hint">选择日期后自动刷新数据</div>
          </div>
        </div>
        <div class="range-divider"></div>
        <button v-for="opt in dayOptions" :key="opt.value"
          class="day-btn" :class="{ active: viewMode === 'range' && days === opt.value }"
          @click="onRangeChange(opt.value)">
          {{ opt.label }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading-state">加载中...</div>

    <div v-else-if="statsData" class="stats-content">
      <!-- 汇总卡片 -->
      <div class="summary-container">
        <div class="summary-cards summary-cards-4">
          <div class="summary-card card-indigo">
            <div class="card-icon">🏢</div>
            <div class="card-info">
              <div class="card-value">{{ summary.companies_created }}</div>
              <div class="card-label">录入公司</div>
            </div>
          </div>
          <div class="summary-card card-violet">
            <div class="card-icon">💼</div>
            <div class="card-info">
              <div class="card-value">{{ summary.positions_created }}</div>
              <div class="card-label">录入岗位</div>
            </div>
          </div>
          <div class="summary-card card-blue">
            <div class="card-icon">📤</div>
            <div class="card-info">
              <div class="card-value">{{ summary.uploaded }}</div>
              <div class="card-label">上传简历</div>
            </div>
          </div>
          <div class="summary-card card-green">
            <div class="card-icon">✅</div>
            <div class="card-info">
              <div class="card-value">{{ summary.matched }}</div>
              <div class="card-label">AI成功匹配</div>
            </div>
          </div>
        </div>
        <div class="summary-divider"></div>
        <div class="summary-cards summary-cards-3">
          <div class="summary-card card-orange">
            <div class="card-icon">📧</div>
            <div class="card-info">
              <div class="card-value">{{ summary.sent }}</div>
              <div class="card-label">发送到公司</div>
            </div>
          </div>
          <div class="summary-card card-purple">
            <div class="card-icon">🎯</div>
            <div class="card-info">
              <div class="card-value">{{ summary.interview }}</div>
              <div class="card-label">面试安排</div>
            </div>
          </div>
          <div class="summary-card card-teal">
            <div class="card-icon">📊</div>
            <div class="card-info">
              <div class="card-value">{{ matchRate }}%</div>
              <div class="card-label">匹配率</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 饼图 + 趋势图 并排 -->
      <div class="charts-row">
      <!-- 招聘状态饼图 -->
      <div class="chart-card pie-card">
        <div class="chart-header">
          <h3 class="chart-title">招聘漏斗状态分布</h3>
          <span class="chart-subtitle">各阶段数量占比（总计 {{ pieTotal }}）</span>
        </div>
        <div class="pie-content">
          <div class="pie-chart-wrap">
            <svg width="180" height="180" viewBox="0 0 180 180">
              <circle cx="90" cy="90" r="70" fill="none" stroke="#F1F5F9" stroke-width="28" />
              <path v-for="slice in pieSlices" :key="slice.label"
                :d="slice.path" :fill="slice.color"
                class="pie-slice" :title="slice.label + ': ' + slice.value + ' (' + slice.percent + '%)'" />
              <text x="90" y="82" text-anchor="middle" class="pie-center-value">{{ pieTotal }}</text>
              <text x="90" y="100" text-anchor="middle" class="pie-center-label">总计</text>
            </svg>
          </div>
          <div class="pie-legend">
            <div v-for="slice in pieSlices" :key="slice.label" class="pie-legend-item">
              <span class="pie-legend-dot" :style="{ background: slice.color }"></span>
              <span class="pie-legend-label">{{ slice.label }}</span>
              <span class="pie-legend-value">{{ slice.value }}</span>
              <span class="pie-legend-percent">{{ slice.percent }}%</span>
            </div>
            <div v-if="pieSlices.length === 0" class="pie-empty">暂无数据</div>
          </div>
        </div>
      </div>

      <!-- 趋势图 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">{{ viewMode === 'single' ? '单日数据趋势' : '近' + days + '天工作趋势' }} <span class="chart-hint">（数据多时可左右滑动查看）</span></h3>
        </div>
        <div class="bar-chart">
          <div v-for="day in trendData" :key="day.date" class="bar-group">
            <div class="bar-stack">
              <div class="bar bar-company" :style="{ height: barHeight(day.companies_created || 0) }" :title="`录入公司: ${day.companies_created || 0}`"></div>
              <div class="bar bar-position" :style="{ height: barHeight(day.positions_created || 0) }" :title="`录入岗位: ${day.positions_created || 0}`"></div>
              <div class="bar bar-upload" :style="{ height: barHeight(day.uploaded) }" :title="`上传: ${day.uploaded}`"></div>
              <div class="bar bar-match" :style="{ height: barHeight(day.matched) }" :title="`匹配: ${day.matched}`"></div>
              <div class="bar bar-sent" :style="{ height: barHeight(day.sent) }" :title="`发送: ${day.sent}`"></div>
              <div class="bar bar-interview" :style="{ height: barHeight(day.interview_scheduled) }" :title="`面试: ${day.interview_scheduled}`"></div>
            </div>
            <div class="bar-label">{{ formatDate(day.date) }}</div>
          </div>
        </div>
        <div class="chart-legend" style="justify-content:center; margin-top:16px;">
          <span class="legend-item"><span class="legend-dot" style="background:#6366F1"></span>录入公司</span>
          <span class="legend-item"><span class="legend-dot" style="background:#14B8A6"></span>录入岗位</span>
          <span class="legend-item"><span class="legend-dot" style="background:#3B82F6"></span>上传</span>
          <span class="legend-item"><span class="legend-dot" style="background:#10B981"></span>匹配</span>
          <span class="legend-item"><span class="legend-dot" style="background:#F59E0B"></span>发送</span>
          <span class="legend-item"><span class="legend-dot" style="background:#8B5CF6"></span>面试</span>
        </div>
      </div>
      </div>

      <!-- 各招聘人员对比 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">各招聘人员工作量对比</h3>
          <div class="recruiter-filter-wrap">
            <button class="filter-btn" @click="showRecruiterFilter = !showRecruiterFilter">
              筛选 ({{ selectedRecruiterIds.length }}/{{ statsData.recruiters.length }}) ▾
            </button>
            <div v-if="showRecruiterFilter" class="filter-dropdown" @click.stop>
              <div class="filter-actions">
                <button class="filter-action-btn" @click="selectAllRecruiters">全选</button>
                <button class="filter-action-btn" @click="clearRecruiterFilter">清空</button>
              </div>
              <div class="filter-list">
                <label v-for="r in statsData.recruiters" :key="r.user_id" class="filter-item">
                  <input type="checkbox" :checked="selectedRecruiterIds.includes(r.user_id)" @change="toggleRecruiter(r.user_id)" />
                  <span>{{ r.name }}</span>
                  <span class="filter-item-phone">{{ r.phone }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>
        <div class="recruiter-chart">
          <div v-for="r in dailyDetail" :key="r.user_id" class="recruiter-bar-group">
            <div class="recruiter-bars">
              <div class="recruiter-bar recruiter-bar-company" :style="{ height: recruiterBarHeight(r.companies_created || 0) }" :title="`录入公司: ${r.companies_created || 0}`"></div>
              <div class="recruiter-bar recruiter-bar-position" :style="{ height: recruiterBarHeight(r.positions_created || 0) }" :title="`录入岗位: ${r.positions_created || 0}`"></div>
              <div class="recruiter-bar recruiter-bar-upload" :style="{ height: recruiterBarHeight(r.uploaded) }" :title="`上传: ${r.uploaded}`"></div>
              <div class="recruiter-bar recruiter-bar-match" :style="{ height: recruiterBarHeight(r.matched) }" :title="`匹配: ${r.matched}`"></div>
              <div class="recruiter-bar recruiter-bar-sent" :style="{ height: recruiterBarHeight(r.sent) }" :title="`发送: ${r.sent}`"></div>
            </div>
            <div class="recruiter-name">{{ r.name }}</div>
          </div>
        </div>
        <div class="chart-legend" style="justify-content:center; margin-top:12px;">
          <span class="legend-item"><span class="legend-dot" style="background:#6366F1"></span>录入公司</span>
          <span class="legend-item"><span class="legend-dot" style="background:#14B8A6"></span>录入岗位</span>
          <span class="legend-item"><span class="legend-dot" style="background:#3B82F6"></span>上传</span>
          <span class="legend-item"><span class="legend-dot" style="background:#10B981"></span>匹配</span>
          <span class="legend-item"><span class="legend-dot" style="background:#F59E0B"></span>发送</span>
        </div>
      </div>

      <!-- 详细数据表格 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">各招聘人员详细数据</h3>
        </div>
        <div class="data-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>招聘人员</th>
                <th>录入公司</th>
                <th>录入岗位</th>
                <th>上传简历</th>
                <th>成功匹配</th>
                <th>未匹配</th>
                <th>发送公司</th>
                <th>面试安排</th>
                <th>面试通过</th>
                <th>面试未通过</th>
                <th>匹配率</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in dailyDetail" :key="r.user_id">
                <td class="td-name">{{ r.name }}</td>
                <td class="td-indigo">{{ r.companies_created }}</td>
                <td class="td-violet">{{ r.positions_created }}</td>
                <td>{{ r.uploaded }}</td>
                <td class="td-green">{{ r.matched }}</td>
                <td class="td-red">{{ r.unmatched }}</td>
                <td>{{ r.sent }}</td>
                <td>{{ r.interview_scheduled }}</td>
                <td class="td-green">{{ r.interview_passed }}</td>
                <td class="td-red">{{ r.interview_failed }}</td>
                <td>
                  <span class="rate-badge">
                    {{ (r.matched + r.unmatched) > 0 ? Math.round(r.matched / (r.matched + r.unmatched) * 100) : 0 }}%
                  </span>
                </td>
              </tr>
              <tr v-if="dailyDetail.length === 0">
                <td colspan="11" style="text-align:center; color:#94A3B8; padding:20px;">当日暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-page { padding: 24px; }
.stats-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.stats-title { font-size: 20px; font-weight: 700; color: #1E293B; margin: 0; }
.stats-desc { font-size: 13px; color: #64748B; margin-top: 4px; }
.days-selector { display: flex; gap: 8px; }
.day-btn { padding: 8px 16px; border: 1px solid #E2E8F0; background: #fff; border-radius: 8px; font-size: 13px; cursor: pointer; color: #64748B; }
.day-btn.active { background: #4F46E5; color: #fff; border-color: #4F46E5; }
.day-btn-single { background: linear-gradient(135deg, #8B5CF6 0%, #6366F1 100%); color: #fff; border-color: transparent; font-weight: 600; }
.day-btn-single:hover { opacity: 0.9; }
.range-divider { width: 1px; height: 24px; background: #E2E8F0; margin: 0 4px; }

/* 单日数据按钮和日期选择器 */
.single-date-wrap { position: relative; }
.date-picker-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  z-index: 100;
  min-width: 260px;
}
.date-input-large {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 14px;
  color: #334155;
  background: #fff;
  cursor: pointer;
}
.date-input-large:focus {
  outline: none;
  border-color: #6366F1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
}
.date-picker-hint {
  font-size: 12px;
  color: #94A3B8;
  margin-top: 10px;
  text-align: center;
}

/* 趋势图范围选择器 */
.trend-range-selector { display: flex; gap: 4px; background: #F1F5F9; padding: 3px; border-radius: 8px; }
.range-btn { padding: 5px 12px; font-size: 12px; border: none; background: transparent; color: #64748B; border-radius: 6px; cursor: pointer; transition: all 0.2s; }
.range-btn.active { background: #fff; color: #4F6EF7; font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }

/* 当日数据明细 */
.daily-detail-card { }
.date-selector-wrap { display: flex; align-items: center; gap: 10px; }
.date-label { font-size: 13px; color: #64748B; }
.date-input { padding: 7px 12px; border: 1px solid #E2E8F0; border-radius: 8px; font-size: 13px; color: #334155; background: #fff; cursor: pointer; }
.date-input:focus { outline: none; border-color: #6366F1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
.daily-summary-row { display: flex; gap: 16px; padding: 16px; background: #F8FAFC; border-radius: 10px; margin-bottom: 16px; }
.daily-summary-item { flex: 1; text-align: center; padding: 10px; background: #fff; border-radius: 8px; border: 1px solid #E2E8F0; }
.daily-summary-value { display: block; font-size: 24px; font-weight: 700; color: #1E293B; }
.daily-summary-label { display: block; font-size: 12px; color: #64748B; margin-top: 4px; }
.loading-state { text-align: center; padding: 60px; color: #94A3B8; }
.stats-content { display: flex; flex-direction: column; gap: 16px; }

.summary-container { background: #fff; border: 1px solid #E2E8F0; border-radius: 12px; padding: 10px 12px; }
.summary-cards { display: grid; gap: 8px; }
.summary-divider { height: 1px; background: #F1F5F9; margin: 6px 0; }
.summary-cards-4 { grid-template-columns: repeat(4, 1fr); }
.summary-cards-3 { grid-template-columns: repeat(4, 1fr); }
.summary-card { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 8px; background: #FAFBFC; border-left: 3px solid #CBD5E1; }
.card-indigo { border-left-color: #6366F1; }
.card-violet { border-left-color: #8B5CF6; }
.card-blue { border-left-color: #3B82F6; }
.card-green { border-left-color: #10B981; }
.card-orange { border-left-color: #F59E0B; }
.card-purple { border-left-color: #8B5CF6; }
.card-teal { border-left-color: #14B8A6; }
.card-icon { font-size: 22px; }
.card-value { font-size: 20px; font-weight: 700; color: #1E293B; }
.card-label { font-size: 12px; color: #64748B; margin-top: 2px; }

.chart-card { background: #fff; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; min-width: 0; overflow: hidden; }
.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.chart-title { font-size: 15px; font-weight: 600; color: #1E293B; margin: 0; }
.chart-legend { display: flex; gap: 16px; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #64748B; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; }

.bar-chart { display: flex; align-items: flex-end; gap: 10px; height: 240px; padding: 0 8px 12px; overflow-x: auto; scrollbar-width: thin; scrollbar-color: #CBD5E1 transparent; }
.bar-chart::-webkit-scrollbar { height: 6px; }
.bar-chart::-webkit-scrollbar-track { background: #F1F5F9; border-radius: 3px; }
.bar-chart::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
.bar-chart::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
.bar-group { display: flex; flex-direction: column; align-items: center; min-width: 80px; width: 80px; flex-shrink: 0; }
.bar-stack { display: flex; align-items: flex-end; gap: 4px; height: 180px; }
.bar { width: 9px; border-radius: 2px 2px 0 0; transition: height 0.3s; }
.bar-company { background: #6366F1; }
.bar-position { background: #14B8A6; }
.bar-upload { background: #3B82F6; }
.bar-match { background: #10B981; }
.bar-sent { background: #F59E0B; }
.bar-interview { background: #8B5CF6; }
.bar-label { font-size: 11px; color: #94A3B8; margin-top: 8px; }

.recruiter-chart { display: flex; align-items: flex-end; justify-content: flex-start; gap: 32px; height: 220px; padding: 0 20px 12px; overflow-x: auto; scrollbar-width: thin; scrollbar-color: #CBD5E1 transparent; }
.recruiter-chart::-webkit-scrollbar { height: 6px; }
.recruiter-chart::-webkit-scrollbar-track { background: #F1F5F9; border-radius: 3px; }
.recruiter-chart::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
.recruiter-chart::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
.recruiter-bar-group { display: flex; flex-direction: column; align-items: center; min-width: 130px; width: 130px; flex-shrink: 0; }
.recruiter-bars { display: flex; align-items: flex-end; gap: 6px; height: 160px; }
.recruiter-bar { width: 18px; border-radius: 3px 3px 0 0; }
.recruiter-bar-company { background: #6366F1; }
.recruiter-bar-position { background: #14B8A6; }
.recruiter-bar-upload { background: #3B82F6; }
.recruiter-bar-match { background: #10B981; }
.recruiter-bar-sent { background: #F59E0B; }
.recruiter-name { font-size: 13px; color: #475569; margin-top: 10px; font-weight: 500; }

.data-table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th { background: #F8FAFC; padding: 10px 12px; text-align: center; font-weight: 600; color: #475569; border-bottom: 2px solid #E2E8F0; }
.data-table td { padding: 10px 12px; text-align: center; border-bottom: 1px solid #F1F5F9; color: #334155; }
.data-table tr:hover { background: #F8FAFC; }
.td-name { font-weight: 600; color: #1E293B; text-align: left !important; }
.td-green { color: #059669; font-weight: 600; }
.td-red { color: #DC2626; }
.td-indigo { color: #6366F1; font-weight: 600; }
.td-violet { color: #8B5CF6; font-weight: 600; }
.rate-badge { display: inline-block; padding: 3px 10px; background: #EEF2FF; color: #4F46E5; border-radius: 12px; font-weight: 600; font-size: 12px; }

/* 饼图 */
.pie-card { }
.pie-content {
  display: flex;
  align-items: center;
  gap: 40px;
  justify-content: center;
}
.pie-chart-wrap {
  position: relative;
}
.pie-slice {
  transition: opacity 0.2s;
  cursor: pointer;
}
.pie-slice:hover {
  opacity: 0.8;
}
.pie-center-value {
  font-size: 28px;
  font-weight: 700;
  fill: #1E293B;
}
.pie-center-label {
  font-size: 11px;
  fill: #94A3B8;
}
.pie-legend {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 200px;
}
.pie-legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.pie-legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  flex-shrink: 0;
}
.pie-legend-label {
  color: #475569;
  flex: 1;
}
.pie-legend-value {
  font-weight: 600;
  color: #1E293B;
  min-width: 35px;
  text-align: right;
}
.pie-legend-percent {
  color: #94A3B8;
  font-size: 12px;
  min-width: 50px;
  text-align: right;
}
.pie-empty {
  color: #94A3B8;
  font-size: 13px;
  text-align: center;
  padding: 20px;
}

/* 饼图+趋势图并排 */
.charts-row {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.pie-card { margin-bottom: 0; }
.pie-content {
  flex-direction: column;
  gap: 16px;
}
.pie-chart-wrap svg {
  width: 140px;
  height: 140px;
}
.pie-legend {
  min-width: auto;
  gap: 8px;
}

/* 招聘人员筛选 */
.recruiter-filter-wrap { position: relative; }
.filter-btn {
  padding: 6px 14px;
  background: #fff;
  border: 1px solid #CBD5E1;
  border-radius: 6px;
  font-size: 12px;
  color: #475569;
  cursor: pointer;
}
.filter-btn:hover { border-color: #4F6EF7; color: #4F6EF7; }
.filter-dropdown {
  position: absolute;
  right: 0;
  top: 100%;
  margin-top: 6px;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  z-index: 100;
  min-width: 240px;
  max-height: 320px;
  display: flex;
  flex-direction: column;
}
.filter-actions {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #F1F5F9;
}
.filter-action-btn {
  padding: 4px 10px;
  font-size: 11px;
  border: 1px solid #E2E8F0;
  background: #F8FAFC;
  border-radius: 4px;
  cursor: pointer;
  color: #475569;
}
.filter-action-btn:hover { background: #EEF2FF; color: #4F6EF7; border-color: #C7D2FE; }
.filter-list {
  overflow-y: auto;
  padding: 6px 0;
}
.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #334155;
}
.filter-item:hover { background: #F8FAFC; }
.filter-item input[type="checkbox"] { accent-color: #4F6EF7; width: 14px; height: 14px; }
.filter-item-phone { margin-left: auto; font-size: 11px; color: #94A3B8; }
</style>
