<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { resumeApi, positionApi, companyApi, feedbackApi } from '../api/index.js'

const getMatchViewParams = inject('getMatchViewParams', () => null)
const clearMatchViewParams = inject('clearMatchViewParams', () => {})
const showAlert = inject('showAlert')
const showConfirm = inject('showConfirm')

// 状态
const loading = ref(false)
const matching = ref(false)
const exporting = ref(false)
const rematchingId = ref(null)
const matchResults = ref([])
const positions = ref([])
const companies = ref([])
const resumes = ref([])
const viewMode = ref('list')
const displayMode = ref('view') // view | simple  视图模式/简洁模式  // 'list' | 'grouped' | 'groupedByOwner' | 'groupedByDate'
const expandedGroups = ref({})  // 分组展开状态
const loadMoreGroups = ref({})  // 分组"加载更多"状态
const allGroupsCollapsed = ref(false)  // 全局折叠状态
const allLoadMore = ref(false)  // 全局加载更多状态
const GROUP_PAGE_SIZE = 5  // 每个分组默认展示条数

// 筛选条件
const filterCompany = ref('')
const filterPosition = ref([])
const showPositionDropdown = ref(false)
const filterPassed = ref('')
const filterMinScore = ref('')
const filterName = ref('')
const filterOwner = ref([])
const showOwnerDropdown = ref(false)
// 本次匹配的简历ID筛选（从简历筛选中心跳转过来时设置）
const filterResumeIds = ref(null)

// 分页
const currentPage = ref(1)
const pageSize = 10
const selectedResultIds = ref([])
// 简洁模式加载更多
const simpleVisibleCount = ref(20)
const SIMPLE_PAGE_SIZE = 20
const sending = ref(false)
const sendMessage = ref('')

// 详情弹窗
const showDetail = ref(false)
const currentDetail = ref(null)
const detailTab = ref('match')  // match / review / interview

// 人工评价
const manualReview = ref(null)
const reviewForm = ref({
  hr_rating: 3,
  hr_comment: '',
  ai_score_correction: null,
  ai_deviation_type: '',
  reviewer_name: ''
})
const savingReview = ref(false)

// 面试反馈
const interviewFeedback = ref(null)
const interviewForm = ref({
  interview_result: '待定',
  interview_scheduled: false,
  fail_reasons: [],
  custom_note: '',
  interviewer: '',
  interview_date: ''
})
const savingInterview = ref(false)

const failReasonOptions = [
  '技能不匹配', '经验不足', '学历不达标', '薪资期望不符',
  '文化契合度低', '沟通表达欠佳', '稳定性不足', '职业规划不符', '其他'
]

// 计算属性
// 根据选中公司过滤岗位列表
const filteredPositions = computed(() => {
  if (!filterCompany.value) return positions.value
  // 找到选中公司的id
  const company = companies.value.find(c => c.name === filterCompany.value)
  if (!company) return []
  return positions.value.filter(p => p.company_id === company.id)
})

// 切换公司时清空已选岗位
function onCompanyChange() {
  filterPosition.value = []
  currentPage.value = 1
}

// 岗位多选切换
function togglePosition(posName) {
  const idx = filterPosition.value.indexOf(posName)
  if (idx > -1) {
    filterPosition.value.splice(idx, 1)
  } else {
    filterPosition.value.push(posName)
  }
}

// 岗位显示文本
const positionFilterText = computed(() => {
  if (filterPosition.value.length === 0) return '全部岗位'
  if (filterPosition.value.length === 1) return filterPosition.value[0]
  return `已选${filterPosition.value.length}个岗位`
})

const filteredResults = computed(() => {
  let list = matchResults.value
  // 本次匹配的简历ID筛选
  if (filterResumeIds.value && filterResumeIds.value.length > 0) {
    list = list.filter(r => filterResumeIds.value.includes(r.resume_id))
  }
  if (filterCompany.value) {
    list = list.filter(r => r.company_name === filterCompany.value)
  }
  if (filterPosition.value.length > 0) {
    list = list.filter(r => filterPosition.value.includes(r.position_name))
  }
  if (filterPassed.value !== '') {
    list = list.filter(r => r.passed_hard === (filterPassed.value === 'true'))
  }
  if (filterMinScore.value) {
    list = list.filter(r => r.total_score >= parseInt(filterMinScore.value))
  }
  if (filterName.value.trim()) {
    const keyword = filterName.value.trim().toLowerCase()
    list = list.filter(r => (r.candidate_name || '').toLowerCase().includes(keyword))
  }
  if (filterOwner.value.length > 0) {
    list = list.filter(r => {
      const ownerInfo = resumeOwnerMap.value[r.resume_id] || { owner_name: '未分配' }
      return filterOwner.value.includes(ownerInfo.owner_name)
    })
  }
  return list
})

// 简历owner映射：通过resume_id查找招聘人员
const resumeOwnerMap = computed(() => {
  const map = {}
  for (const r of resumes.value) {
    map[r.id] = { owner_id: r.owner_id, owner_name: r.owner_name || '未分配' }
  }
  return map
})

// 招聘人员列表（从简历中提取唯一的owner_name）
const ownerOptions = computed(() => {
  const names = new Set()
  for (const r of resumes.value) {
    if (r.owner_name) names.add(r.owner_name)
  }
  return Array.from(names).sort()
})

// 切换招聘人员多选
function toggleOwner(ownerName) {
  const idx = filterOwner.value.indexOf(ownerName)
  if (idx >= 0) filterOwner.value.splice(idx, 1)
  else filterOwner.value.push(ownerName)
  currentPage.value = 1
}

// 招聘人员筛选显示文本
const ownerFilterText = computed(() => {
  if (filterOwner.value.length === 0) return '全部上传人'
  if (filterOwner.value.length === 1) return filterOwner.value[0]
  return `已选 ${filterOwner.value.length} 人`
})

// ========== 按上传时间统计 ==========
function getDateStr(d) {
  const dt = new Date(d)
  const y = dt.getFullYear()
  const m = String(dt.getMonth() + 1).padStart(2, '0')
  const day = String(dt.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
function isToday(dateStr) { return dateStr === getDateStr(new Date()) }
function isYesterday(dateStr) {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return dateStr === getDateStr(d)
}
function isThisWeek(dateStr) {
  const d = new Date(dateStr)
  const now = new Date()
  const dayOfWeek = now.getDay() || 7
  const monday = new Date(now)
  monday.setDate(now.getDate() - dayOfWeek + 1)
  monday.setHours(0, 0, 0, 0)
  return d >= monday
}

// 简历上传日期映射
const resumeUploadDateMap = computed(() => {
  const map = {}
  for (const r of resumes.value) {
    if (r.created_at) map[r.id] = getDateStr(r.created_at)
  }
  return map
})

// 上传统计概览
const uploadStats = computed(() => {
  const stats = {
    today: { uploaded: 0, matched: 0, resumeIds: new Set() },
    yesterday: { uploaded: 0, matched: 0, resumeIds: new Set() },
    thisWeek: { uploaded: 0, matched: 0, resumeIds: new Set() },
    total: { uploaded: 0, matched: 0, resumeIds: new Set() },
  }
  for (const r of filteredResults.value) {
    const dateStr = resumeUploadDateMap.value[r.resume_id]
    if (!dateStr) continue
    // 累计
    stats.total.matched++
    stats.total.resumeIds.add(r.resume_id)
    if (isToday(dateStr)) {
      stats.today.matched++
      stats.today.resumeIds.add(r.resume_id)
    }
    if (isYesterday(dateStr)) {
      stats.yesterday.matched++
      stats.yesterday.resumeIds.add(r.resume_id)
    }
    if (isThisWeek(dateStr)) {
      stats.thisWeek.matched++
      stats.thisWeek.resumeIds.add(r.resume_id)
    }
  }
  // 上传简历数（去重）
  stats.today.uploaded = stats.today.resumeIds.size
  stats.yesterday.uploaded = stats.yesterday.resumeIds.size
  stats.thisWeek.uploaded = stats.thisWeek.resumeIds.size
  stats.total.uploaded = stats.total.resumeIds.size
  return stats
})

// 按上传日期分组的匹配结果
const groupedByDate = computed(() => {
  const groups = {}
  for (const r of filteredResults.value) {
    const dateStr = resumeUploadDateMap.value[r.resume_id] || '未知日期'
    if (!groups[dateStr]) {
      groups[dateStr] = {
        date: dateStr,
        results: [],
        resumeIds: new Set(),
        total_count: 0,
        passed_count: 0,
        avg_score: 0,
        expanded: !allGroupsCollapsed.value && expandedGroups.value['date_' + dateStr] !== false,
      }
    }
    groups[dateStr].results.push(r)
    groups[dateStr].resumeIds.add(r.resume_id)
  }
  // 转换为数组并计算统计
  const result = []
  for (const dateStr in groups) {
    const g = groups[dateStr]
    g.total_count = g.results.length
    g.uploaded_count = g.resumeIds.size
    g.passed_count = g.results.filter(r => r.passed_hard).length
    g.avg_score = g.total_count > 0 ? Math.round(g.results.reduce((s, r) => s + r.total_score, 0) / g.total_count) : 0
    g.results.sort((a, b) => b.total_score - a.total_score)
    result.push(g)
  }
  result.sort((a, b) => b.date.localeCompare(a.date))
  return result
})

// 日期显示文本（今天/昨天/具体日期）
function formatDateLabel(dateStr) {
  if (isToday(dateStr)) return '今天 (' + dateStr + ')'
  if (isYesterday(dateStr)) return '昨天 (' + dateStr + ')'
  return dateStr
}

// 分数样式分类
function scoreClass(score) {
  if (score >= 80) return 'high'
  if (score >= 60) return 'mid'
  return 'low'
}

// 获取面试状态文本（简洁模式用）
function getInterviewStatusSimple(r) {
  if (r.interview_result === '通过') return '面试通过'
  if (r.interview_result === '不通过') return '面试不通过'
  if (r.interview_scheduled) return '已安排面试'
  return '未安排'
}

// 简洁模式统计辅助函数
function simpleCompanyTotal(company) {
  return company.positions.reduce((s, p) => s + p.owners.reduce((s2, o) => s2 + o.results.length, 0), 0)
}
function simpleCompanyPassed(company) {
  return company.positions.reduce((s, p) => s + p.owners.reduce((s2, o) => s2 + o.results.filter(r => r.passed_hard).length, 0), 0)
}
function simplePositionTotal(position) {
  return position.owners.reduce((s, o) => s + o.results.length, 0)
}
function simpleOwnerGroupTotal(owner) {
  return owner.companies.reduce((s, c) => s + c.positions.reduce((s2, p) => s2 + p.results.length, 0), 0)
}
function simpleOwnerGroupAvg(owner) {
  let total = 0, count = 0
  for (const c of owner.companies) {
    for (const p of c.positions) {
      for (const r of p.results) {
        total += r.total_score
        count++
      }
    }
  }
  return count > 0 ? Math.round(total / count) : 0
}
function simpleCompanyGroupTotal(company) {
  return company.positions.reduce((s, p) => s + p.results.length, 0)
}

// 分组结果：按公司→职位→招聘人员分组
const groupedResults = computed(() => {
  const groups = {}
  for (const r of filteredResults.value) {
    const companyName = r.company_name || '未知公司'
    const positionName = r.position_name || '未知职位'
    const ownerInfo = resumeOwnerMap.value[r.resume_id] || { owner_name: '未分配' }
    const ownerName = ownerInfo.owner_name

    if (!groups[companyName]) groups[companyName] = {}
    if (!groups[companyName][positionName]) groups[companyName][positionName] = {}
    if (!groups[companyName][positionName][ownerName]) {
      groups[companyName][positionName][ownerName] = {
        company_name: companyName,
        position_name: positionName,
        owner_name: ownerName,
        results: [],
        avg_score: 0,
        passed_count: 0,
        total_count: 0
      }
    }
    groups[companyName][positionName][ownerName].results.push(r)
  }

  // 转换为数组并计算统计
  const result = []
  for (const companyName in groups) {
    const companyGroup = { name: companyName, positions: [], expanded: !allGroupsCollapsed.value && expandedGroups.value['company_' + companyName] !== false }
    for (const positionName in groups[companyName]) {
      const positionGroup = { name: positionName, owners: [], expanded: !allGroupsCollapsed.value && expandedGroups.value['pos_' + companyName + '_' + positionName] !== false }
      for (const ownerName in groups[companyName][positionName]) {
        const g = groups[companyName][positionName][ownerName]
        g.total_count = g.results.length
        g.passed_count = g.results.filter(r => r.passed_hard).length
        g.avg_score = g.total_count > 0 ? Math.round(g.results.reduce((s, r) => s + r.total_score, 0) / g.total_count) : 0
        g.results.sort((a, b) => b.total_score - a.total_score)
        positionGroup.owners.push(g)
      }
      positionGroup.owners.sort((a, b) => b.avg_score - a.avg_score)
      companyGroup.positions.push(positionGroup)
    }
    companyGroup.positions.sort((a, b) => a.name.localeCompare(b.name))
    result.push(companyGroup)
  }
  result.sort((a, b) => a.name.localeCompare(b.name))
  return result
})

// 分组结果：按招聘人员→公司→职位分组
const groupedByOwnerResults = computed(() => {
  const groups = {}
  for (const r of filteredResults.value) {
    const ownerInfo = resumeOwnerMap.value[r.resume_id] || { owner_name: '未分配' }
    const ownerName = ownerInfo.owner_name
    const companyName = r.company_name || '未知公司'
    const positionName = r.position_name || '未知职位'

    if (!groups[ownerName]) groups[ownerName] = {}
    if (!groups[ownerName][companyName]) groups[ownerName][companyName] = {}
    if (!groups[ownerName][companyName][positionName]) {
      groups[ownerName][companyName][positionName] = {
        owner_name: ownerName,
        company_name: companyName,
        position_name: positionName,
        results: [],
        avg_score: 0,
        passed_count: 0,
        total_count: 0
      }
    }
    groups[ownerName][companyName][positionName].results.push(r)
  }

  // 转换为数组并计算统计
  const result = []
  for (const ownerName in groups) {
    const ownerGroup = { name: ownerName, companies: [], expanded: !allGroupsCollapsed.value && expandedGroups.value['owner_' + ownerName] !== false }
    for (const companyName in groups[ownerName]) {
      const companyGroup = { name: companyName, positions: [], expanded: !allGroupsCollapsed.value && expandedGroups.value['ownerCompany_' + ownerName + '_' + companyName] !== false }
      for (const positionName in groups[ownerName][companyName]) {
        const g = groups[ownerName][companyName][positionName]
        g.total_count = g.results.length
        g.passed_count = g.results.filter(r => r.passed_hard).length
        g.avg_score = g.total_count > 0 ? Math.round(g.results.reduce((s, r) => s + r.total_score, 0) / g.total_count) : 0
        g.results.sort((a, b) => b.total_score - a.total_score)
        companyGroup.positions.push(g)
      }
      companyGroup.positions.sort((a, b) => b.avg_score - a.avg_score)
      ownerGroup.companies.push(companyGroup)
    }
    ownerGroup.companies.sort((a, b) => a.name.localeCompare(b.name))
    result.push(ownerGroup)
  }
  result.sort((a, b) => a.name.localeCompare(b.name))
  return result
})

function toggleGroup(groupKey) {
  const currentExpanded = !allGroupsCollapsed.value && expandedGroups.value[groupKey] !== false
  allGroupsCollapsed.value = false
  expandedGroups.value[groupKey] = !currentExpanded
}

// 切换分组"加载更多"状态
function toggleLoadMore(groupKey) {
  allLoadMore.value = false
  loadMoreGroups.value[groupKey] = !loadMoreGroups.value[groupKey]
}

// 判断分组是否处于加载更多状态
function isGroupLoadMore(groupKey) {
  return allLoadMore.value || !!loadMoreGroups.value[groupKey]
}

// 获取分组可见的结果（默认前GROUP_PAGE_SIZE条，加载更多后展示全部）
function getGroupVisibleResults(results, groupKey) {
  if (allLoadMore.value || loadMoreGroups.value[groupKey]) return results
  return results.slice(0, GROUP_PAGE_SIZE)
}

// 全部折叠所有分组
function collapseAllGroups() {
  allGroupsCollapsed.value = true
  allLoadMore.value = false
  expandedGroups.value = {}
  loadMoreGroups.value = {}
}

// 全部展开所有分组
function expandAllGroups() {
  allGroupsCollapsed.value = false
  allLoadMore.value = true
  expandedGroups.value = {}
  loadMoreGroups.value = {}
}

const totalPages = computed(() => Math.max(1, Math.ceil(filteredResults.value.length / pageSize)))
const pagedResults = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredResults.value.slice(start, start + pageSize)
})
const pagedResultIds = computed(() => pagedResults.value.map(r => r.id))
const isAllSelected = computed(() => pagedResultIds.value.length > 0 && pagedResultIds.value.every(id => selectedResultIds.value.includes(id)))

// 简洁模式列表视图：加载更多
const simpleListResults = computed(() => filteredResults.value.slice(0, simpleVisibleCount.value))
const simpleListIds = computed(() => simpleListResults.value.map(r => r.id))
const isSimpleAllSelected = computed(() => simpleListIds.value.length > 0 && simpleListIds.value.every(id => selectedResultIds.value.includes(id)))
function loadMoreSimpleList() {
  simpleVisibleCount.value += SIMPLE_PAGE_SIZE
}
function toggleSimpleSelectAll() {
  if (isSimpleAllSelected.value) {
    selectedResultIds.value = selectedResultIds.value.filter(id => !simpleListIds.value.includes(id))
  } else {
    for (const id of simpleListIds.value) {
      if (!selectedResultIds.value.includes(id)) {
        selectedResultIds.value.push(id)
      }
    }
  }
}
// 简洁模式分组视图：分组级全选
function isGroupAllSelected(results) {
  if (!results || results.length === 0) return false
  return results.every(r => selectedResultIds.value.includes(r.id))
}
function toggleGroupSelectAllSimple(results) {
  if (!results) return
  if (isGroupAllSelected(results)) {
    for (const r of results) {
      const idx = selectedResultIds.value.indexOf(r.id)
      if (idx >= 0) selectedResultIds.value.splice(idx, 1)
    }
  } else {
    for (const r of results) {
      if (!selectedResultIds.value.includes(r.id)) {
        selectedResultIds.value.push(r.id)
      }
    }
  }
}
const selectedCount = computed(() => selectedResultIds.value.length)
function goPage(p) {
  if (p < 1 || p > totalPages.value) return
  currentPage.value = p
}

const stats = computed(() => {
  const list = filteredResults.value
  if (list.length === 0) return { total: 0, passed: 0, avgScore: 0, highMatch: 0 }
  const passed = list.filter(r => r.passed_hard).length
  const avgScore = Math.round(list.reduce((s, r) => s + r.total_score, 0) / list.length)
  const highMatch = list.filter(r => r.total_score >= 80).length
  return { total: list.length, passed, avgScore, highMatch }
})

// 维度配置
const dimensions = [
  { key: 'education_score', label: '学历', color: '#4F6EF7' },
  { key: 'experience_score', label: '工作年限', color: '#10B981' },
  { key: 'skill_score', label: '核心技能', color: '#F59E0B' },
  { key: 'industry_score', label: '行业经验', color: '#8B5CF6' },
  { key: 'project_score', label: '项目经验', color: '#0EA5E9' },
  { key: 'certificate_score', label: '证书', color: '#EF4444' },
]

// 加载数据
async function loadData() {
  loading.value = true
  try {
    // 并行加载岗位、公司、匹配结果、简历列表
    const [posList, compList, results, resumeList] = await Promise.all([
      positionApi.list(),
      companyApi.list(),
      resumeApi.matchResults(),
      resumeApi.list()
    ])
    positions.value = posList
    companies.value = compList
    matchResults.value = results
    resumes.value = resumeList
  } catch (e) {
    console.error('加载数据失败:', e)
  } finally {
    loading.value = false
  }
}

// 对所有简历执行全域匹配
async function matchAllResumes() {
  const confirmed = await showConfirm('将对所有已解析简历执行全域匹配，可能需要一些时间，是否继续？', '全域匹配确认', 'info')
  if (!confirmed) return

  matching.value = true
  try {
    // 先获取简历列表
    const resumeList = await resumeApi.list()
    const parsedResumes = resumeList.filter(r => r.status === '已解析')

    let successCount = 0
    for (const resume of parsedResumes) {
      try {
        await resumeApi.matchAll(resume.id)
        successCount++
      } catch (e) {
        console.error(`简历 ${resume.id} 匹配失败:`, e)
      }
    }

    showAlert(`匹配完成！成功处理 ${successCount}/${parsedResumes.length} 份简历`, 'success', '匹配完成')
    await loadData()
  } catch (e) {
    showAlert('匹配失败: ' + e.message, 'error')
  } finally {
    matching.value = false
  }
}

// 查看详情
async function openDetail(result) {
  currentDetail.value = result
  showDetail.value = true
  detailTab.value = 'match'
  // 加载人工评价
  try {
    const review = await feedbackApi.getManualReview(result.id)
    manualReview.value = review
    if (review) {
      reviewForm.value = {
        hr_rating: review.hr_rating,
        hr_comment: review.hr_comment || '',
        ai_score_correction: review.ai_score_correction,
        ai_deviation_type: review.ai_deviation_type || '',
        reviewer_name: review.reviewer_name || ''
      }
    } else {
      reviewForm.value = { hr_rating: 3, hr_comment: '', ai_score_correction: null, ai_deviation_type: '', reviewer_name: '' }
    }
  } catch (e) {
    manualReview.value = null
  }
  // 加载面试反馈
  try {
    const feedback = await feedbackApi.getInterviewFeedback(result.id)
    interviewFeedback.value = feedback
    if (feedback) {
      interviewForm.value = {
        interview_result: feedback.interview_result,
        interview_scheduled: currentDetail.value?.interview_scheduled || false,
        fail_reasons: feedback.fail_reasons ? feedback.fail_reasons.split(',').filter(Boolean) : [],
        custom_note: feedback.custom_note || '',
        interviewer: feedback.interviewer || '',
        interview_date: feedback.interview_date || ''
      }
    } else {
      interviewForm.value = { interview_result: '待定', interview_scheduled: currentDetail.value?.interview_scheduled || false, fail_reasons: [], custom_note: '', interviewer: '', interview_date: '' }
    }
  } catch (e) {
    interviewFeedback.value = null
  }
}

// 保存人工评价
async function saveManualReview() {
  savingReview.value = true
  try {
    const data = {
      match_result_id: currentDetail.value.id,
      hr_rating: reviewForm.value.hr_rating,
      hr_comment: reviewForm.value.hr_comment,
      ai_score_correction: reviewForm.value.ai_score_correction,
      ai_deviation_type: reviewForm.value.ai_deviation_type || null,
      reviewer_name: reviewForm.value.reviewer_name || null
    }
    const result = await feedbackApi.createManualReview(data)
    manualReview.value = result
    showAlert('人工评价保存成功！', 'success')
  } catch (e) {
    showAlert('保存失败: ' + e.message, 'error')
  } finally {
    savingReview.value = false
  }
}

// 切换面试安排状态
async function toggleInterviewScheduled() {
  console.log('[面试安排开关] 点击触发, currentDetail:', currentDetail.value?.id, '当前值:', interviewForm.value.interview_scheduled)
  if (!currentDetail.value) {
    console.log('[面试安排开关] currentDetail为空，退出')
    return
  }
  const newVal = !interviewForm.value.interview_scheduled
  console.log('[面试安排开关] 准备切换为:', newVal)
  try {
    await resumeApi.toggleInterviewScheduled(currentDetail.value.id, newVal)
    interviewForm.value.interview_scheduled = newVal
    currentDetail.value.interview_scheduled = newVal
    if (newVal) {
      currentDetail.value.interview_scheduled_at = new Date().toISOString()
    } else {
      currentDetail.value.interview_scheduled_at = null
    }
    // 同步更新列表中的数据
    const item = filteredResults.value.find(x => x.id === currentDetail.value.id)
    if (item) {
      item.interview_scheduled = newVal
      item.interview_scheduled_at = currentDetail.value.interview_scheduled_at
    }
  } catch (e) {
    console.error('[面试安排开关] 错误:', e)
    showAlert('操作失败: ' + (e.message || e), 'error')
  }
}

// 保存面试反馈
async function saveInterviewFeedback() {
  savingInterview.value = true
  try {
    const data = {
      match_result_id: currentDetail.value.id,
      interview_result: interviewForm.value.interview_result,
      fail_reasons: interviewForm.value.fail_reasons.join(','),
      custom_note: interviewForm.value.custom_note,
      interviewer: interviewForm.value.interviewer || null,
      interview_date: interviewForm.value.interview_date ? new Date(interviewForm.value.interview_date).toISOString() : null
    }
    const result = await feedbackApi.createInterviewFeedback(data)
    interviewFeedback.value = result
    showAlert('面试反馈保存成功！系统将自动学习此反馈数据。', 'success', '保存成功')
  } catch (e) {
    showAlert('保存失败: ' + e.message, 'error')
  } finally {
    savingInterview.value = false
  }
}

// 格式化日期
function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  } catch (e) {
    return dateStr
  }
}

// 切换失败原因
function toggleFailReason(reason) {
  const idx = interviewForm.value.fail_reasons.indexOf(reason)
  if (idx > -1) {
    interviewForm.value.fail_reasons.splice(idx, 1)
  } else {
    interviewForm.value.fail_reasons.push(reason)
  }
}

function closeDetail() {
  showDetail.value = false
  currentDetail.value = null
}

// 解析match_details_json
function getMatchDetails(result) {
  if (!result.match_details_json) return []
  try {
    return JSON.parse(result.match_details_json)
  } catch {
    return []
  }
}

// 分数等级
function scoreLevel(score) {
  if (score >= 80) return 'high'
  if (score >= 60) return 'mid'
  return 'low'
}

function scoreText(score) {
  if (score >= 80) return '高度匹配'
  if (score >= 60) return '基本匹配'
  return '匹配度低'
}

// 重置筛选
function resetFilters() {
  filterCompany.value = ''
  filterPosition.value = []
  filterPassed.value = ''
  filterMinScore.value = ''
  filterName.value = ''
  filterOwner.value = []
  currentPage.value = 1
}

// 删除单条匹配结果
function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedResultIds.value = selectedResultIds.value.filter(id => !pagedResultIds.value.includes(id))
  } else {
    for (const id of pagedResultIds.value) {
      if (!selectedResultIds.value.includes(id)) {
        selectedResultIds.value.push(id)
      }
    }
  }
}
function toggleSelect(id) {
  const idx = selectedResultIds.value.indexOf(id)
  if (idx >= 0) selectedResultIds.value.splice(idx, 1)
  else selectedResultIds.value.push(id)
}
function isAllGroupSelected(results) {
  if (!results || results.length === 0) return false
  return results.every(r => selectedResultIds.value.includes(r.id))
}
function toggleGroupSelectAll(results) {
  if (!results) return
  if (isAllGroupSelected(results)) {
    // 取消全选
    for (const r of results) {
      const idx = selectedResultIds.value.indexOf(r.id)
      if (idx >= 0) selectedResultIds.value.splice(idx, 1)
    }
  } else {
    // 全选
    for (const r of results) {
      if (!selectedResultIds.value.includes(r.id)) {
        selectedResultIds.value.push(r.id)
      }
    }
  }
}
function clearSelection() {
  selectedResultIds.value = []
}
async function sendToCompany(result) {
  const action = result.sent_to_company ? '再次发送' : '发送'
  const confirmed = await showConfirm(`确定将 ${result.resume_name} 的匹配结果${action}到 ${result.company_name} 的邮箱吗？`, '发送确认', 'info')
  if (!confirmed) return
  try {
    const resp = await resumeApi.sendMatchToCompany(result.id)
    if (resp.email_sent) {
      result.sent_to_company = true
      result.sent_at = new Date().toISOString()
      showAlert('✓ 已成功发送到公司邮箱：' + (resp.company_email || ''), 'success', '发送成功')
    } else {
      showAlert('⚠ 邮件未真实发送：' + (resp.message || '未知原因'), 'warning', '发送提示')
      result.sent_to_company = true
      result.sent_at = new Date().toISOString()
    }
  } catch (e) {
    showAlert('发送失败: ' + (e.message || e), 'error')
  }
}
async function batchSendToCompany() {
  if (selectedResultIds.value.length === 0) return
  const confirmed = await showConfirm(`确定将选中的 ${selectedResultIds.value.length} 条匹配结果发送到对应公司邮箱吗？`, '批量发送确认', 'info')
  if (!confirmed) return
  sending.value = true
  sendMessage.value = ''
  try {
    const result = await resumeApi.batchSendToCompany(selectedResultIds.value)
    sendMessage.value = `成功发送 ${result.success_count} 条，失败 ${result.failed_count} 条`
    // 更新已发送状态
    for (const item of result.success || []) {
      const r = filteredResults.value.find(x => x.id === item.id)
      if (r) { r.sent_to_company = true; r.sent_at = new Date().toISOString() }
    }
    clearSelection()
    setTimeout(() => { sendMessage.value = '' }, 5000)
  } catch (e) {
    sendMessage.value = '批量发送失败: ' + (e.message || e)
  } finally {
    sending.value = false
  }
}

// 专项匹配：重新匹配该简历与该岗位
async function rematchPosition(result) {
  const confirmed = await showConfirm(`确定要重新匹配「${result.resume_name} → ${result.position_name}」吗？将基于最新的Schema配置重新计算匹配分数。`, '重新匹配确认', 'info')
  if (!confirmed) return
  rematchingId.value = result.id
  try {
    const matchResult = await resumeApi.matchPosition(result.resume_id, result.position_id)
    // 刷新数据
    await loadMatchResults()
    // 显示匹配结果提示
    const passedText = matchResult.passed_hard ? '满足硬性条件' : '不满足硬性条件'
    showAlert(`重新匹配完成！\n候选人：${matchResult.candidate_name}\n岗位：${matchResult.position_name}\n匹配分数：${matchResult.total_score}分\n${passedText}\n匹配方式：${matchResult.match_method === 'ai' ? 'AI匹配' : '规则降级'}`, 'success', '匹配完成')
  } catch (e) {
    showAlert('重新匹配失败: ' + (e.message || e), 'error')
  } finally {
    rematchingId.value = null
  }
}

async function deleteResult(result) {
  const confirmed = await showConfirm(`确定要删除「${result.resume_name} → ${result.position_name}」的匹配结果吗？此操作不可恢复。`, '删除确认', 'warning')
  if (!confirmed) return
  try {
    await resumeApi.deleteMatchResult(result.id)
    // 从列表中移除
    matchResults.value = matchResults.value.filter(r => r.id !== result.id)
  } catch (e) {
    showAlert('删除失败: ' + e.message, 'error')
  }
}

// 全部删除匹配结果
async function deleteAllResults() {
  if (matchResults.value.length === 0) {
    showAlert('没有可删除的匹配结果', 'warning')
    return
  }
  const confirmed = await showConfirm(`确定要删除全部 ${matchResults.value.length} 条匹配结果吗？此操作不可恢复，删除后需要重新执行匹配。`, '全部删除确认', 'warning')
  if (!confirmed) return
  try {
    // 获取所有ID，批量删除
    const allIds = matchResults.value.map(r => r.id).join(',')
    await resumeApi.batchDeleteMatchResults({ ids: allIds })
    matchResults.value = []
    showAlert('全部删除成功！', 'success')
  } catch (e) {
    showAlert('删除失败: ' + e.message, 'error')
  }
}

// 导出匹配结果Excel
async function exportExcel() {
  if (filteredResults.value.length === 0) {
    showAlert('当前没有可导出的匹配结果', 'warning')
    return
  }
  exporting.value = true
  try {
    const params = {
      view_mode: viewMode.value,
      company: filterCompany.value,
      position: filterPosition.value.join(','),
      owner: filterOwner.value.join(','),
      passed: filterPassed.value,
      min_score: filterMinScore.value || 0,
      name: filterName.value.trim()
    }
    const result = await resumeApi.exportMatchResults(params)
    if (result.success) {
      // 导出成功，不需要额外提示，浏览器会自动下载
    }
  } catch (e) {
    showAlert('导出失败: ' + (e.message || e), 'error')
  } finally {
    exporting.value = false
  }
}

// 清除本次匹配筛选，显示全部匹配结果
function clearResumeFilter() {
  filterResumeIds.value = null
  clearMatchViewParams()
}

onMounted(() => {
  // 读取从简历筛选中心跳转过来时传递的参数
  const params = getMatchViewParams()
  if (params && params.resume_ids && params.resume_ids.length > 0) {
    filterResumeIds.value = params.resume_ids
  }
  loadData()
})
</script>

<template>
  <div class="match-result-page" @click="showPositionDropdown = false; showOwnerDropdown = false">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2 class="page-title">查看匹配结果</h2>
      <p class="page-desc">AI语义匹配结果，按匹配度降序排列，支持多维度筛选</p>
    </div>

    <!-- 本次匹配筛选提示 -->
    <div v-if="filterResumeIds && filterResumeIds.length > 0" class="resume-filter-tip">
      <span class="filter-tip-icon">🎯</span>
      <span class="filter-tip-text">当前仅显示本次匹配的 <b>{{ filterResumeIds.length }}</b> 位候选人数据</span>
      <button class="filter-clear-btn" @click="clearResumeFilter">查看全部匹配结果</button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon blue">📊</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">匹配记录总数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon green">✅</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.passed }}</div>
          <div class="stat-label">满足硬性条件</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon orange">⭐</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.avgScore }}</div>
          <div class="stat-label">平均匹配分</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon red">🏆</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.highMatch }}</div>
          <div class="stat-label">80分以上高度匹配</div>
        </div>
      </div>
    </div>

    <!-- 上传统计概览 -->
    <div class="upload-stats-bar">
      <div class="upload-stat-card upload-stat-today">
        <div class="upload-stat-label">📅 今天</div>
        <div class="upload-stat-values">
          <span class="upload-stat-num">{{ uploadStats.today.uploaded }}</span>
          <span class="upload-stat-unit">份上传</span>
          <span class="upload-stat-divider">·</span>
          <span class="upload-stat-num">{{ uploadStats.today.matched }}</span>
          <span class="upload-stat-unit">条匹配</span>
        </div>
      </div>
      <div class="upload-stat-card upload-stat-yesterday">
        <div class="upload-stat-label">📆 昨天</div>
        <div class="upload-stat-values">
          <span class="upload-stat-num">{{ uploadStats.yesterday.uploaded }}</span>
          <span class="upload-stat-unit">份上传</span>
          <span class="upload-stat-divider">·</span>
          <span class="upload-stat-num">{{ uploadStats.yesterday.matched }}</span>
          <span class="upload-stat-unit">条匹配</span>
        </div>
      </div>
      <div class="upload-stat-card upload-stat-week">
        <div class="upload-stat-label">📊 本周</div>
        <div class="upload-stat-values">
          <span class="upload-stat-num">{{ uploadStats.thisWeek.uploaded }}</span>
          <span class="upload-stat-unit">份上传</span>
          <span class="upload-stat-divider">·</span>
          <span class="upload-stat-num">{{ uploadStats.thisWeek.matched }}</span>
          <span class="upload-stat-unit">条匹配</span>
        </div>
      </div>
      <div class="upload-stat-card upload-stat-total">
        <div class="upload-stat-label">📈 累计</div>
        <div class="upload-stat-values">
          <span class="upload-stat-num">{{ uploadStats.total.uploaded }}</span>
          <span class="upload-stat-unit">份上传</span>
          <span class="upload-stat-divider">·</span>
          <span class="upload-stat-num">{{ uploadStats.total.matched }}</span>
          <span class="upload-stat-unit">条匹配</span>
        </div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="filter-item">
        <label>公司</label>
        <select v-model="filterCompany" class="filter-select" @change="onCompanyChange">
          <option value="">全部公司</option>
          <option v-for="c in companies" :key="c.id" :value="c.name">{{ c.name }}</option>
        </select>
      </div>
      <div class="filter-item position-filter-wrap">
        <label>岗位</label>
        <div class="multi-select" @click.stop>
          <div class="multi-select-trigger" :class="{ active: showPositionDropdown }" @click="showPositionDropdown = !showPositionDropdown">
            <span :class="{ placeholder: filterPosition.length === 0 }">{{ positionFilterText }}</span>
            <span class="multi-select-arrow">▾</span>
          </div>
          <div v-if="showPositionDropdown" class="multi-select-dropdown">
            <div class="multi-select-actions">
              <span class="multi-select-count">共 {{ filteredPositions.length }} 个岗位</span>
              <button class="multi-select-clear" @click="filterPosition = []">清空</button>
            </div>
            <div class="multi-select-list">
              <label v-for="p in filteredPositions" :key="p.id" class="multi-select-option" :class="{ selected: filterPosition.includes(p.name) }">
                <input type="checkbox" :checked="filterPosition.includes(p.name)" @change="togglePosition(p.name)" />
                <span>{{ p.name }}</span>
              </label>
              <div v-if="filteredPositions.length === 0" class="multi-select-empty">
                {{ filterCompany ? '该公司暂无岗位' : '请先选择公司' }}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="filter-item owner-filter-wrap">
        <label>上传人</label>
        <div class="multi-select" @click.stop>
          <div class="multi-select-trigger" :class="{ active: showOwnerDropdown }" @click="showOwnerDropdown = !showOwnerDropdown">
            <span :class="{ placeholder: filterOwner.length === 0 }">{{ ownerFilterText }}</span>
            <span class="multi-select-arrow">▾</span>
          </div>
          <div v-if="showOwnerDropdown" class="multi-select-dropdown">
            <div class="multi-select-actions">
              <span class="multi-select-count">共 {{ ownerOptions.length }} 人</span>
              <button class="multi-select-clear" @click="filterOwner = []">清空</button>
            </div>
            <div class="multi-select-list">
              <label v-for="owner in ownerOptions" :key="owner" class="multi-select-option" :class="{ selected: filterOwner.includes(owner) }">
                <input type="checkbox" :checked="filterOwner.includes(owner)" @change="toggleOwner(owner)" />
                <span>{{ owner }}</span>
              </label>
              <div v-if="ownerOptions.length === 0" class="multi-select-empty">暂无招聘人员数据</div>
            </div>
          </div>
        </div>
      </div>
      <div class="filter-item">
        <label>硬性条件</label>
        <select v-model="filterPassed" class="filter-select">
          <option value="">全部</option>
          <option value="true">满足硬性条件</option>
          <option value="false">未满足硬性条件</option>
        </select>
      </div>
      <div class="filter-item">
        <label>最低分</label>
        <select v-model="filterMinScore" class="filter-select">
          <option value="">不限</option>
          <option value="80">80分以上</option>
          <option value="70">70分以上</option>
          <option value="60">60分以上</option>
        </select>
      </div>
      <div class="filter-item filter-name-item">
        <label>候选人</label>
        <input type="text" v-model="filterName" class="filter-input" placeholder="输入姓名搜索" />
      </div>
      <button class="btn-reset-filter" @click="resetFilters">重置</button>
    </div>

    <!-- 匹配结果列表 -->
    <div class="result-card">
      <div class="result-header">
        <div class="result-header-line">
          <span class="result-title">匹配结果列表</span>
          <span class="result-count">共 {{ filteredResults.length }} 条记录</span>
        </div>
        <div class="result-header-line">
          <div class="display-mode-switch">
            <button :class="['mode-btn', { active: displayMode === 'view' }]" @click="displayMode = 'view'" title="卡片式分组展示">🎨 视图模式</button>
            <button :class="['mode-btn', { active: displayMode === 'simple' }]" @click="displayMode = 'simple'" title="表格方式呈现，类似Excel">📊 简洁模式</button>
          </div>
          <div class="action-btn-group" style="margin-left: auto;">
            <button class="btn-refresh-sm" @click="loadData" :disabled="loading">{{ loading ? '加载中...' : '🔄 刷新' }}</button>
            <button class="btn-export-sm" @click="exportExcel" :disabled="exporting || matchResults.length === 0">{{ exporting ? '导出中...' : '📥 下载Excel' }}</button>
            <button class="btn-match-all-sm" @click="matchAllResumes" :disabled="matching">{{ matching ? '匹配中...' : '⚡ 执行全域匹配' }}</button>
            <button class="btn-delete-all-sm" @click="deleteAllResults" :disabled="loading || matchResults.length === 0">🗑 全部删除</button>
          </div>
        </div>
        <div class="result-header-line">
          <div class="view-toggle">
            <button :class="['view-toggle-btn', { active: viewMode === 'list' }]" @click="viewMode = 'list'">📋 列表视图</button>
            <button :class="['view-toggle-btn', { active: viewMode === 'grouped' }]" @click="viewMode = 'grouped'">🏢 按公司分组</button>
            <button :class="['view-toggle-btn', { active: viewMode === 'groupedByOwner' }]" @click="viewMode = 'groupedByOwner'">👤 按招聘人员分组</button>
            <button :class="['view-toggle-btn', { active: viewMode === 'groupedByDate' }]" @click="viewMode = 'groupedByDate'">📅 按上传时间分组</button>
          </div>
          <template v-if="viewMode !== 'list'" class="expand-collapse-group">
            <button class="header-action-btn" @click="expandAllGroups">全部展开</button>
            <button class="header-action-btn" @click="collapseAllGroups">全部折叠</button>
          </template>
        </div>
      </div>

      <!-- 批量操作栏 -->
      <div v-if="selectedCount > 0" class="batch-action-bar">
        <span class="batch-selected-info">已选中 <strong>{{ selectedCount }}</strong> 条</span>
        <div class="batch-actions">
          <button class="batch-btn batch-send" @click="batchSendToCompany" :disabled="sending">
            {{ sending ? '发送中...' : '📧 批量发送到公司' }}
          </button>
          <button class="batch-btn batch-cancel" @click="clearSelection">取消选择</button>
        </div>
        <span v-if="sendMessage" class="batch-message">{{ sendMessage }}</span>
      </div>

      <div v-if="loading" class="loading-state">
        <div class="loading-spinner"></div>
        <span>加载中...</span>
      </div>

      <!-- 简洁模式：TABLE方式呈现，类似Excel -->
      <div v-if="!loading && filteredResults.length > 0 && displayMode === 'simple'" class="simple-mode-wrap">
        <table class="simple-table">
          <thead v-if="viewMode === 'list'">
            <tr class="simple-table-header">
              <th style="width:40px"><input type="checkbox" :checked="isSimpleAllSelected" @change="toggleSimpleSelectAll()" /></th>
              <th style="width:50px">序号</th>
              <th>候选人 / 层级</th>
              <th>目标岗位</th>
              <th>公司</th>
              <th style="width:80px">总分</th>
              <th style="width:110px">硬性条件</th>
              <th style="width:80px">匹配方式</th>
              <th style="width:100px">面试状态</th>
              <th style="width:120px">操作</th>
            </tr>
          </thead>
          <tbody>
            <!-- 列表视图 -->
            <template v-if="viewMode === 'list'">
              <tr v-for="(r, idx) in simpleListResults" :key="'l_'+r.id" class="simple-data-row" :class="{ selected: selectedResultIds.includes(r.id) }">
                <td><input type="checkbox" :checked="selectedResultIds.includes(r.id)" @change="toggleSelect(r.id)" /></td>
                <td>{{ idx + 1 }}</td>
                <td class="candidate-cell">{{ r.candidate_name || r.resume_name }}</td>
                <td>{{ r.position_name }}</td>
                <td>{{ r.company_name }}</td>
                <td><span class="score-badge" :class="scoreClass(r.total_score)">{{ r.total_score }}</span></td>
                <td><span class="hard-tag" :class="r.passed_hard ? 'hard-pass' : 'hard-fail'">{{ r.passed_hard ? '满足硬性条件' : '不满足硬性条件' }}</span></td>
                <td><span class="method-tag" :class="r.match_method === 'ai' ? 'method-ai' : 'method-rule'">{{ r.match_method === 'ai' ? 'AI匹配' : '规则降级' }}</span></td>
                <td>{{ getInterviewStatusSimple(r) }}</td>
                <td class="action-cell">
                  <button class="simple-action-btn" @click="openDetail(r)">详情</button>
                  <button class="simple-action-btn send-btn" @click="sendToCompany(r)">{{ r.sent_to_company ? '再次发送' : '发送' }}</button>
                  <button class="simple-action-btn danger" @click="deleteResult(r)">删除</button>
                </td>
              </tr>
              <tr v-if="simpleVisibleCount < filteredResults.length" class="simple-load-more-row">
                <td colspan="10" style="text-align:center;padding:12px">
                  <button class="simple-load-more-btn" @click="loadMoreSimpleList">加载更多（还有 {{ filteredResults.length - simpleVisibleCount }} 条）</button>
                </td>
              </tr>
            </template>
            <!-- 按公司分组 -->
            <template v-else-if="viewMode === 'grouped'">
              <template v-for="company in groupedResults" :key="'sc_'+company.name">
                <tr class="simple-group-row level-1-row">
                  <td colspan="10"><span class="group-level-badge level-1">L1</span> 🏢 {{ company.name }} <span class="group-stat">（{{ simpleCompanyTotal(company) }}条，{{ simpleCompanyPassed(company) }}满足硬性）</span></td>
                </tr>
                <template v-for="position in company.positions" :key="'sp_'+company.name+'_'+position.name">
                  <tr class="simple-group-row level-2-row">
                    <td colspan="10" style="padding-left:32px"><span class="group-level-badge level-2">L2</span> 💼 {{ position.name }} <span class="group-stat">（{{ simplePositionTotal(position) }}条）</span></td>
                  </tr>
                  <template v-for="owner in position.owners" :key="'so_'+company.name+'_'+position.name+'_'+owner.owner_name">
                    <tr class="simple-group-row level-3-row">
                      <td colspan="10" style="padding-left:56px"><span class="group-level-badge level-3">L3</span> 👤 {{ owner.owner_name }} <span class="group-stat">（{{ owner.results.length }}条）</span></td>
                    </tr>
                    <tr class="simple-sub-header-row">
                      <th style="width:40px"><input type="checkbox" :checked="isGroupAllSelected(owner.results)" @change="toggleGroupSelectAllSimple(owner.results)" /></th>
                      <th style="width:50px">序号</th>
                      <th>候选人</th>
                      <th>目标岗位</th>
                      <th>公司</th>
                      <th style="width:80px">总分</th>
                      <th style="width:110px">硬性条件</th>
                      <th style="width:80px">匹配方式</th>
                      <th style="width:100px">面试状态</th>
                      <th style="width:120px">操作</th>
                    </tr>
                    <tr v-for="(r, ridx) in getGroupVisibleResults(owner.results, 'owner_' + company.name + '_' + position.name + '_' + owner.owner_name)" :key="'c_'+r.id" class="simple-data-row" :class="{ selected: selectedResultIds.includes(r.id) }">
                      <td><input type="checkbox" :checked="selectedResultIds.includes(r.id)" @change="toggleSelect(r.id)" /></td>
                      <td>{{ ridx + 1 }}</td>
                      <td class="candidate-cell" style="padding-left:72px">{{ r.candidate_name || r.resume_name }}</td>
                      <td>{{ r.position_name }}</td>
                      <td>{{ r.company_name }}</td>
                      <td><span class="score-badge" :class="scoreClass(r.total_score)">{{ r.total_score }}</span></td>
                      <td><span class="hard-tag" :class="r.passed_hard ? 'hard-pass' : 'hard-fail'">{{ r.passed_hard ? '满足硬性条件' : '不满足硬性条件' }}</span></td>
                      <td><span class="method-tag" :class="r.match_method === 'ai' ? 'method-ai' : 'method-rule'">{{ r.match_method === 'ai' ? 'AI匹配' : '规则降级' }}</span></td>
                      <td>{{ getInterviewStatusSimple(r) }}</td>
                      <td class="action-cell">
                        <button class="simple-action-btn" @click="openDetail(r)">详情</button>
                        <button class="simple-action-btn send-btn" @click="sendToCompany(r)">{{ r.sent_to_company ? '再次发送' : '发送' }}</button>
                        <button class="simple-action-btn danger" @click="deleteResult(r)">删除</button>
                      </td>
                    </tr>
                    <tr v-if="!isGroupLoadMore('owner_' + company.name + '_' + position.name + '_' + owner.owner_name) && owner.results.length > GROUP_PAGE_SIZE" class="simple-load-more-row">
                      <td colspan="10" style="text-align:center;padding:8px;padding-left:72px">
                        <button class="simple-load-more-btn" @click="toggleLoadMore('owner_' + company.name + '_' + position.name + '_' + owner.owner_name)">加载更多（还有 {{ owner.results.length - GROUP_PAGE_SIZE }} 条）</button>
                      </td>
                    </tr>
                  </template>
                </template>
              </template>
            </template>
            <!-- 按招聘人员分组 -->
            <template v-else-if="viewMode === 'groupedByOwner'">
              <template v-for="owner in groupedByOwnerResults" :key="'so_'+owner.name">
                <tr class="simple-group-row level-1-row">
                  <td colspan="10"><span class="group-level-badge level-1">L1</span> 👤 {{ owner.name }} <span class="group-stat">（{{ simpleOwnerGroupTotal(owner) }}条，均分{{ simpleOwnerGroupAvg(owner) }}）</span></td>
                </tr>
                <template v-for="company in owner.companies" :key="'sc_'+owner.name+'_'+company.name">
                  <tr class="simple-group-row level-2-row">
                    <td colspan="10" style="padding-left:32px"><span class="group-level-badge level-2">L2</span> 🏢 {{ company.name }} <span class="group-stat">（{{ simpleCompanyGroupTotal(company) }}条）</span></td>
                  </tr>
                  <template v-for="position in company.positions" :key="'sp_'+owner.name+'_'+company.name+'_'+position.position_name">
                    <tr class="simple-group-row level-3-row">
                      <td colspan="10" style="padding-left:56px"><span class="group-level-badge level-3">L3</span> 💼 {{ position.position_name }} <span class="group-stat">（{{ position.results.length }}条）</span></td>
                    </tr>
                    <tr class="simple-sub-header-row">
                      <th style="width:40px"><input type="checkbox" :checked="isGroupAllSelected(position.results)" @change="toggleGroupSelectAllSimple(position.results)" /></th>
                      <th style="width:50px">序号</th>
                      <th>候选人</th>
                      <th>目标岗位</th>
                      <th>公司</th>
                      <th style="width:80px">总分</th>
                      <th style="width:110px">硬性条件</th>
                      <th style="width:80px">匹配方式</th>
                      <th style="width:100px">面试状态</th>
                      <th style="width:120px">操作</th>
                    </tr>
                    <tr v-for="(r, ridx) in getGroupVisibleResults(position.results, 'ownerPos_' + owner.name + '_' + company.name + '_' + position.position_name)" :key="'o_'+r.id" class="simple-data-row" :class="{ selected: selectedResultIds.includes(r.id) }">
                      <td><input type="checkbox" :checked="selectedResultIds.includes(r.id)" @change="toggleSelect(r.id)" /></td>
                      <td>{{ ridx + 1 }}</td>
                      <td class="candidate-cell" style="padding-left:72px">{{ r.candidate_name || r.resume_name }}</td>
                      <td>{{ r.position_name }}</td>
                      <td>{{ r.company_name }}</td>
                      <td><span class="score-badge" :class="scoreClass(r.total_score)">{{ r.total_score }}</span></td>
                      <td><span class="hard-tag" :class="r.passed_hard ? 'hard-pass' : 'hard-fail'">{{ r.passed_hard ? '满足硬性条件' : '不满足硬性条件' }}</span></td>
                      <td><span class="method-tag" :class="r.match_method === 'ai' ? 'method-ai' : 'method-rule'">{{ r.match_method === 'ai' ? 'AI匹配' : '规则降级' }}</span></td>
                      <td>{{ getInterviewStatusSimple(r) }}</td>
                      <td class="action-cell">
                        <button class="simple-action-btn" @click="openDetail(r)">详情</button>
                        <button class="simple-action-btn send-btn" @click="sendToCompany(r)">{{ r.sent_to_company ? '再次发送' : '发送' }}</button>
                        <button class="simple-action-btn danger" @click="deleteResult(r)">删除</button>
                      </td>
                    </tr>
                    <tr v-if="!isGroupLoadMore('ownerPos_' + owner.name + '_' + company.name + '_' + position.position_name) && position.results.length > GROUP_PAGE_SIZE" class="simple-load-more-row">
                      <td colspan="10" style="text-align:center;padding:8px;padding-left:72px">
                        <button class="simple-load-more-btn" @click="toggleLoadMore('ownerPos_' + owner.name + '_' + company.name + '_' + position.position_name)">加载更多（还有 {{ position.results.length - GROUP_PAGE_SIZE }} 条）</button>
                      </td>
                    </tr>
                  </template>
                </template>
              </template>
            </template>
            <!-- 按上传时间分组 -->
            <template v-else-if="viewMode === 'groupedByDate'">
              <template v-for="day in groupedByDate" :key="'sd_'+day.date">
                <tr class="simple-group-row level-1-row">
                  <td colspan="10"><span class="group-level-badge level-1">L1</span> 📅 {{ formatDateLabel(day.date) }} <span class="group-stat">（{{ day.results.length }}条，{{ day.passed_count }}满足硬性）</span></td>
                </tr>
                <tr class="simple-sub-header-row">
                  <th style="width:40px"><input type="checkbox" :checked="isGroupAllSelected(day.results)" @change="toggleGroupSelectAllSimple(day.results)" /></th>
                  <th style="width:50px">序号</th>
                  <th>候选人</th>
                  <th>目标岗位</th>
                  <th>公司</th>
                  <th style="width:80px">总分</th>
                  <th style="width:110px">硬性条件</th>
                  <th style="width:80px">匹配方式</th>
                  <th style="width:100px">面试状态</th>
                  <th style="width:120px">操作</th>
                </tr>
                <tr v-for="(r, ridx) in getGroupVisibleResults(day.results, 'date_' + day.date)" :key="'d_'+r.id" class="simple-data-row" :class="{ selected: selectedResultIds.includes(r.id) }">
                  <td><input type="checkbox" :checked="selectedResultIds.includes(r.id)" @change="toggleSelect(r.id)" /></td>
                  <td>{{ ridx + 1 }}</td>
                  <td class="candidate-cell" style="padding-left:24px">{{ r.candidate_name || r.resume_name }}</td>
                  <td>{{ r.position_name }}</td>
                  <td>{{ r.company_name }}</td>
                  <td><span class="score-badge" :class="scoreClass(r.total_score)">{{ r.total_score }}</span></td>
                  <td><span class="hard-tag" :class="r.passed_hard ? 'hard-pass' : 'hard-fail'">{{ r.passed_hard ? '满足硬性条件' : '不满足硬性条件' }}</span></td>
                  <td><span class="method-tag" :class="r.match_method === 'ai' ? 'method-ai' : 'method-rule'">{{ r.match_method === 'ai' ? 'AI匹配' : '规则降级' }}</span></td>
                  <td>{{ getInterviewStatusSimple(r) }}</td>
                  <td class="action-cell">
                    <button class="simple-action-btn" @click="openDetail(r)">详情</button>
                    <button class="simple-action-btn send-btn" @click="sendToCompany(r)">{{ r.sent_to_company ? '再次发送' : '发送' }}</button>
                    <button class="simple-action-btn danger" @click="deleteResult(r)">删除</button>
                  </td>
                </tr>
                <tr v-if="!isGroupLoadMore('date_' + day.date) && day.results.length > GROUP_PAGE_SIZE" class="simple-load-more-row">
                  <td colspan="10" style="text-align:center;padding:8px;padding-left:24px">
                    <button class="simple-load-more-btn" @click="toggleLoadMore('date_' + day.date)">加载更多（还有 {{ day.results.length - GROUP_PAGE_SIZE }} 条）</button>
                  </td>
                </tr>
              </template>
            </template>
          </tbody>
        </table>
      </div>

<div v-if="!loading && filteredResults.length === 0" class="empty-state">
        <div class="empty-icon">📭</div>
        <div class="empty-text">暂无匹配结果</div>
        <div class="empty-hint">请先上传简历并执行全域匹配</div>
        <button class="btn-match-all" @click="matchAllResumes">立即匹配</button>
      </div>

      <div v-if="!loading && filteredResults.length > 0 && viewMode === 'list' && displayMode === 'view'" class="result-table-wrap">
        <table class="result-table">
          <thead>
            <tr>
              <th style="width:40px">
                <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" />
              </th>
              <th style="width:50px">序号</th>
              <th>候选人</th>
              <th>目标岗位</th>
              <th>公司</th>
              <th style="width:90px">总分</th>
              <th style="width:110px">硬性条件</th>
              <th style="width:80px">匹配方式</th>
              <th style="width:110px">面试状态</th>
              <th style="width:100px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(result, idx) in pagedResults" :key="result.id" class="result-row" :class="{ 'row-selected': selectedResultIds.includes(result.id) }">
              <td class="cell-checkbox">
                <input type="checkbox" :checked="selectedResultIds.includes(result.id)" @change="toggleSelect(result.id)" />
              </td>
              <td class="cell-index">{{ (currentPage - 1) * pageSize + idx + 1 }}</td>
              <td class="cell-candidate">
                <div class="candidate-name">{{ result.resume_name || '未知' }}</div>
              </td>
              <td class="cell-position">{{ result.position_name }}</td>
              <td class="cell-company">{{ result.company_name }}</td>
              <td class="cell-score">
                <span class="score-badge" :class="scoreLevel(result.total_score)">
                  {{ result.total_score }}
                </span>
              </td>
              <td class="cell-passed">
                <span v-if="result.passed_hard" class="tag-passed">满足硬性条件</span>
                <span v-else class="tag-rejected">不满足硬性条件</span>
              </td>
              <td class="cell-method">
                <span v-if="result.match_method === 'ai'" class="method-tag method-ai">AI匹配</span>
                <span v-else class="method-tag method-rule">规则降级</span>
              </td>
              <td class="cell-interview-status">
                <span v-if="result.interview_result === '通过'" class="interview-tag interview-pass">面试通过</span>
                <span v-else-if="result.interview_result === '不通过'" class="interview-tag interview-fail">面试不通过</span>
                <span v-else-if="result.interview_scheduled" class="interview-tag interview-scheduled">已安排面试</span>
                <span v-else class="interview-tag interview-none">未安排</span>
              </td>
              <td class="cell-action">
                <div class="action-btns">
                  <button class="btn-detail" @click="openDetail(result)">详情</button>
                  <button class="btn-rematch" @click="rematchPosition(result)" :disabled="rematchingId === result.id" :title="'重新匹配该岗位'">
                    {{ rematchingId === result.id ? '匹配中...' : '重新匹配' }}
                  </button>
                  <button class="btn-send" @click="sendToCompany(result)" :title="result.sent_to_company ? '再次发送到公司邮箱' : '发送到公司邮箱'">{{ result.sent_to_company ? '再次发送' : '发送' }}</button>
                  <span v-if="result.sent_to_company" class="sent-badge" title="已发送">✓已发</span>
                  <button class="btn-delete" @click="deleteResult(result)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 分页 -->
        <div class="pagination" v-if="filteredResults.length > pageSize">
          <button class="page-btn" :disabled="currentPage === 1" @click="goPage(currentPage - 1)">上一页</button>
          <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页（共 {{ filteredResults.length }} 条）</span>
          <button class="page-btn" :disabled="currentPage === totalPages" @click="goPage(currentPage + 1)">下一页</button>
        </div>
      </div>

      <!-- 分组视图 -->
      <div v-if="!loading && filteredResults.length > 0 && viewMode === 'grouped' && displayMode === 'view'" class="grouped-view">
        <div v-for="company in groupedResults" :key="company.name" class="group-company">
          <div class="group-header company-header" @click="toggleGroup('company_' + company.name)">
            <span class="group-toggle">{{ company.expanded ? '▼' : '▶' }}</span>
            <span class="group-level-badge level-1">L1 公司</span>
            <span class="group-icon">🏢</span>
            <span class="group-title">{{ company.name }}</span>
            <span class="group-stats">
              {{ company.positions.length }} 个岗位 · 
              {{ company.positions.reduce((s, p) => s + p.owners.reduce((s2, o) => s2 + o.total_count, 0), 0) }} 条匹配
            </span>
          </div>
          <div v-if="company.expanded" class="group-children">
            <div v-for="position in company.positions" :key="position.name" class="group-position">
              <div class="group-header position-header" @click="toggleGroup('pos_' + company.name + '_' + position.name)">
                <span class="group-toggle">{{ position.expanded ? '▼' : '▶' }}</span>
                <span class="group-level-badge level-2">L2 岗位</span>
                <span class="group-icon">💼</span>
                <span class="group-title">{{ position.name }}</span>
                <span class="group-stats">
                  {{ position.owners.length }} 个招聘人员 · 
                  {{ position.owners.reduce((s, o) => s + o.total_count, 0) }} 条匹配
                </span>
              </div>
              <div v-if="position.expanded" class="group-children">
                <div v-for="owner in position.owners" :key="owner.owner_name" class="group-owner">
                  <div class="owner-header">
                    <span class="group-level-badge level-3">L3 招聘人</span>
                    <span class="group-icon">👤</span>
                    <span class="owner-name">{{ owner.owner_name }}</span>
                    <span class="owner-stats">
                      <span class="stat-badge stat-total">{{ owner.total_count }} 条</span>
                      <span class="stat-badge stat-passed">{{ owner.passed_count }} 满足硬性</span>
                      <span class="stat-badge stat-avg">均分 {{ owner.avg_score }}</span>
                    </span>
                  </div>
                  <div class="owner-results">
                    <table class="result-table group-result-table">
                      <thead>
                        <tr>
                          <th style="width:40px"><input type="checkbox" :checked="isAllGroupSelected(owner.results)" @change="toggleGroupSelectAll(owner.results)" /></th>
                          <th style="width:50px">序号</th>
                          <th>候选人</th>
                          <th style="width:90px">总分</th>
                          <th style="width:110px">硬性条件</th>
                          <th style="width:80px">匹配方式</th>
                          <th style="width:110px">面试状态</th>
                          <th style="width:100px">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(result, idx) in getGroupVisibleResults(owner.results, 'co_' + company.name + '_' + position.name + '_' + owner.owner_name)" :key="result.id" class="result-row" :class="{ 'row-selected': selectedResultIds.includes(result.id) }">
                          <td class="cell-checkbox"><input type="checkbox" :checked="selectedResultIds.includes(result.id)" @change="toggleSelect(result.id)" /></td>
                          <td class="cell-index">{{ idx + 1 }}</td>
                          <td class="cell-candidate"><div class="candidate-name">{{ result.resume_name || '未知' }}</div></td>
                          <td class="cell-score"><span class="score-badge" :class="scoreLevel(result.total_score)">{{ result.total_score }}</span></td>
                          <td class="cell-passed"><span v-if="result.passed_hard" class="tag-passed">满足硬性条件</span><span v-else class="tag-rejected">不满足硬性条件</span></td>
                          <td class="cell-method"><span v-if="result.match_method === 'ai'" class="method-tag method-ai">AI匹配</span><span v-else class="method-tag method-rule">规则降级</span></td>
                          <td class="cell-interview-status">
                            <span v-if="result.interview_result === '通过'" class="interview-tag interview-pass">面试通过</span>
                            <span v-else-if="result.interview_result === '不通过'" class="interview-tag interview-fail">面试不通过</span>
                            <span v-else-if="result.interview_scheduled" class="interview-tag interview-scheduled">已安排面试</span>
                            <span v-else class="interview-tag interview-none">未安排</span>
                          </td>
                          <td class="cell-action">
                            <div class="action-btns">
                              <button class="btn-detail" @click="openDetail(result)">详情</button>
                              <button class="btn-send" @click="sendToCompany(result)" :title="result.sent_to_company ? '再次发送到公司邮箱' : '发送到公司邮箱'">{{ result.sent_to_company ? '再次发送' : '发送' }}</button>
                              <button class="btn-delete" @click="deleteResult(result)">删除</button>
                            </div>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-if="owner.results.length > GROUP_PAGE_SIZE" class="load-more-wrap">
                    <button class="load-more-btn" @click="toggleLoadMore('co_' + company.name + '_' + position.name + '_' + owner.owner_name)">
                      {{ isGroupLoadMore('co_' + company.name + '_' + position.name + '_' + owner.owner_name) ? '收起' : `还有 ${owner.results.length - GROUP_PAGE_SIZE} 条，点击加载更多` }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 按招聘人员分组视图 -->
      <div v-if="!loading && filteredResults.length > 0 && viewMode === 'groupedByOwner' && displayMode === 'view'" class="grouped-view">
        <div v-for="owner in groupedByOwnerResults" :key="owner.name" class="group-company">
          <div class="group-header owner-group-header" @click="toggleGroup('owner_' + owner.name)">
            <span class="group-toggle">{{ owner.expanded ? '▼' : '▶' }}</span>
            <span class="group-level-badge level-1">L1 招聘人</span>
            <span class="group-icon">👤</span>
            <span class="group-title">{{ owner.name }}</span>
            <span class="group-stats">
              {{ owner.companies.length }} 家公司 · 
              {{ owner.companies.reduce((s, c) => s + c.positions.reduce((s2, p) => s2 + p.total_count, 0), 0) }} 条匹配 ·
              均分 {{ owner.companies.length > 0 ? Math.round(owner.companies.reduce((s, c) => s + c.positions.reduce((s2, p) => s2 + p.avg_score * p.total_count, 0), 0) / owner.companies.reduce((s, c) => s + c.positions.reduce((s2, p) => s2 + p.total_count, 0), 0)) : 0 }}
            </span>
          </div>
          <div v-if="owner.expanded" class="group-children">
            <div v-for="company in owner.companies" :key="company.name" class="group-position">
              <div class="group-header company-header" @click="toggleGroup('ownerCompany_' + owner.name + '_' + company.name)">
                <span class="group-toggle">{{ company.expanded ? '▼' : '▶' }}</span>
                <span class="group-level-badge level-2">L2 公司</span>
                <span class="group-icon">🏢</span>
                <span class="group-title">{{ company.name }}</span>
                <span class="group-stats">
                  {{ company.positions.length }} 个岗位 · 
                  {{ company.positions.reduce((s, p) => s + p.total_count, 0) }} 条匹配
                </span>
              </div>
              <div v-if="company.expanded" class="group-children">
                <div v-for="position in company.positions" :key="position.position_name" class="group-owner">
                  <div class="owner-header">
                    <span class="group-level-badge level-3">L3 岗位</span>
                    <span class="group-icon">💼</span>
                    <span class="owner-name">{{ position.position_name }}</span>
                    <span class="owner-stats">
                      <span class="stat-badge stat-total">{{ position.total_count }} 条</span>
                      <span class="stat-badge stat-passed">{{ position.passed_count }} 满足硬性</span>
                      <span class="stat-badge stat-avg">均分 {{ position.avg_score }}</span>
                    </span>
                  </div>
                  <div class="owner-results">
                    <table class="result-table group-result-table">
                      <thead>
                        <tr>
                          <th style="width:40px"><input type="checkbox" :checked="isAllGroupSelected(position.results)" @change="toggleGroupSelectAll(position.results)" /></th>
                          <th style="width:50px">序号</th>
                          <th>候选人</th>
                          <th style="width:90px">总分</th>
                          <th style="width:110px">硬性条件</th>
                          <th style="width:80px">匹配方式</th>
                          <th style="width:110px">面试状态</th>
                          <th style="width:100px">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(result, idx) in getGroupVisibleResults(position.results, 'oc_' + owner.name + '_' + company.name + '_' + position.position_name)" :key="result.id" class="result-row" :class="{ 'row-selected': selectedResultIds.includes(result.id) }">
                          <td class="cell-checkbox"><input type="checkbox" :checked="selectedResultIds.includes(result.id)" @change="toggleSelect(result.id)" /></td>
                          <td class="cell-index">{{ idx + 1 }}</td>
                          <td class="cell-candidate"><div class="candidate-name">{{ result.resume_name || '未知' }}</div></td>
                          <td class="cell-score"><span class="score-badge" :class="scoreLevel(result.total_score)">{{ result.total_score }}</span></td>
                          <td class="cell-passed"><span v-if="result.passed_hard" class="tag-passed">满足硬性条件</span><span v-else class="tag-rejected">不满足硬性条件</span></td>
                          <td class="cell-method"><span v-if="result.match_method === 'ai'" class="method-tag method-ai">AI匹配</span><span v-else class="method-tag method-rule">规则降级</span></td>
                          <td class="cell-interview-status">
                            <span v-if="result.interview_result === '通过'" class="interview-tag interview-pass">面试通过</span>
                            <span v-else-if="result.interview_result === '不通过'" class="interview-tag interview-fail">面试不通过</span>
                            <span v-else-if="result.interview_scheduled" class="interview-tag interview-scheduled">已安排面试</span>
                            <span v-else class="interview-tag interview-none">未安排</span>
                          </td>
                          <td class="cell-action">
                            <div class="action-btns">
                              <button class="btn-detail" @click="openDetail(result)">详情</button>
                              <button class="btn-send" @click="sendToCompany(result)" :title="result.sent_to_company ? '再次发送到公司邮箱' : '发送到公司邮箱'">{{ result.sent_to_company ? '再次发送' : '发送' }}</button>
                              <button class="btn-delete" @click="deleteResult(result)">删除</button>
                            </div>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-if="position.results.length > GROUP_PAGE_SIZE" class="load-more-wrap">
                    <button class="load-more-btn" @click="toggleLoadMore('oc_' + owner.name + '_' + company.name + '_' + position.position_name)">
                      {{ isGroupLoadMore('oc_' + owner.name + '_' + company.name + '_' + position.position_name) ? '收起' : `还有 ${position.results.length - GROUP_PAGE_SIZE} 条，点击加载更多` }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 按上传时间分组视图 -->
      <div v-if="!loading && filteredResults.length > 0 && viewMode === 'groupedByDate' && displayMode === 'view'" class="grouped-view">
        <div v-for="dayGroup in groupedByDate" :key="dayGroup.date" class="group-company">
          <div class="group-header date-group-header" @click="toggleGroup('date_' + dayGroup.date)">
            <span class="group-toggle">{{ dayGroup.expanded ? '▼' : '▶' }}</span>
            <span class="group-level-badge level-1">L1 日期</span>
            <span class="group-icon">📅</span>
            <span class="group-title">{{ formatDateLabel(dayGroup.date) }}</span>
            <span class="group-stats">
              {{ dayGroup.uploaded_count }} 份简历 · 
              {{ dayGroup.total_count }} 条匹配 ·
              {{ dayGroup.passed_count }} 满足硬性条件 ·
              均分 {{ dayGroup.avg_score }}
            </span>
          </div>
          <div v-if="dayGroup.expanded" class="group-children">
            <div class="date-results-grid">
              <table class="result-table group-result-table">
                <thead>
                  <tr>
                    <th style="width:40px"><input type="checkbox" :checked="isAllGroupSelected(dayGroup.results)" @change="toggleGroupSelectAll(dayGroup.results)" /></th>
                    <th style="width:50px">序号</th>
                    <th>候选人</th>
                    <th>目标岗位</th>
                    <th>公司</th>
                    <th style="width:90px">总分</th>
                    <th style="width:110px">硬性条件</th>
                    <th style="width:80px">匹配方式</th>
                    <th style="width:110px">面试状态</th>
                    <th style="width:100px">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(result, idx) in getGroupVisibleResults(dayGroup.results, 'date_' + dayGroup.date)" :key="result.id" class="result-row" :class="{ 'row-selected': selectedResultIds.includes(result.id) }">
                    <td class="cell-checkbox"><input type="checkbox" :checked="selectedResultIds.includes(result.id)" @change="toggleSelect(result.id)" /></td>
                    <td class="cell-index">{{ idx + 1 }}</td>
                    <td class="cell-candidate"><div class="candidate-name">{{ result.resume_name || '未知' }}</div></td>
                    <td class="cell-position">{{ result.position_name }}</td>
                    <td class="cell-company">{{ result.company_name }}</td>
                    <td class="cell-score"><span class="score-badge" :class="scoreLevel(result.total_score)">{{ result.total_score }}</span></td>
                    <td class="cell-passed"><span v-if="result.passed_hard" class="tag-passed">满足硬性条件</span><span v-else class="tag-rejected">不满足硬性条件</span></td>
                    <td class="cell-method"><span v-if="result.match_method === 'ai'" class="method-tag method-ai">AI匹配</span><span v-else class="method-tag method-rule">规则降级</span></td>
                    <td class="cell-interview-status">
                      <span v-if="result.interview_result === '通过'" class="interview-tag interview-pass">面试通过</span>
                      <span v-else-if="result.interview_result === '不通过'" class="interview-tag interview-fail">面试不通过</span>
                      <span v-else-if="result.interview_scheduled" class="interview-tag interview-scheduled">已安排面试</span>
                      <span v-else class="interview-tag interview-none">未安排</span>
                    </td>
                    <td class="cell-action">
                      <div class="action-btns">
                        <button class="btn-detail" @click="openDetail(result)">详情</button>
                        <button class="btn-send" @click="sendToCompany(result)" :title="result.sent_to_company ? '再次发送到公司邮箱' : '发送到公司邮箱'">{{ result.sent_to_company ? '再次发送' : '发送' }}</button>
                        <button class="btn-delete" @click="deleteResult(result)">删除</button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="dayGroup.results.length > GROUP_PAGE_SIZE" class="load-more-wrap">
              <button class="load-more-btn" @click="toggleLoadMore('date_' + dayGroup.date)">
                {{ isGroupLoadMore('date_' + dayGroup.date) ? '收起' : `还有 ${dayGroup.results.length - GROUP_PAGE_SIZE} 条，点击加载更多` }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <div v-if="showDetail && currentDetail" class="detail-modal" @click.self="closeDetail">
      <div class="detail-content">
        <div class="detail-header">
          <div>
            <h3 class="detail-title">匹配详情</h3>
            <p class="detail-subtitle">
              {{ currentDetail.resume_name }} → {{ currentDetail.company_name }} · {{ currentDetail.position_name }}
            </p>
          </div>
          <button class="btn-close" @click="closeDetail">✕</button>
        </div>

        <!-- 标签页导航 -->
        <div class="detail-tabs">
          <div class="detail-tab" :class="{ active: detailTab === 'match' }" @click="detailTab = 'match'">匹配详情</div>
          <div class="detail-tab" :class="{ active: detailTab === 'review' }" @click="detailTab = 'review'">
            人工评价
            <span v-if="manualReview" class="tab-badge">已评</span>
          </div>
          <div class="detail-tab" :class="{ active: detailTab === 'interview' }" @click="detailTab = 'interview'">
            面试反馈
            <span v-if="interviewFeedback" class="tab-badge" :class="interviewFeedback.interview_result === '通过' ? 'badge-pass' : interviewFeedback.interview_result === '不通过' ? 'badge-fail' : 'badge-pending'">{{ interviewFeedback.interview_result }}</span>
          </div>
        </div>

        <div class="detail-body">
          <!-- ========== 匹配详情标签页 ========== -->
          <div v-show="detailTab === 'match'">
          <!-- 总分概览 -->
          <div class="detail-overview">
            <div class="overview-score">
              <div class="score-circle" :class="scoreLevel(currentDetail.total_score)">
                <span class="score-num">{{ currentDetail.total_score }}</span>
                <span class="score-label">{{ scoreText(currentDetail.total_score) }}</span>
              </div>
            </div>
            <div class="overview-info">
              <div class="info-row">
                <span class="info-label">硬性条件：</span>
                <span v-if="currentDetail.passed_hard" class="tag-passed">满足硬性条件</span>
                <span v-else class="tag-rejected">不满足硬性条件</span>
              </div>
              <div v-if="currentDetail.reject_reason" class="info-row">
                <span class="info-label">拒绝原因：</span>
                <span class="reject-reason">{{ currentDetail.reject_reason }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">匹配方式：</span>
                <span v-if="currentDetail.match_method === 'ai'" class="method-tag method-ai">AI语义匹配</span>
                <span v-else class="method-tag method-rule">规则引擎匹配</span>
              </div>
            </div>
          </div>

          <!-- 各维度得分 -->
          <div class="detail-section">
            <h4 class="section-title">各维度得分</h4>
            <div class="dimension-list">
              <div v-for="dim in dimensions" :key="dim.key" class="dimension-item">
                <span class="dim-label">{{ dim.label }}</span>
                <div class="dim-bar">
                  <div class="dim-bar-fill" :style="{ width: currentDetail[dim.key] + '%', background: dim.color }"></div>
                </div>
                <span class="dim-score">{{ currentDetail[dim.key] }}</span>
              </div>
            </div>
          </div>

          <!-- 匹配亮点 -->
          <div v-if="currentDetail.match_highlights" class="detail-section">
            <h4 class="section-title section-highlight">匹配亮点</h4>
            <div class="highlight-box">
              {{ currentDetail.match_highlights }}
            </div>
          </div>

          <!-- 匹配不足 -->
          <div v-if="currentDetail.match_gaps" class="detail-section">
            <h4 class="section-title section-gap">存在差距</h4>
            <div class="gap-box">
              {{ currentDetail.match_gaps }}
            </div>
          </div>

          <!-- 详细匹配项 -->
          <div v-if="getMatchDetails(currentDetail).length > 0" class="detail-section">
            <h4 class="section-title">详细匹配项</h4>
            <div class="match-detail-list">
              <div v-for="(item, i) in getMatchDetails(currentDetail)" :key="i" class="match-detail-item">
                <div class="detail-item-header">
                  <span class="detail-item-name">{{ item.field_name || '维度' + (i+1) }}</span>
                  <span class="detail-item-score" :class="item.passed ? 'matched' : 'unmatched'">
                    {{ item.passed ? '✓ 匹配' : '✗ 不匹配' }}
                  </span>
                </div>
                <div v-if="item.requirement" class="detail-item-row">
                  <span class="row-label">要求：</span>
                  <span class="row-value">{{ item.requirement }}</span>
                </div>
                <div v-if="item.resume_value && item.resume_value !== '未提供'" class="detail-item-row">
                  <span class="row-label">实际：</span>
                  <span class="row-value">{{ item.resume_value }}</span>
                </div>
                <div v-if="item.reason" class="detail-item-row">
                  <span class="row-label">说明：</span>
                  <span class="row-value">{{ item.reason }}</span>
                </div>
              </div>
            </div>
          </div>
          </div>

          <!-- ========== 人工评价标签页 ========== -->
          <div v-show="detailTab === 'review'" class="tab-content">
            <div v-if="manualReview" class="review-existing-tip">
              <span class="tip-icon">✓</span>
              已有人工评价，可修改更新
            </div>
            <div class="fb-form-group">
              <label class="fb-form-label">HR星级打分 <span class="fb-required">*</span></label>
              <div class="star-rating">
                <span v-for="n in 5" :key="n" class="star" :class="{ active: n <= reviewForm.hr_rating }" @click="reviewForm.hr_rating = n">★</span>
                <span class="star-text">{{ ['很差','较差','一般','较好','很好'][reviewForm.hr_rating - 1] }}</span>
              </div>
            </div>
            <div class="fb-form-group">
              <label class="fb-form-label">文字评价</label>
              <textarea v-model="reviewForm.hr_comment" rows="4" class="fb-form-textarea" placeholder="请输入对该候选人的综合评价，包括优势、不足、录用建议等..."></textarea>
            </div>
            <div class="fb-form-group">
              <label class="fb-form-label">AI偏差类型</label>
              <select v-model="reviewForm.ai_deviation_type" class="fb-form-select">
                <option value="">无偏差/不标注</option>
                <option value="高估">AI高估（AI分高但实际不合适）</option>
                <option value="低估">AI低估（AI分低但实际合适）</option>
                <option value="识别错误">AI识别错误（简历信息提取有误）</option>
                <option value="维度遗漏">维度遗漏（关键维度未匹配到）</option>
                <option value="其他">其他</option>
              </select>
            </div>
            <div class="fb-form-row">
              <div class="fb-form-group">
                <label class="fb-form-label">AI分数修正</label>
                <input v-model.number="reviewForm.ai_score_correction" type="number" min="0" max="100" class="fb-form-input" placeholder="0-100，留空不修正" />
              </div>
              <div class="fb-form-group">
                <label class="fb-form-label">评价人</label>
                <input v-model="reviewForm.reviewer_name" type="text" class="fb-form-input" placeholder="请输入评价人姓名" />
              </div>
            </div>
            <div class="fb-form-actions">
              <button class="fb-btn-primary" @click="saveManualReview" :disabled="savingReview">
                {{ savingReview ? '保存中...' : (manualReview ? '更新评价' : '提交评价') }}
              </button>
            </div>
          </div>

          <!-- ========== 面试反馈标签页 ========== -->
          <div v-show="detailTab === 'interview'" class="tab-content">
            <div v-if="interviewFeedback" class="review-existing-tip">
              <span class="tip-icon">✓</span>
              已有面试反馈，可修改更新
            </div>
            <div class="fb-form-group">
              <label class="fb-form-label">面试安排</label>
              <div class="interview-schedule-toggle" @click="toggleInterviewScheduled">
                <div class="toggle-track" :class="{ active: interviewForm.interview_scheduled }">
                  <div class="toggle-thumb"></div>
                </div>
                <span class="toggle-label">{{ interviewForm.interview_scheduled ? '✓ 已安排面试' : '未安排面试' }}</span>
                <span v-if="currentDetail?.interview_scheduled_at" class="schedule-time">{{ formatDate(currentDetail.interview_scheduled_at) }}</span>
              </div>
            </div>
            <div class="fb-form-group">
              <label class="fb-form-label">面试结果 <span class="fb-required">*</span></label>
              <div class="result-options">
                <div class="result-option" :class="{ selected: interviewForm.interview_result === '通过' }" @click="interviewForm.interview_result = '通过'">
                  <span class="option-pass">✓ 通过</span>
                </div>
                <div class="result-option" :class="{ selected: interviewForm.interview_result === '不通过' }" @click="interviewForm.interview_result = '不通过'">
                  <span class="option-fail">✗ 不通过</span>
                </div>
                <div class="result-option" :class="{ selected: interviewForm.interview_result === '待定' }" @click="interviewForm.interview_result = '待定'">
                  <span class="option-pending">⏳ 待定</span>
                </div>
              </div>
            </div>
            <div v-if="interviewForm.interview_result === '不通过'" class="fb-form-group">
              <label class="fb-form-label">失败原因（可多选）</label>
              <div class="fail-reasons-grid">
                <div v-for="reason in failReasonOptions" :key="reason" class="fail-reason-item" :class="{ selected: interviewForm.fail_reasons.includes(reason) }" @click="toggleFailReason(reason)">
                  {{ reason }}
                </div>
              </div>
            </div>
            <div class="fb-form-group">
              <label class="fb-form-label">自定义备注</label>
              <textarea v-model="interviewForm.custom_note" rows="3" class="fb-form-textarea" placeholder="请输入面试中的具体表现、面试官评价、不通过的详细原因等..."></textarea>
            </div>
            <div class="fb-form-row">
              <div class="fb-form-group">
                <label class="fb-form-label">面试官</label>
                <input v-model="interviewForm.interviewer" type="text" class="fb-form-input" placeholder="请输入面试官姓名" />
              </div>
              <div class="fb-form-group">
                <label class="fb-form-label">面试日期</label>
                <input v-model="interviewForm.interview_date" type="date" class="fb-form-input" />
              </div>
            </div>
            <div class="ai-learn-tip">
              <span class="tip-icon">💡</span>
              保存面试反馈后，系统将自动学习此案例数据，用于优化AI匹配权重和语义识别规则，实现越用越精准。
            </div>
            <div class="fb-form-actions">
              <button class="fb-btn-primary" @click="saveInterviewFeedback" :disabled="savingInterview">
                {{ savingInterview ? '保存中...' : (interviewFeedback ? '更新反馈' : '提交反馈') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.match-result-page {
  display: flex;
  flex-direction: column;
  gap: 0;
  width: 100%;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 8px;
}
.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #1E293B;
  margin: 0;
}
.page-desc {
  font-size: 13px;
  color: #64748B;
  margin-top: 4px;
}
.resume-filter-tip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
  border: 1px solid #93C5FD;
  border-radius: 8px;
  margin-bottom: 16px;
}
.filter-tip-icon { font-size: 18px; }
.filter-tip-text { font-size: 13px; color: #1E40AF; flex: 1; }
.filter-tip-text b { color: #1D4ED8; font-weight: 700; }
.filter-clear-btn {
  padding: 5px 14px;
  background: #fff;
  border: 1px solid #93C5FD;
  border-radius: 6px;
  font-size: 12px;
  color: #2563EB;
  cursor: pointer;
  font-weight: 500;
  white-space: nowrap;
}
.filter-clear-btn:hover { background: #EFF6FF; }
.header-actions {
  display: flex;
  gap: 10px;
}
.btn-refresh {
  padding: 8px 18px;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
}
.btn-refresh:hover { background: #F8FAFC; }
.btn-refresh:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-export {
  padding: 8px 18px;
  background: linear-gradient(135deg, #10B981 0%, #059669 100%);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-export:hover { background: linear-gradient(135deg, #059669 0%, #047857 100%); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3); }
.btn-export:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
.btn-match-all {
  padding: 8px 20px;
  background: #4F6EF7;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-match-all:hover { background: #3B5BE5; }
.btn-match-all:disabled { opacity: 0.5; cursor: not-allowed; }

/* 上传统计概览 */
.upload-stats-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 8px; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 8px; }
.upload-stat-card { padding: 14px 18px; border-radius: 10px; border: 1px solid #E2E8F0; background: #fff; }
.upload-stat-today { background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%); border-color: #BFDBFE; }
.upload-stat-yesterday { background: linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%); border-color: #BBF7D0; }
.upload-stat-week { background: linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%); border-color: #FDE68A; }
.upload-stat-total { background: linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%); border-color: #DDD6FE; }
.upload-stat-label { font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 8px; }
.upload-stat-values { display: flex; align-items: baseline; gap: 4px; flex-wrap: wrap; }
.upload-stat-num { font-size: 22px; font-weight: 700; color: #1E293B; }
.upload-stat-unit { font-size: 12px; color: #64748B; }
.upload-stat-divider { color: #CBD5E1; }

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 20px;
  background: #fff;
  border: 1px solid #E8ECF0;
  border-radius: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.filter-item label {
  font-size: 12px;
  color: #64748B;
  font-weight: 500;
}
.filter-select {
  padding: 0 12px;
  height: 34px;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  font-size: 13px;
  color: #475569;
  background: #fff;
  min-width: 130px;
  cursor: pointer;
  box-sizing: border-box;
}
.filter-input {
  padding: 0 12px;
  height: 34px;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  font-size: 13px;
  color: #475569;
  background: #fff;
  min-width: 130px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.filter-input:focus {
  border-color: #6366F1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
}
.filter-name-item {
  min-width: 150px;
}
.btn-reset-filter {
  padding: 0 16px;
  background: #F1F5F9;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  font-size: 13px;
  color: #64748B;
  cursor: pointer;
  height: 34px;
  box-sizing: border-box;
  margin-top: 20px;
}
.btn-reset-filter:hover { background: #E2E8F0; }

/* 多选下拉 */
.multi-select { position: relative; width: 180px; }
.multi-select-trigger {
  display: flex; align-items: center; justify-content: space-between;
  height: 34px; padding: 0 12px;
  background: #fff; border: 1px solid #E2E8F0; border-radius: 6px;
  font-size: 13px; color: #334155; cursor: pointer;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.multi-select-trigger:hover { border-color: #94A3B8; }
.multi-select-trigger.active { border-color: #4F6EF7; box-shadow: 0 0 0 3px rgba(79,110,247,0.1); }
.multi-select-trigger .placeholder { color: #94A3B8; }
.multi-select-arrow { font-size: 10px; color: #94A3B8; margin-left: 8px; }
.multi-select-dropdown {
  position: absolute; top: calc(100% + 4px); left: 0; right: 0;
  background: #fff; border: 1px solid #E2E8F0; border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12); z-index: 100;
  max-height: 280px; display: flex; flex-direction: column;
}
.multi-select-actions {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; border-bottom: 1px solid #F1F5F9;
  font-size: 12px; color: #64748B;
}
.multi-select-clear {
  background: none; border: none; color: #4F6EF7; font-size: 12px;
  cursor: pointer; padding: 2px 6px; border-radius: 4px;
}
.multi-select-clear:hover { background: #EEF2FF; }
.multi-select-list { overflow-y: auto; flex: 1; padding: 4px 0; }
.multi-select-option {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; cursor: pointer; font-size: 13px; color: #334155;
  transition: background 0.15s;
}
.multi-select-option:hover { background: #F8FAFC; }
.multi-select-option.selected { background: #EEF2FF; color: #4F6EF7; }
.multi-select-option input[type="checkbox"] {
  width: 14px; height: 14px; accent-color: #4F6EF7; cursor: pointer;
}
.multi-select-empty {
  padding: 20px 12px; text-align: center; font-size: 12px; color: #94A3B8;
}

/* 结果卡片 */
.result-card {
  background: #fff;
  border: 1px solid #E8ECF0;
  border-radius: 10px;
  overflow: hidden;
}
.result-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 20px;
  border-bottom: 1px solid #F0F2F5;
}
.result-header-line {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.result-header-line .result-count {
  margin-left: auto;
}
.expand-collapse-group {
  display: flex;
  gap: 6px;
  align-items: center;
}
.action-btn-group {
  display: flex;
  gap: 6px;
  align-items: center;
}
.header-actions-right {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.btn-refresh-sm {
  padding: 5px 12px;
  font-size: 12px;
  border: 1px solid #CBD5E1;
  background: #fff;
  color: #475569;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-refresh-sm:hover:not(:disabled) { background: #F1F5F9; border-color: #94A3B8; }
.btn-refresh-sm:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-export-sm {
  padding: 5px 12px;
  font-size: 12px;
  border: 1px solid #10B981;
  background: #fff;
  color: #10B981;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-export-sm:hover:not(:disabled) { background: #ECFDF5; }
.btn-export-sm:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-match-all-sm {
  padding: 5px 12px;
  font-size: 12px;
  border: 1px solid #4F6EF7;
  background: #4F6EF7;
  color: #fff;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-match-all-sm:hover:not(:disabled) { background: #3B5DE8; }
.btn-match-all-sm:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-delete-all-sm {
  padding: 5px 12px;
  font-size: 12px;
  border: 1px solid #EF4444;
  background: #fff;
  color: #EF4444;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-delete-all-sm:hover:not(:disabled) { background: #FEF2F2; }
.btn-delete-all-sm:disabled { opacity: 0.5; cursor: not-allowed; }
.result-title {
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
}
.result-count {
  font-size: 13px;
  color: #94A3B8;
}
.header-actions { display: flex; align-items: center; gap: 8px; }
.header-action-btn {
  padding: 5px 12px;
  font-size: 12px;
  border: 1px solid #E2E8F0;
  background: #fff;
  color: #475569;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.header-action-btn:hover { background: #F8FAFC; border-color: #CBD5E1; color: #1E293B; }

/* 加载和空状态 */
.loading-state, .empty-state {
  padding: 60px 20px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #E2E8F0;
  border-top-color: #4F6EF7;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.empty-icon { font-size: 48px; }
.empty-text { font-size: 16px; font-weight: 600; color: #475569; }
.empty-hint { font-size: 13px; color: #94A3B8; }

/* 视图切换 */
.view-toggle { display: flex; gap: 4px; background: #F1F5F9; padding: 3px; border-radius: 8px; }
.view-toggle-btn { padding: 5px 12px; font-size: 12px; border: none; background: transparent; color: #64748B; border-radius: 6px; cursor: pointer; transition: all 0.2s; }
.view-toggle-btn.active { background: #fff; color: #4F6EF7; font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }

/* 显示模式切换 */
.display-mode-switch { display: flex; gap: 4px; background: #F1F5F9; padding: 3px; border-radius: 8px; }
.mode-btn { padding: 5px 12px; font-size: 12px; border: none; background: transparent; color: #64748B; border-radius: 6px; cursor: pointer; transition: all 0.2s; white-space: nowrap; }
.mode-btn.active { background: #fff; color: #0EA5E9; font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }

/* 分组视图 */
.grouped-view { display: flex; flex-direction: column; gap: 12px; }

/* 层级标签 */
.group-level-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; margin-right: 8px; }
.level-1 { background: #6366F1; color: #fff; }
.level-2 { background: #10B981; color: #fff; }
.level-3 { background: #3B82F6; color: #fff; }
.group-company { background: #fff; border: 2px solid #C7D2FE; border-radius: 12px; overflow: hidden; margin-bottom: 12px; }
.company-header { background: linear-gradient(135deg, #E0E7FF 0%, #EDE9FE 100%); padding: 14px 18px; border-bottom: 2px solid #C7D2FE; }
.position-header { background: linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%); padding: 12px 16px; }
.owner-group-header { background: linear-gradient(135deg, #D1FAE5 0%, #CCFBF1 100%); padding: 14px 18px; border-bottom: 2px solid #6EE7B7; }
.date-group-header { background: linear-gradient(135deg, #FFEDD5 0%, #FED7AA 100%); padding: 14px 18px; border-bottom: 2px solid #FDBA74; }
.date-results-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; padding: 12px 0; }
.mini-company { font-size: 11px; color: #4F46E5; font-weight: 500; }
.mini-position { font-size: 11px; color: #059669; font-weight: 500; }
.group-header { display: flex; align-items: center; gap: 10px; cursor: pointer; user-select: none; position: sticky; top: 0; z-index: 10; }
.group-toggle { font-size: 12px; color: #64748B; width: 16px; }
.group-icon { font-size: 18px; }
.group-title { font-size: 15px; font-weight: 600; color: #1E293B; }
.group-stats { margin-left: auto; font-size: 12px; color: #64748B; }
.group-children { padding: 12px 12px 12px 28px; border-left: 3px dashed #CBD5E1; margin-left: 20px; }
.load-more-wrap { display: flex; justify-content: center; padding: 10px 0; }
.load-more-btn {
  padding: 6px 16px;
  font-size: 12px;
  color: #4F46E5;
  background: #EEF2FF;
  border: 1px solid #C7D2FE;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.load-more-btn:hover { background: #E0E7FF; color: #4338CA; }
.group-position { margin-top: 10px; border: 2px solid #86EFAC; border-radius: 10px; overflow: hidden; background: #F0FDF4; }
.position-header { background: linear-gradient(135deg, #DCFCE7 0%, #D1FAE5 100%); padding: 12px 16px; border-bottom: 1px solid #86EFAC; }
.group-owner { margin: 10px; padding: 12px; background: #EFF6FF; border: 2px solid #93C5FD; border-radius: 8px; }
.owner-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px dashed #BFDBFE; }
.owner-name { font-size: 14px; font-weight: 600; color: #334155; }
.owner-stats { margin-left: auto; display: flex; gap: 6px; }
.stat-badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
.stat-total { background: #E0E7FF; color: #4338CA; }
.stat-passed { background: #D1FAE5; color: #065F46; }
.stat-avg { background: #FEF3C7; color: #92400E; }
.owner-results { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }
.result-mini-card { background: #fff; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 12px; cursor: pointer; transition: all 0.2s; }
.result-mini-card:hover { border-color: #6366F1; box-shadow: 0 2px 8px rgba(99,102,241,0.15); transform: translateY(-1px); }
.mini-candidate { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.mini-name { font-size: 13px; font-weight: 600; color: #1E293B; }
.mini-score { font-size: 12px; font-weight: 700; padding: 2px 6px; border-radius: 4px; }
.mini-score.score-high { background: #D1FAE5; color: #065F46; }
.mini-score.score-mid { background: #FEF3C7; color: #92400E; }
.mini-score.score-low { background: #FEE2E2; color: #991B1B; }
.mini-meta { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.mini-method { font-size: 11px; color: #64748B; }
.mini-sent { font-size: 11px; color: #059669; }
.mini-interview { font-size: 11px; color: #8B5CF6; }
.mini-actions { display: flex; gap: 6px; margin-top: 8px; padding-top: 8px; border-top: 1px solid #F1F5F9; }
.mini-action-btn { flex: 1; padding: 4px 0; font-size: 11px; border: 1px solid #E2E8F0; background: #fff; border-radius: 5px; cursor: pointer; transition: all 0.2s; color: #475569; }
.mini-action-btn:hover { opacity: 0.85; }
.mini-action-detail { color: #4F46E5; border-color: #C7D2FE; background: #EEF2FF; }
.mini-action-send { color: #059669; border-color: #A7F3D0; background: #ECFDF5; }
.mini-action-delete { color: #DC2626; border-color: #FECACA; background: #FEF2F2; }

/* 表格 */
.result-table-wrap {
  overflow-x: auto;
}
.result-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.result-table th {
  background: #F8FAFC;
  padding: 12px 14px;
  text-align: left;
  font-weight: 600;
  color: #64748B;
  font-size: 12.5px;
  border-bottom: 1px solid #E2E8F0;
  white-space: nowrap;
}
.result-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #F1F5F9;
  color: #334155;
}
.result-row:hover { background: #F8FAFC; }
.cell-index { color: #94A3B8; }
.candidate-name { font-weight: 600; color: #1E293B; }
.cell-position { color: #475569; }
.cell-company { color: #64748B; font-size: 12.5px; }

.score-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: 700;
  font-size: 13px;
}
.score-badge.high { background: #ECFDF5; color: #10B981; }
.score-badge.mid { background: #FFFBEB; color: #F59E0B; }
.score-badge.low { background: #FEF2F2; color: #EF4444; }

/* 简洁模式 TABLE */
.simple-load-more-row { background: #FAFBFC; }
.simple-load-more-btn {
  padding: 6px 20px;
  font-size: 13px;
  border: 1px solid #CBD5E1;
  background: #fff;
  color: #4F6EF7;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.simple-load-more-btn:hover { background: #EFF4FF; border-color: #4F6EF7; }

.simple-mode-wrap { overflow-x: auto; border-radius: 8px; }
.simple-table { width: 100%; border-collapse: collapse; font-size: 13px; background: #fff; }
.simple-sub-header-row { background: #F8FAFC; }
.simple-sub-header-row th { padding: 8px 12px; font-size: 13px; font-weight: 600; color: #475569; text-align: left; border-bottom: 1px solid #E2E8F0; }

.simple-table-header th { background: #F8FAFC; color: #475569; font-weight: 600; padding: 10px 8px; text-align: center; border-bottom: 2px solid #E2E8F0; white-space: nowrap; }
.simple-group-row { font-weight: 600; }
.simple-group-row td { padding: 8px 12px; border-bottom: 1px solid #E2E8F0; }
.level-1-row td { background: linear-gradient(90deg, #EEF2FF 0%, #F5F3FF 100%); color: #4338CA; font-size: 14px; }
.level-2-row td { background: linear-gradient(90deg, #F0FDF4 0%, #ECFDF5 100%); color: #047857; }
.level-3-row td { background: linear-gradient(90deg, #EFF6FF 0%, #F0F9FF 100%); color: #1D4ED8; }
.group-stat { font-weight: 400; font-size: 12px; color: #64748B; margin-left: 8px; }
.simple-data-row td { padding: 8px; border-bottom: 1px solid #F1F5F9; text-align: center; }
.simple-data-row:hover { background: #F8FAFC; }
.simple-data-row.selected { background: #EFF6FF; }
.candidate-cell { text-align: left !important; font-weight: 500; color: #1E293B; }
.action-cell { white-space: nowrap; }
.simple-action-btn { padding: 3px 8px; font-size: 12px; border: 1px solid #E2E8F0; background: #fff; color: #475569; border-radius: 4px; cursor: pointer; margin: 0 2px; transition: all 0.2s; }
.simple-action-btn:hover { background: #F1F5F9; border-color: #CBD5E1; }
.simple-action-btn.danger { color: #EF4444; border-color: #FECACA; }
.simple-action-btn.danger:hover { background: #FEF2F2; }

.tag-passed {
  display: inline-block;
  padding: 2px 6px;
  background: #ECFDF5;
  color: #10B981;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.tag-rejected {
  display: inline-block;
  padding: 2px 6px;
  background: #FEF2F2;
  color: #EF4444;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

.cell-interview-status { text-align: center; }
.interview-tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
.interview-pass { background: #ECFDF5; color: #10B981; }
.interview-fail { background: #FEF2F2; color: #EF4444; }
.interview-scheduled { background: #EFF6FF; color: #3B82F6; }
.interview-none { background: #F1F5F9; color: #94A3B8; }
.interview-status-cell {
  display: flex;
  align-items: center;
}
.status-scheduled {
  display: inline-block;
  padding: 3px 8px;
  background: #DBEAFE;
  color: #2563EB;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}
.status-not-scheduled {
  color: #94A3B8;
  font-size: 12px;
}

.method-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.method-ai { background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0; }
.method-rule { background: #FFF7ED; color: #C2410C; border: 1px solid #FED7AA; }

.action-btns {
  display: flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
}
.btn-detail {
  padding: 3px 10px;
  background: #EEF1FE;
  color: #4F6EF7;
  border: 1px solid #C7D2FE;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}
.btn-detail:hover { background: #E0E6FD; }
.btn-rematch {
  padding: 3px 10px;
  background: #FFFBEB;
  color: #D97706;
  border: 1px solid #FDE68A;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}
.btn-rematch:hover:not(:disabled) { background: #FEF3C7; }
.btn-rematch:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-delete {
  padding: 3px 10px;
  background: #FEF2F2;
  color: #EF4444;
  border: 1px solid #FECACA;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}
.btn-delete:hover { background: #FEE2E2; }
.btn-delete-all {
  padding: 8px 20px;
  background: #FEF2F2;
  color: #EF4444;
  border: 1px solid #FECACA;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-delete-all:hover { background: #FEE2E2; }
.btn-delete-all:disabled { opacity: 0.5; cursor: not-allowed; }

/* 发送按钮 - 与详情/删除按钮风格统一 */
.btn-send {
  padding: 3px 10px;
  background: #ECFDF5;
  color: #059669;
  border: 1px solid #A7F3D0;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}
.btn-send:hover { background: #D1FAE5; }
.sent-badge {
  display: inline-block;
  padding: 3px 8px;
  background: #D1FAE5;
  color: #059669;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

/* 复选框列 */
.cell-checkbox {
  text-align: center;
}
.cell-checkbox input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #4F6EF7;
}
.row-selected {
  background: #EFF6FF !important;
}


/* 分组视图行形式 */
.group-result-row { display: flex; align-items: center; gap: 12px; padding: 10px 14px; background: #fff; border-bottom: 1px solid #F1F5F9; transition: background 0.2s; }
.group-result-row:hover { background: #F8FAFC; }
.group-result-row.row-selected { background: #EEF2FF; }
.grow-checkbox { width: 30px; flex-shrink: 0; text-align: center; }
.grow-candidate { flex: 1; min-width: 0; cursor: pointer; }
.grow-name { font-weight: 600; color: #334155; font-size: 14px; }
.grow-company { width: 120px; flex-shrink: 0; color: #64748B; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.grow-position { width: 120px; flex-shrink: 0; color: #64748B; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.grow-score { width: 60px; flex-shrink: 0; text-align: center; }
.grow-passed { width: 100px; flex-shrink: 0; text-align: center; }
.grow-method { width: 70px; flex-shrink: 0; text-align: center; }
.grow-actions { width: 160px; flex-shrink: 0; display: flex; gap: 6px; justify-content: flex-end; }
.owner-results { overflow-x: auto; margin-top: 8px; }
.date-results-grid { overflow-x: auto; }
/* 批量操作栏 */
.batch-action-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 16px;
  background: #EFF6FF;
  border: 1px solid #BFDBFE;
  border-radius: 8px;
  margin-bottom: 12px;
}
.batch-selected-info {
  font-size: 13px;
  color: #1E40AF;
}
.batch-selected-info strong {
  color: #1D4ED8;
  font-size: 15px;
}
.batch-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
  align-items: center;
}
.batch-btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  white-space: nowrap;
}
.batch-send {
  background: #2563EB;
  color: #fff;
}
.batch-send:hover:not(:disabled) {
  background: #1D4ED8;
}
.batch-send:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.batch-cancel {
  background: #fff;
  color: #64748B;
  border: 1px solid #CBD5E1;
}
.batch-cancel:hover {
  background: #F8FAFC;
}
.batch-message {
  font-size: 12px;
  color: #059669;
  font-weight: 500;
  white-space: nowrap;
}

/* 详情弹窗 */
.detail-modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.detail-content {
  background: #fff;
  border-radius: 12px;
  width: 90%;
  max-width: 720px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.detail-header {
  padding: 20px 24px;
  border-bottom: 1px solid #F0F2F5;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.detail-title {
  font-size: 18px;
  font-weight: 700;
  color: #1E293B;
  margin: 0;
}
.detail-subtitle {
  font-size: 13px;
  color: #64748B;
  margin-top: 4px;
}
.btn-close {
  background: none;
  border: none;
  font-size: 18px;
  color: #94A3B8;
  cursor: pointer;
  padding: 4px 8px;
}
.btn-close:hover { color: #475569; }

.detail-body {
  padding: 20px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 概览 */
.detail-overview {
  display: flex;
  gap: 24px;
  align-items: center;
  padding: 16px;
  background: #F8FAFC;
  border-radius: 10px;
}
.score-circle {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.score-circle.high { background: linear-gradient(135deg, #10B981, #34D399); color: #fff; }
.score-circle.mid { background: linear-gradient(135deg, #F59E0B, #FBBF24); color: #fff; }
.score-circle.low { background: linear-gradient(135deg, #EF4444, #F87171); color: #fff; }
.score-num { font-size: 32px; font-weight: 700; line-height: 1; }
.score-label { font-size: 11px; margin-top: 4px; opacity: 0.9; }
.overview-info { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.info-label { color: #64748B; flex-shrink: 0; }
.reject-reason { color: #EF4444; }

/* 维度得分 */
.detail-section { display: flex; flex-direction: column; gap: 12px; }
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
  margin: 0;
}
.section-highlight { color: #10B981; }
.section-gap { color: #EF4444; }

.dimension-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dimension-item {
  display: flex;
  align-items: center;
  gap: 12px;
}
.dim-label {
  width: 70px;
  font-size: 13px;
  color: #475569;
  flex-shrink: 0;
}
.dim-bar {
  flex: 1;
  height: 8px;
  background: #E2E8F0;
  border-radius: 4px;
  overflow: hidden;
}
.dim-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}
.dim-score {
  width: 30px;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
  color: #1E293B;
}

.highlight-box {
  padding: 12px 16px;
  background: #ECFDF5;
  border-radius: 8px;
  font-size: 13px;
  color: #065F46;
  line-height: 1.7;
}
.gap-box {
  padding: 12px 16px;
  background: #FEF2F2;
  border-radius: 8px;
  font-size: 13px;
  color: #991B1B;
  line-height: 1.7;
}

/* 详细匹配项 */
.match-detail-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.match-detail-item {
  padding: 12px 14px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
}
.detail-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.detail-item-name {
  font-size: 13px;
  font-weight: 600;
  color: #1E293B;
}
.detail-item-score {
  font-size: 12px;
  font-weight: 500;
}
.detail-item-score.matched { color: #10B981; }
.detail-item-score.unmatched { color: #EF4444; }
.detail-item-row {
  display: flex;
  gap: 8px;
  font-size: 12.5px;
  margin-top: 4px;
}
.row-label { color: #94A3B8; flex-shrink: 0; }
.row-value { color: #475569; }

/* 详情标签页 */
.detail-tabs {
  display: flex;
  border-bottom: 2px solid #E2E8F0;
  padding: 0 20px;
  gap: 0;
}
.detail-tab {
  padding: 12px 20px;
  font-size: 14px;
  font-weight: 500;
  color: #64748B;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}
.detail-tab:hover { color: #4F6EF7; }
.detail-tab.active {
  color: #4F6EF7;
  border-bottom-color: #4F6EF7;
  font-weight: 600;
}
.tab-badge {
  font-size: 10px;
  padding: 1px 6px;
  background: #F1F5F9;
  color: #64748B;
  border-radius: 8px;
  font-weight: 500;
}
.badge-pass { background: #ECFDF5; color: #10B981; }
.badge-fail { background: #FEF2F2; color: #EF4444; }
.badge-pending { background: #FFFBEB; color: #F59E0B; }

.tab-content { padding-top: 10px; }

/* 已有评价提示 */
.review-existing-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #ECFDF5;
  border-radius: 8px;
  font-size: 13px;
  color: #059669;
  margin-bottom: 16px;
}
.review-existing-tip .tip-icon {
  width: 20px;
  height: 20px;
  background: #10B981;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

/* 星级打分 */
.star-rating {
  display: flex;
  align-items: center;
  gap: 4px;
}
.star {
  font-size: 28px;
  color: #E2E8F0;
  cursor: pointer;
  transition: color 0.15s;
}
.star:hover { transform: scale(1.1); }
.star.active { color: #F59E0B; }
.star-text {
  margin-left: 10px;
  font-size: 13px;
  color: #64748B;
}

/* 面试结果选项 */
.result-options {
  display: flex;
  gap: 12px;
}
.result-option {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  border: 2px solid #E2E8F0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.result-option input { display: none; }
.result-option.selected { border-color: #4F6EF7; background: #EEF2FF; }
.option-pass { color: #10B981; font-weight: 600; font-size: 14px; }
.option-fail { color: #EF4444; font-weight: 600; font-size: 14px; }
.option-pending { color: #F59E0B; font-weight: 600; font-size: 14px; }

/* 失败原因网格 */
.fail-reasons-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.fail-reason-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  color: #475569;
  transition: all 0.15s;
}
.fail-reason-item:hover { border-color: #CBD5E1; background: #F8FAFC; }
.fail-reason-item.selected { border-color: #EF4444; background: #FEF2F2; color: #DC2626; }
.fail-reason-item input { display: none; }

/* 表单行 */
.form-row {
  display: flex;
  gap: 12px;
}

/* AI学习提示 */
.ai-learn-tip {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 14px;
  background: #EFF6FF;
  border-radius: 8px;
  font-size: 12px;
  color: #1E40AF;
  margin: 16px 0;
  line-height: 1.6;
}
.ai-learn-tip .tip-icon { font-size: 16px; }

/* ========== 反馈表单统一样式 ========== */
.tab-content {
  padding: 16px 4px;
}
.fb-form-group {
  margin-bottom: 18px;
}
.fb-form-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 8px;
}
.fb-required {
  color: #EF4444;
  margin-left: 2px;
}
.fb-form-input,
.fb-form-select,
.fb-form-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  font-size: 13px;
  color: #1E293B;
  background: #fff;
  transition: all 0.2s;
  box-sizing: border-box;
  outline: none;
}
.fb-form-input:focus,
.fb-form-select:focus,
.fb-form-textarea:focus {
  border-color: #4F6EF7;
  box-shadow: 0 0 0 3px rgba(79, 110, 247, 0.1);
}
.fb-form-input::placeholder,
.fb-form-textarea::placeholder {
  color: #94A3B8;
}
.fb-form-textarea {
  resize: vertical;
  min-height: 80px;
  line-height: 1.6;
  font-family: inherit;
}
.fb-form-select {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2364748B' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
}
.fb-form-row {
  display: flex;
  gap: 14px;
}
.fb-form-row .fb-form-group {
  flex: 1;
  margin-bottom: 0;
}
.fb-form-actions {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
  border-top: 1px solid #F1F5F9;
}
.fb-btn-primary {
  padding: 10px 28px;
  background: linear-gradient(135deg, #4F6EF7, #6366F1);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(79, 110, 247, 0.25);
}
.fb-btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 110, 247, 0.35);
}
.fb-btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 面试安排开关 */
.interview-schedule-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  padding: 8px 0;
}
.toggle-track {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background: #CBD5E1;
  position: relative;
  transition: background 0.2s;
  flex-shrink: 0;
}
.toggle-track.active {
  background: #10B981;
}
.toggle-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: white;
  position: absolute;
  top: 2px;
  left: 2px;
  transition: left 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.toggle-track.active .toggle-thumb {
  left: 22px;
}
.toggle-label {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}
.schedule-time {
  font-size: 12px;
  color: #94A3B8;
}

/* 面试结果选项优化 */
.result-options {
  display: flex;
  gap: 10px;
}
.result-option {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px 12px;
  border: 2px solid #E2E8F0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}
.result-option:hover {
  border-color: #CBD5E1;
  background: #F8FAFC;
}
.result-option.selected {
  border-color: #4F6EF7;
  background: #EEF2FF;
}
.option-pass, .option-fail, .option-pending {
  font-weight: 600;
  font-size: 14px;
}

/* 失败原因网格优化 */
.fail-reasons-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.fail-reason-item {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 8px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  color: #475569;
  transition: all 0.15s;
  text-align: center;
  background: #fff;
}
.fail-reason-item:hover {
  border-color: #CBD5E1;
  background: #F8FAFC;
}
.fail-reason-item.selected {
  border-color: #EF4444;
  background: #FEF2F2;
  color: #DC2626;
  font-weight: 500;
}

/* 分页 */
.pagination { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 16px; padding-top: 16px; border-top: 1px solid #F1F5F9; }
.page-btn { padding: 6px 14px; border: 1px solid #E2E8F0; border-radius: 6px; background: #fff; color: #475569; font-size: 12px; cursor: pointer; }
.page-btn:hover:not(:disabled) { border-color: #4F6EF7; color: #4F6EF7; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 12px; color: #64748B; }
</style>