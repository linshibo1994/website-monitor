import { reactive, computed } from 'vue'

// 认证状态管理
const state = reactive({
  token: localStorage.getItem('auth_token') || null,
  user: null,
  isLoggedIn: false
})

// 存储token到localStorage
const saveToken = (token) => {
  if (token) {
    localStorage.setItem('auth_token', token)
    state.token = token
  } else {
    localStorage.removeItem('auth_token')
    state.token = null
  }
}

// 用户登录 - 密码方式
const login = async (username, password) => {
  try {
    const { loginWithPassword } = await import('@/api')
    const response = await loginWithPassword(username, password)

    // 后端返回: { access_token, token_type, user_type, expires_in }
    const data = response.data
    if (data.access_token) {
      saveToken(data.access_token)
      state.user = { type: data.user_type, username }
      state.isLoggedIn = true
      return { success: true, user: state.user }
    }
    return { success: false, message: '登录失败' }
  } catch (error) {
    console.error('Login failed:', error)
    const message = error.response?.data?.detail || '登录失败，请检查用户名和密码'
    return { success: false, message }
  }
}

// 用户登录 - Token方式
const loginWithToken = async (token) => {
  try {
    const { loginWithToken: apiLoginWithToken } = await import('@/api')
    const response = await apiLoginWithToken(token)

    // 后端返回: { access_token, token_type, user_type, expires_in }
    const data = response.data
    if (data.access_token) {
      saveToken(data.access_token)
      state.user = { type: data.user_type }
      state.isLoggedIn = true
      return { success: true, user: state.user }
    }
    return { success: false, message: '登录失败' }
  } catch (error) {
    console.error('Token login failed:', error)
    const message = error.response?.data?.detail || 'Token登录失败，请检查Token是否有效'
    return { success: false, message }
  }
}

// 退出登录
const logout = () => {
  saveToken(null)
  state.user = null
  state.isLoggedIn = false
}

// 检查认证状态
const checkAuth = async () => {
  if (!state.token) {
    state.isLoggedIn = false
    return false
  }

  try {
    const { getCurrentUser } = await import('@/api')
    const response = await getCurrentUser()

    // 后端返回: { subject, type, token_id, token_name, is_admin }
    const data = response.data
    if (data.subject) {
      state.user = {
        type: data.type,
        username: data.subject,
        tokenId: data.token_id,
        tokenName: data.token_name,
        isAdmin: data.is_admin
      }
      state.isLoggedIn = true
      return true
    } else {
      logout()
      return false
    }
  } catch (error) {
    console.error('Auth check failed:', error)
    logout()
    return false
  }
}

// 导出 composable
export function useAuth() {
  return {
    // 状态
    token: computed(() => state.token),
    user: computed(() => state.user),
    isLoggedIn: computed(() => state.isLoggedIn),
    isAdmin: computed(() => state.user && state.user.type === 'admin'),

    // 方法
    login,
    loginWithToken,
    logout,
    checkAuth
  }
}
