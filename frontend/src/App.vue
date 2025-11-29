<template>
  <el-container class="app-container">
    <!-- 侧边栏 -->
    <el-aside width="220px" class="app-aside">
      <div class="logo">
        <span class="logo-icon">🏔️</span>
        <span class="logo-text">Arc'teryx 监控</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="app-menu"
        background-color="#1a1a2e"
        text-color="#a0a0a0"
        active-text-color="#409eff"
      >
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/inventory">
          <el-icon><Monitor /></el-icon>
          <span>库存监控</span>
        </el-menu-item>
        <el-menu-item index="/products">
          <el-icon><Goods /></el-icon>
          <span>商品列表</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><Clock /></el-icon>
          <span>历史记录</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag :type="statusType" effect="dark">
            {{ statusText }}
          </el-tag>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getMonitorStatus } from '@/api'

const route = useRoute()

const monitorStatus = ref({
  is_running: false,
  last_total_count: 0
})

const activeMenu = computed(() => route.path)

const currentPageTitle = computed(() => {
  const titles = {
    '/': '仪表盘',
    '/inventory': '库存监控',
    '/products': '商品列表',
    '/history': '历史记录',
    '/settings': '系统设置'
  }
  return titles[route.path] || '未知页面'
})

const statusType = computed(() => monitorStatus.value.is_running ? 'success' : 'info')
const statusText = computed(() => {
  if (monitorStatus.value.is_running) {
    return `运行中 | ${monitorStatus.value.last_total_count} 件商品`
  }
  return '未启动'
})

const fetchStatus = async () => {
  try {
    const res = await getMonitorStatus()
    monitorStatus.value = res.data
  } catch (error) {
    console.error('获取状态失败:', error)
  }
}

onMounted(() => {
  fetchStatus()
  // 每30秒刷新状态
  setInterval(fetchStatus, 30000)
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.app-container {
  height: 100%;
}

.app-aside {
  background: #1a1a2e;
  border-right: 1px solid #2a2a3e;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #2a2a3e;
}

.logo-icon {
  font-size: 24px;
  margin-right: 8px;
}

.logo-text {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}

.app-menu {
  border-right: none;
}

.app-menu .el-menu-item {
  height: 50px;
  line-height: 50px;
}

.app-menu .el-menu-item:hover {
  background-color: #2a2a3e !important;
}

.app-menu .el-menu-item.is-active {
  background-color: #16213e !important;
  border-left: 3px solid #409eff;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.app-main {
  background: #f5f7fa;
  padding: 20px;
  overflow-y: auto;
}
</style>
