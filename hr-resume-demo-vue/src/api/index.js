// API 请求基础配置
const BASE_URL = '/api'

// ========== 本地存储 Token 管理 ==========
export function getToken() {
  return localStorage.getItem('token') || ''
}
export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch { return null }
}
export function setAuth(token, user) {
  localStorage.setItem('token', token)
  localStorage.setItem('user', JSON.stringify(user))
}
export function clearAuth() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

// 401 时跳转登录页
function handleUnauthorized() {
  clearAuth()
  // 避免在登录页重复跳转
  if (!location.hash.includes('login')) {
    location.reload()
  }
}

async function request(url, options = {}) {
  const token = getToken()
  const headers = {}
  // FormData上传时不设置Content-Type，让浏览器自动处理boundary
  if (!options.isFormData) {
    headers['Content-Type'] = 'application/json'
  }
  Object.assign(headers, options.headers || {})
  if (token) {
    headers['Authorization'] = 'Bearer ' + token
  }
  const response = await fetch(`${BASE_URL}${url}`, {
    headers,
    ...options
  })
  if (response.status === 401) {
    handleUnauthorized()
    throw new Error('登录已过期，请重新登录')
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(error.detail || '请求失败')
  }
  return response.json()
}

// ========== 认证 ==========
export const authApi = {
  register: (data) => request('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data) => request('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request('/auth/me'),
  logout: () => { clearAuth() }
}

// ========== 用户管理 ==========
export const userApi = {
  list: () => request('/users/'),
  recruiters: () => request('/users/recruiters'),
  updateRole: (id, role) => request(`/users/${id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) }),
  updateStatus: (id, status) => request(`/users/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  approve: (id) => request(`/users/${id}/approve`, { method: 'POST' })
}

// ========== 公司管理 ==========
export const companyApi = {
  list: () => request('/companies/'),
  listDeleted: () => request('/companies/deleted'),
  get: (id) => request(`/companies/${id}`),
  create: (data) => request('/companies/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => request(`/companies/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => request(`/companies/${id}`, { method: 'DELETE' }),
  restore: (id) => request(`/companies/${id}/restore`, { method: 'POST' })
}

// ========== 岗位管理 ==========
export const positionApi = {
  list: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/positions/${query ? '?' + query : ''}`)
  },
  get: (id) => request(`/positions/${id}`),
  create: (data) => request('/positions/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => request(`/positions/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  updateStatus: (id, status) => request(`/positions/${id}/status?status=${encodeURIComponent(status)}`, { method: 'PATCH' }),
  delete: (id) => request(`/positions/${id}`, { method: 'DELETE' }),
  matchAllResumes: (id) => request(`/positions/${id}/match-all-resumes`, { method: 'POST' })
}

// ========== Schema字段管理 ==========
export const schemaApi = {
  list: (positionId) => request(`/schema-fields/?position_id=${positionId}`),
  create: (data) => request('/schema-fields/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => request(`/schema-fields/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => request(`/schema-fields/${id}`, { method: 'DELETE' }),
  initDefaults: (positionId) => request(`/schema-fields/batch/${positionId}`, { method: 'POST' }),
  batchSave: (positionId, fields) => request(`/schema-fields/batch-save/${positionId}`, { method: 'PUT', body: JSON.stringify({ fields }) })
}

// ========== 简历管理 ==========
export const resumeApi = {
  upload: (files) => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    const token = getToken()
    return fetch(`${BASE_URL}/resumes/upload`, {
      method: 'POST',
      headers: token ? { 'Authorization': 'Bearer ' + token } : {},
      body: formData
    }).then(async res => {
      if (res.status === 401) { handleUnauthorized(); throw new Error('登录已过期') }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '上传失败' }))
        throw new Error(err.detail || '上传失败')
      }
      return res.json()
    })
  },
  getBatchStatus: (batchId) => request(`/resumes/batch/${batchId}`),
  retryTask: (batchId, taskId) => request(`/resumes/batch/${batchId}/retry/${taskId}`, { method: 'POST' }),
  retryAll: (batchId) => request(`/resumes/batch/${batchId}/retry-all`, { method: 'POST' }),
  list: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/resumes/${query ? '?' + query : ''}`)
  },
  get: (id) => request(`/resumes/${id}`),
  delete: (id) => request(`/resumes/${id}`, { method: 'DELETE' }),
  matchAll: (id) => request(`/resumes/match-all/${id}`, { method: 'POST' }),
  matchPosition: (resumeId, positionId) => request(`/resumes/match-position/${resumeId}/${positionId}`, { method: 'POST' }),
  matchResults: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/resumes/match-results/${query ? '?' + query : ''}`)
  },
  deleteMatchResult: (id) => request(`/resumes/match-results/${id}`, { method: 'DELETE' }),
  batchDeleteMatchResults: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/resumes/match-results/${query ? '?' + query : ''}`, { method: 'DELETE' })
  },
  aiStatus: () => request('/resumes/ai/status'),
  reassignOwner: (resumeId, ownerId) => request(`/resumes/${resumeId}/owner`, { method: 'PATCH', body: JSON.stringify({ owner_id: ownerId }) }),
  batchReassign: (resumeIds, ownerId) => request('/resumes/batch-reassign', { method: 'PATCH', body: JSON.stringify({ resume_ids: resumeIds, owner_id: ownerId }) }),
  sendMatchToCompany: (matchId) => request('/resumes/match-results/' + matchId + '/send', { method: 'POST' }),
  batchSendToCompany: (matchIds) => request('/resumes/match-results/batch-send', { method: 'POST', body: JSON.stringify({ match_ids: matchIds }) }),
  toggleInterviewScheduled: (matchId, scheduled) => request('/resumes/match-results/' + matchId + '/interview-scheduled', { method: 'PATCH', body: JSON.stringify({ interview_scheduled: scheduled }) }),
  // 导出匹配结果Excel
  exportMatchResults: async (params = {}) => {
    const token = getToken()
    const query = new URLSearchParams(params).toString()
    const url = BASE_URL + '/export/match-results' + (query ? '?' + query : '')
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': 'Bearer ' + token
      }
    })
    if (!response.ok) {
      throw new Error('导出失败')
    }
    const blob = await response.blob()
    // 从Content-Disposition获取文件名
    const disposition = response.headers.get('Content-Disposition') || ''
    let filename = '匹配结果.xlsx'
    const match = disposition.match(/filename\*=UTF-8''([^;]+)/)
    if (match) {
      filename = decodeURIComponent(match[1])
    }
    // 触发下载
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(link.href)
    return { success: true, filename }
  }
}

// 统计数据
export const statsApi = {
  recruiterDaily: (days = 14) => request('/stats/recruiter-daily?days=' + days),
  dashboard: () => request('/stats/dashboard', { method: 'GET' }),
  recruiters: () => request('/stats/recruiters', { method: 'GET' })
}

// 人工评价与自学习优化
export const feedbackApi = {
  stats: () => request('/feedback/stats', { method: 'GET' }),
  createManualReview: (data) => request('/feedback/manual-reviews', { method: 'POST', body: JSON.stringify(data) }),
  getManualReview: (matchResultId) => request(`/feedback/manual-reviews/${matchResultId}`, { method: 'GET' }),
  listManualReviews: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/feedback/manual-reviews${query ? '?' + query : ''}`)
  },
  createInterviewFeedback: (data) => request('/feedback/interview-feedbacks', { method: 'POST', body: JSON.stringify(data) }),
  getInterviewFeedback: (matchResultId) => request(`/feedback/interview-feedbacks/${matchResultId}`, { method: 'GET' }),
  listInterviewFeedbacks: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/feedback/interview-feedbacks${query ? '?' + query : ''}`)
  },
  runOptimization: (data) => request('/feedback/optimize/run', { method: 'POST', body: JSON.stringify(data) }),
  getOptimizationLogs: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/feedback/optimize/logs${query ? '?' + query : ''}`)
  },
  getAccuracyTrend: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/feedback/optimize/accuracy-trend${query ? '?' + query : ''}`)
  },
}

// ========== 批量导入 ==========
export const batchImportApi = {
  upload: (file, mode) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('mode', mode)
    return request('/batch-import/upload', { method: 'POST', body: formData, isFormData: true })
  },
  downloadTemplate: () => '/api/batch-import/template'
}

// ========== 因子库 ==========
export const factorApi = {
  list: () => request('/factors'),
  fieldTypes: () => request('/factors/field-types'),
  create: (data) => request('/factors', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => request(`/factors/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => request(`/factors/${id}`, { method: 'DELETE' }),
}

// ========== 岗位模板 ==========
export const positionTemplateApi = {
  list: () => request('/position-templates'),
  get: (id) => request(`/position-templates/${id}`),
  create: (data) => request('/position-templates', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => request(`/position-templates/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => request(`/position-templates/${id}`, { method: 'DELETE' }),
  addFactors: (id, factorIds) => request(`/position-templates/${id}/factors`, { method: 'POST', body: JSON.stringify({ factor_ids: factorIds }) }),
  removeFactor: (id, factorId) => request(`/position-templates/${id}/factors/${factorId}`, { method: 'DELETE' }),
}

// ========== 系统配置 ==========
export const systemConfigApi = {
  getAll: () => request('/system-config'),
  update: (configs) => request('/system-config', { method: 'PUT', body: JSON.stringify({ configs }) }),
}
