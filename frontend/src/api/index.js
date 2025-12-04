import axios from 'axios'

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// 请求拦截器 - 添加 Authorization 头
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器 - 处理401未授权
api.interceptors.response.use(
  response => response,
  async error => {
    console.error('API Error:', error)

    // 401未授权，自动登出并跳转登录页
    if (error.response && error.response.status === 401) {
      // 动态导入避免循环依赖，同步更新 auth 响应式状态
      const { useAuth } = await import('@/stores/auth')
      const { logout } = useAuth()
      logout()

      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)

// ==================== 认证相关 ====================

// 密码登录
export const loginWithPassword = (username, password) => api.post('/auth/login', { username, password })

// Token登录
export const loginWithToken = (token) => api.post('/auth/login/token', { token })

// 获取当前用户信息
export const getCurrentUser = () => api.get('/auth/me')

// 获取Token列表
export const getTokenList = () => api.get('/tokens')

// 创建新Token
export const createToken = (name, expiresIn) => api.post('/tokens', { name, expires_in: expiresIn })

// 更新Token备注
export const updateToken = (id, name) => api.put(`/tokens/${id}`, { name })

// 删除Token
export const deleteToken = (id) => api.delete(`/tokens/${id}`)

// ==================== 监控相关 ====================

export const getMonitorStatus = () => api.get('/monitor/status')

export const triggerCheck = () => api.post('/monitor/trigger')

export const startScheduler = () => api.post('/monitor/start')

export const stopScheduler = () => api.post('/monitor/stop')

// ==================== 商品相关 ====================

export const getProducts = (params) => api.get('/products', { params })

export const getProduct = (productId) => api.get(`/products/${productId}`)

export const getProductsSummary = () => api.get('/products/stats/summary')

// ==================== 历史记录相关 ====================

export const getHistory = (params) => api.get('/history', { params })

export const getHistoryDetail = (logId) => api.get(`/history/${logId}`)

export const getStatistics = (days = 30) => api.get('/history/statistics', { params: { days } })

export const getRecentChanges = (limit = 10) => api.get('/history/recent', { params: { limit } })

// ==================== 设置相关 ====================

export const getSettings = () => api.get('/settings')

export const updateSettings = (data) => api.put('/settings', data)

export const sendTestEmail = () => api.post('/settings/test-email')

export const reloadConfig = () => api.post('/settings/reload')

// ==================== 健康检查 ====================

export const healthCheck = () => api.get('/health')

// ==================== 库存监控相关 ====================

export const getInventoryStatus = () => api.get('/inventory/status')

export const triggerInventoryCheck = () => api.post('/inventory/check')

export const startInventoryScheduler = (interval = 5) => api.post('/inventory/start', null, { params: { interval_minutes: interval } })

export const stopInventoryScheduler = () => api.post('/inventory/stop')

export const addInventoryProduct = (data) => api.post('/inventory/products', data)

export const removeInventoryProduct = (url) => api.delete('/inventory/products', { params: { url } })

// 获取支持的站点列表
export const getInventorySites = () => api.get('/inventory/sites')

// 智能解析商品输入
export const parseProductInput = (input) => api.post('/inventory/parse', { input })

export default api
