<template>
  <el-container class="layout-container">
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
          <el-avatar :size="32" icon="UserFilled" class="user-avatar" />
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
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { Monitor, Odometer, Box, Goods, Timer, Setting, UserFilled } from '@element-plus/icons-vue'
import { getMonitorStatus } from '@/api'

const route = useRoute()
const monitorStatus = ref({ is_running: false })
let statusTimer = null

const activeMenu = computed(() => route.path)

const currentPageTitle = computed(() => {
  const titles = {
    '/': '仪表盘',
    '/inventory': '库存监控',
    '/products': '商品列表',
    '/history': '历史记录',
    '/settings': '系统设置'
  }
  return titles[route.path] || 'Monitor'
})

const fetchStatus = async () => {
  try {
    const res = await getMonitorStatus()
    monitorStatus.value = res.data
  } catch (error) {
    console.error('Failed to fetch status', error)
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
}

.user-avatar {
  cursor: pointer;
  background-color: #409eff;
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
