import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '仪表盘', requiresAuth: true }
  },
  {
    path: '/inventory',
    name: 'Inventory',
    component: () => import('@/views/Inventory.vue'),
    meta: { title: '库存监控', requiresAuth: true }
  },
  {
    path: '/products',
    name: 'Products',
    component: () => import('@/views/Products.vue'),
    meta: { title: '商品列表', requiresAuth: true }
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/History.vue'),
    meta: { title: '历史记录', requiresAuth: true }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { title: '系统设置', requiresAuth: true }
  },
  {
    path: '/tokens',
    name: 'TokenManage',
    component: () => import('@/views/TokenManage.vue'),
    meta: { title: 'Token 管理', requiresAuth: true, requiresAdmin: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫 - 认证检查
router.beforeEach(async (to, from, next) => {
  document.title = `${to.meta.title || 'Arc\'teryx 监控'} - Arc'teryx 商品监控`

  const { isLoggedIn, isAdmin, checkAuth, token } = useAuth()

  // 如果路由不需要认证，直接通过
  if (to.meta.requiresAuth === false) {
    // 如果已登录访问登录页，重定向到首页
    if (to.path === '/login' && isLoggedIn.value) {
      next('/')
      return
    }
    next()
    return
  }

  // 检查是否已登录
  if (!isLoggedIn.value) {
    // 只有存在 token 但未登录时才尝试恢复登录状态
    if (token.value) {
      const authenticated = await checkAuth()
      if (!authenticated) {
        // 未登录，跳转到登录页
        next('/login')
        return
      }
    } else {
      // 没有 token，直接跳转登录页
      next('/login')
      return
    }
  }

  // 检查是否需要管理员权限
  if (to.meta.requiresAdmin && !isAdmin.value) {
    // Token 用户访问管理员页面，跳转到首页
    next('/')
    return
  }

  next()
})

export default router
