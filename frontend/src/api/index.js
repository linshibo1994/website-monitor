import axios from 'axios'

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// 请求拦截器
api.interceptors.request.use(
  config => config,
  error => Promise.reject(error)
)

// 响应拦截器
api.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

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

export default api
