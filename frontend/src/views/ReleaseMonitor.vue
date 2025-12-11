<template>
  <div class="release-monitor-view">
    <!-- Overview Cards -->
    <el-row :gutter="20" class="overview-row">
      <el-col :span="6">
        <div class="stat-card">
          <div class="icon-wrapper bg-blue">
            <el-icon><Bell /></el-icon>
          </div>
          <div class="content">
            <div class="value">{{ status.total }}</div>
            <div class="label">监控商品</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="icon-wrapper bg-orange">
            <el-icon><Clock /></el-icon>
          </div>
          <div class="content">
            <div class="value">{{ status.coming_soon }}</div>
            <div class="label">即将上线</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="icon-wrapper bg-green">
            <el-icon><Check /></el-icon>
          </div>
          <div class="content">
            <div class="value">{{ status.available }}</div>
            <div class="label">已上线</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6" class="actions-col">
        <el-button
          type="primary"
          :loading="checking"
          @click="triggerCheck"
          :icon="Refresh"
          class="action-btn"
        >
          立即检测
        </el-button>
      </el-col>
    </el-row>

    <!-- Main Table Card -->
    <el-card class="table-card" shadow="never">
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <el-icon><List /></el-icon>
            <span>上线监控列表</span>
          </div>
          <el-button type="primary" :icon="Plus" @click="openAddDialog">
            添加商品
          </el-button>
        </div>
      </template>

      <el-table
        :data="status.products"
        style="width: 100%"
        v-loading="loading"
        row-key="id"
      >
        <el-table-column prop="name" label="商品名称" min-width="200">
          <template #default="{ row }">
            <div class="product-name-cell">
              <span class="name-text">{{ row.name || '正在获取...' }}</span>
              <el-tag size="small" effect="plain" type="info">{{ getWebsiteTag(row.website_type) }}</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" effect="light">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="scheduled_release_time" label="预计上线" width="180">
          <template #default="{ row }">
            <span v-if="row.scheduled_release_time" class="release-time">
              <el-icon><Clock /></el-icon>
              {{ row.scheduled_release_time }}
            </span>
            <span v-else class="text-gray">未知</span>
          </template>
        </el-table-column>

        <el-table-column prop="notification_sent" label="通知" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.notification_sent" type="success" size="small" effect="plain">
              <el-icon><Bell /></el-icon> 已发送
            </el-tag>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>

        <el-table-column label="最后检测" width="160">
          <template #default="{ row }">
            <span class="text-gray">{{ formatTime(row.last_check_time) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" align="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button link type="primary" :icon="Link" @click="openLink(row.url)">访问</el-button>
              <el-button link type="primary" :icon="Refresh" @click="checkSingleProduct(row)" :loading="row._checking">检测</el-button>
              <el-button link type="danger" :icon="Delete" @click="removeProduct(row)">移除</el-button>
            </el-button-group>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无监控商品" />
        </template>
      </el-table>
    </el-card>

    <!-- Add Product Dialog -->
    <el-dialog v-model="showAddDialog" title="添加上线监控商品" width="550px" @close="handleDialogClose" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="商品链接 (URL)">
          <el-input
            v-model="newProduct.url"
            placeholder="输入 Daytona Park 或 Rakuten 商品链接"
            :prefix-icon="Search"
            @input="debounceParseInput"
            clearable
          />
          <div class="tip-text">支持 Daytona Park 和 Rakuten 日本网站</div>
        </el-form-item>

        <div v-if="parseResult.success" class="parse-success-card">
          <div class="header">
            <el-icon><CircleCheckFilled /></el-icon> 识别成功
          </div>
          <div class="info-grid">
            <div class="item"><span class="label">网站:</span> {{ parseResult.website_name }}</div>
            <div class="item"><span class="label">商品ID:</span> {{ parseResult.product_id || '未知' }}</div>
          </div>
        </div>
        <div v-else-if="parseResult.error" class="parse-error-msg">
          {{ parseResult.error }}
        </div>

        <el-form-item label="商品名称（可选）">
          <el-input v-model="newProduct.name" placeholder="默认自动获取" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addProduct" :loading="adding" :disabled="!canSubmit">
          开始监控
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Bell, Clock, Check, Refresh, Plus, List, Link, Delete, Search, CircleCheckFilled
} from '@element-plus/icons-vue'
import {
  getReleaseStatus,
  triggerReleaseCheck,
  addReleaseProduct,
  removeReleaseProduct,
  parseReleaseUrl,
  checkSingleReleaseProduct
} from '@/api'

const status = ref({
  total: 0,
  active: 0,
  coming_soon: 0,
  available: 0,
  unavailable: 0,
  error: 0,
  notified: 0,
  products: []
})

const loading = ref(false)
const checking = ref(false)
const adding = ref(false)
const showAddDialog = ref(false)
let refreshTimer = null
let parseTimer = null

// Add Product Form
const newProduct = ref({
  url: '',
  name: ''
})

const parseResult = ref({ success: false, error: null })

const canSubmit = computed(() => {
  return parseResult.value.success || (newProduct.value.url && !parseResult.value.error)
})

// Methods
const fetchStatus = async () => {
  try {
    const res = await getReleaseStatus()
    status.value = res.data
  } catch (err) {
    console.error(err)
    ElMessage.error('获取监控状态失败')
  }
}

const triggerCheck = async () => {
  checking.value = true
  try {
    const res = await triggerReleaseCheck()
    ElMessage.success(`检测完成: ${res.data.available} 个已上线, ${res.data.coming_soon} 个待上线`)
    await fetchStatus()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '检测失败')
  } finally {
    checking.value = false
  }
}

const checkSingleProduct = async (row) => {
  row._checking = true
  try {
    await checkSingleReleaseProduct(row.id)
    ElMessage.success('检测完成')
    await fetchStatus()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '检测失败')
  } finally {
    row._checking = false
  }
}

// Parsing
const debounceParseInput = () => {
  if (parseTimer) clearTimeout(parseTimer)
  parseTimer = setTimeout(parseInput, 500)
}

const parseInput = async () => {
  const url = newProduct.value.url.trim()
  if (!url) {
    parseResult.value = { success: false, error: null }
    return
  }

  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    parseResult.value = { success: false, error: '请输入完整的URL (http:// 或 https://)' }
    return
  }

  try {
    const res = await parseReleaseUrl(url)
    parseResult.value = res.data
  } catch (err) {
    parseResult.value = { success: false, error: err.response?.data?.detail || '无法解析' }
  }
}

const addProduct = async () => {
  adding.value = true
  try {
    await addReleaseProduct({
      url: newProduct.value.url,
      name: newProduct.value.name || null
    })
    ElMessage.success('添加成功')
    showAddDialog.value = false
    await fetchStatus()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '添加失败')
  } finally {
    adding.value = false
  }
}

const removeProduct = async (row) => {
  try {
    await ElMessageBox.confirm('确定移除该商品的上线监控吗?', '警告', { type: 'warning' })
    await removeReleaseProduct(row.id)
    ElMessage.success('已移除')
    fetchStatus()
  } catch (e) {
    // 只有非取消操作时才显示错误
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('移除失败')
    }
  }
}

const openLink = (url) => window.open(url, '_blank')

// Helpers
const formatTime = (t) => {
  if (!t) return '从未'
  return new Date(t).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const getWebsiteTag = (type) => {
  const map = {
    'daytona_park': 'Daytona Park',
    'rakuten': 'Rakuten'
  }
  return map[type] || type
}

const getStatusType = (s) => ({
  available: 'success',
  coming_soon: 'warning',
  unavailable: 'danger',
  error: 'danger'
}[s] || 'info')

const getStatusText = (s) => ({
  available: '已上线',
  coming_soon: '即将上线',
  unavailable: '不可用',
  error: '错误'
}[s] || s)

const openAddDialog = () => {
  newProduct.value = { url: '', name: '' }
  parseResult.value = { success: false }
  showAddDialog.value = true
}
const handleDialogClose = () => {}

onMounted(() => {
  loading.value = true
  fetchStatus().finally(() => loading.value = false)
  refreshTimer = setInterval(fetchStatus, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.release-monitor-view {
  max-width: 1200px;
  margin: 0 auto;
}

.overview-row {
  margin-bottom: 24px;
}

.stat-card {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  box-shadow: 0 2px 6px rgba(0,0,0,0.04);
  border: 1px solid #ebeef5;
}

.icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: white;
  margin-right: 16px;
}

.bg-blue { background: linear-gradient(135deg, #1890ff, #36cfc9); }
.bg-green { background: linear-gradient(135deg, #52c41a, #95de64); }
.bg-orange { background: linear-gradient(135deg, #fa8c16, #faad14); }

.content .value { font-size: 20px; font-weight: 600; color: #262626; }
.content .label { font-size: 12px; color: #8c8c8c; margin-top: 4px; }

.actions-col {
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-btn {
  width: 100%;
  height: 100%;
}

.table-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.product-name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.name-text { font-weight: 500; color: #1f1f1f; }

.text-gray { color: #909399; font-size: 13px; }

.release-time {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #fa8c16;
}

.tip-text {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

.parse-success-card {
  margin-top: 16px;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  padding: 12px;
  border-radius: 4px;
}

.parse-success-card .header {
  color: #52c41a;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  font-size: 13px;
}

.info-grid .label { color: #8c8c8c; }

.parse-error-msg {
  margin-top: 12px;
  color: #ff4d4f;
  font-size: 13px;
}
</style>
