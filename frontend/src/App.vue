<template>
  <el-container class="layout-container" v-if="!isLoginPage">
    <!-- Sidebar -->
    <el-aside width="240px" class="aside">
      <div class="logo-container">
        <div class="logo-icon">
          <el-icon><Monitor /></el-icon>
        </div>
        <span class="logo-text">Arc'teryx Monitor</span>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        class="el-menu-vertical"
        background-color="#001529"
        text-color="#a6adb4"
        active-text-color="#409eff"
        :collapse="false"
      >
        <el-menu-item index="/">
          <el-icon><Odometer /></el-icon>
          <template #title>仪表盘</template>
        </el-menu-item>

        <el-menu-item index="/inventory">
          <el-icon><Box /></el-icon>
          <template #title>库存监控</template>
        </el-menu-item>

        <el-menu-item index="/release">
          <el-icon><Bell /></el-icon>
          <template #title>上线监控</template>
        </el-menu-item>

        <el-menu-item index="/products">
          <el-icon><Goods /></el-icon>
          <template #title>商品列表</template>
        </el-menu-item>

        <el-menu-item index="/history">
          <el-icon><Timer /></el-icon>
          <template #title>历史记录</template>
        </el-menu-item>

        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <template #title>系统设置</template>
        </el-menu-item>

        <!-- Token 管理菜单 - 仅管理员可见 -->
        <el-menu-item v-if="isAdmin" index="/tokens">
          <el-icon><Key /></el-icon>
          <template #title>Token 管理</template>
        </el-menu-item>
      </el-menu>

      <div class="version-info">
        v1.0.0
      </div>
    </el-aside>

    <!-- Main Content -->
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <div class="status-indicator" :class="{ active: monitorStatus.is_running }">
            <span class="dot"></span>
            <span class="text">{{ monitorStatus.is_running ? '监控运行中' : '监控已暂停' }}</span>
          </div>

          <!-- 用户信息和退出 -->
          <el-dropdown @command="handleUserCommand">
            <div class="user-info">
              <el-avatar :size="32" icon="UserFilled" class="user-avatar" />
              <span class="user-name">{{ userName }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  <div class="user-type-tag">
                    <el-tag :type="isAdmin ? 'danger' : 'primary'" size="small">
                      {{ isAdmin ? '管理员' : 'Token 用户' }}
                    </el-tag>
                  </div>
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>

  <!-- 登录页面不显示侧边栏 -->
  <router-view v-else />
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Monitor, Odometer, Box, Goods, Timer, Setting, Key, UserFilled, SwitchButton, Bell } from '@element-plus/icons-vue'
import { getMonitorStatus } from '@/api'
import { useAuth } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const { user, isAdmin, logout } = useAuth()

const monitorStatus = ref({ is_running: false })
let statusTimer = null

const activeMenu = computed(() => route.path)

const isLoginPage = computed(() => route.path === '/login')

const userName = computed(() => {
  if (!user.value) return '未登录'
  if (user.value.username) return user.value.username
  if (user.value.name) return user.value.name
  return isAdmin.value ? '管理员' : 'Token 用户'
})

const currentPageTitle = computed(() => {
  const titles = {
    '/': '仪表盘',
    '/inventory': '库存监控',
    '/release': '上线监控',
    '/products': '商品列表',
    '/history': '历史记录',
    '/settings': '系统设置',
    '/tokens': 'Token 管理'
  }
  return titles[route.path] || 'Monitor'
})

const fetchStatus = async () => {
  // 登录页面不获取状态
  if (isLoginPage.value) return

  try {
    const res = await getMonitorStatus()
    monitorStatus.value = res.data
  } catch (error) {
    console.error('Failed to fetch status', error)
  }
}

// 处理用户菜单命令
const handleUserCommand = async (command) => {
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出登录吗？', '退出登录', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      })

      logout()
      ElMessage.success('已退出登录')
      router.push('/login')
    } catch (error) {
      // 用户取消
    }
  }
}

onMounted(() => {
  fetchStatus()
  statusTimer = setInterval(fetchStatus, 30000)
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
})
</script>

<style>
/* Global Reset */
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.layout-container {
  height: 100vh;
}

/* Sidebar */
.aside {
  background-color: #001529;
  color: white;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  box-shadow: 2px 0 6px rgba(0,21,41,0.35);
  z-index: 10;
}

.logo-container {
  height: 64px;
  display: flex;
  align-items: center;
  padding-left: 20px;
  background-color: #002140;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo-icon {
  color: #409eff;
  font-size: 24px;
  margin-right: 10px;
  display: flex;
  align-items: center;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: white;
  letter-spacing: 0.5px;
}

.el-menu-vertical {
  border-right: none !important;
  flex: 1;
}

.version-info {
  padding: 16px;
  text-align: center;
  color: #5d6b77;
  font-size: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

/* Header */
.header {
  background-color: #fff;
  height: 64px !important;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px !important;
  box-shadow: 0 1px 4px rgba(0,21,41,0.08);
  z-index: 9;
}

.status-indicator {
  display: flex;
  align-items: center;
  margin-right: 20px;
  padding: 6px 12px;
  border-radius: 16px;
  background-color: #f5f5f5;
  transition: all 0.3s;
}

.status-indicator.active {
  background-color: #f0f9eb;
  color: #67c23a;
}

.status-indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #909399;
  margin-right: 8px;
}

.status-indicator.active .dot {
  background-color: #67c23a;
  box-shadow: 0 0 0 2px rgba(103, 194, 58, 0.2);
}

.status-indicator .text {
  font-size: 13px;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 12px;
  border-radius: 20px;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: #f5f7fa;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.user-avatar {
  cursor: pointer;
  background-color: #409eff;
}

.user-type-tag {
  padding: 8px 0;
  text-align: center;
}

/* Main Content */
.main-content {
  background-color: #f0f2f5;
  padding: 24px !important;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
