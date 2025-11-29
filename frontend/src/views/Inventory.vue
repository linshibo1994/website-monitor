<template>
  <div class="inventory-container">
    <!-- 状态卡片 -->
    <el-row :gutter="20" class="status-row">
      <el-col :span="6">
        <el-card class="status-card" shadow="hover">
          <div class="stat-item">
            <el-icon class="stat-icon" :style="{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }">
              <Monitor />
            </el-icon>
            <div class="stat-content">
              <div class="stat-value">{{ status.monitored_products }}</div>
              <div class="stat-label">监控商品数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="status-card" shadow="hover">
          <div class="stat-item">
            <el-icon class="stat-icon" :style="{ background: status.is_running ? 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)' : 'linear-gradient(135deg, #e74c3c 0%, #c0392b 100%)' }">
              <VideoPlay v-if="status.is_running" />
              <VideoPause v-else />
            </el-icon>
            <div class="stat-content">
              <div class="stat-value">{{ status.is_running ? '运行中' : '已停止' }}</div>
              <div class="stat-label">监控状态</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="status-card" shadow="hover">
          <div class="stat-item">
            <el-icon class="stat-icon" :style="{ background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' }">
              <Clock />
            </el-icon>
            <div class="stat-content">
              <div class="stat-value">{{ formatTime(status.last_check_time) }}</div>
              <div class="stat-label">上次检查</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="status-card" shadow="hover">
          <div class="stat-item control-buttons">
            <el-button type="primary" :loading="checking" @click="triggerCheck" :icon="Refresh">
              立即检查
            </el-button>
            <el-button
              :type="status.is_running ? 'danger' : 'success'"
              @click="toggleScheduler"
              :icon="status.is_running ? VideoPause : VideoPlay"
            >
              {{ status.is_running ? '停止监控' : '启动监控' }}
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 商品库存卡片列表 -->
    <div class="products-section">
      <div class="section-header">
        <h3><el-icon><Goods /></el-icon> 商品库存监控</h3>
        <el-button type="primary" size="small" :icon="Plus" @click="showAddDialog = true">
          添加商品
        </el-button>
      </div>

      <el-row :gutter="20">
        <el-col :span="12" v-for="product in status.products" :key="product.url">
          <el-card class="product-card" shadow="hover">
            <template #header>
              <div class="product-header">
                <div class="product-info">
                  <h4 class="product-name">{{ product.name || '未知商品' }}</h4>
                  <div class="product-meta">
                    <el-tag size="small" type="info">{{ getWebsiteTag(product.url) }}</el-tag>
                    <el-tag size="small" :type="getStatusType(product.status)" effect="dark">
                      {{ getStatusText(product.status) }}
                    </el-tag>
                    <span class="target-sizes" v-if="product.target_sizes.length > 0">
                      目标尺码: <el-tag size="small" v-for="size in product.target_sizes" :key="size" type="warning">{{ size }}</el-tag>
                    </span>
                  </div>
                </div>
                <el-button
                  type="danger"
                  size="small"
                  :icon="Delete"
                  circle
                  @click="removeProduct(product.url)"
                />
              </div>
            </template>

            <!-- Coming Soon 状态显示 -->
            <div v-if="product.status === 'coming_soon'" class="coming-soon-notice">
              <el-icon><Clock /></el-icon>
              <span>商品即将上架，正在监控中...</span>
            </div>

            <!-- 库存状态表格 -->
            <el-table v-else :data="product.variants" size="small" stripe>
              <el-table-column prop="size" label="尺码" width="100" align="center">
                <template #default="{ row }">
                  <el-tag
                    :type="isTargetSize(row.size, product.target_sizes) ? 'warning' : 'info'"
                    size="small"
                  >
                    {{ row.size }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="stock_status" label="库存状态" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.is_available ? 'success' : 'danger'" effect="dark">
                    <el-icon v-if="row.is_available"><Check /></el-icon>
                    <el-icon v-else><Close /></el-icon>
                    {{ row.is_available ? '有货' : '缺货' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>

            <div class="product-footer">
              <div class="check-time" v-if="product.last_check_time">
                <el-icon><Clock /></el-icon>
                检查时间: {{ formatTime(product.last_check_time) }}
              </div>
              <el-link :href="product.url" target="_blank" type="primary">
                <el-icon><Link /></el-icon> 查看商品
              </el-link>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 空状态 -->
      <el-empty v-if="status.products.length === 0" description="暂无监控商品，请添加商品开始监控" />
    </div>

    <!-- 添加商品对话框 -->
    <el-dialog v-model="showAddDialog" title="添加监控商品" width="500px">
      <el-form :model="newProduct" label-width="100px">
        <el-form-item label="商品URL" required>
          <el-input v-model="newProduct.url" placeholder="请输入商品页面URL" />
        </el-form-item>
        <el-form-item label="商品名称">
          <el-input v-model="newProduct.name" placeholder="可选，留空则自动获取" />
        </el-form-item>
        <el-form-item label="目标尺码">
          <el-select v-model="newProduct.target_sizes" multiple placeholder="选择要监控的尺码" style="width: 100%">
            <el-option label="XS" value="XS" />
            <el-option label="S" value="S" />
            <el-option label="M" value="M" />
            <el-option label="L" value="L" />
            <el-option label="XL" value="XL" />
            <el-option label="2XL" value="2XL" />
            <el-option label="XXL" value="XXL" />
          </el-select>
          <div class="form-tip">留空则监控所有尺码</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addProduct" :loading="adding">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Monitor, VideoPlay, VideoPause, Clock, Goods, Plus, Delete,
  Check, Close, Link, Refresh
} from '@element-plus/icons-vue'
import {
  getInventoryStatus,
  triggerInventoryCheck,
  startInventoryScheduler,
  stopInventoryScheduler,
  addInventoryProduct,
  removeInventoryProduct
} from '@/api'

// 状态数据
const status = ref({
  is_running: false,
  last_check_time: null,
  monitored_products: 0,
  products: []
})

// 加载状态
const checking = ref(false)
const adding = ref(false)
const showAddDialog = ref(false)

// 新商品表单
const newProduct = ref({
  url: '',
  name: '',
  target_sizes: []
})

// 定时刷新
let refreshTimer = null

// 获取状态
const fetchStatus = async () => {
  try {
    const response = await getInventoryStatus()
    status.value = response.data
  } catch (error) {
    console.error('获取库存监控状态失败:', error)
  }
}

// 触发检查
const triggerCheck = async () => {
  checking.value = true
  try {
    const response = await triggerInventoryCheck()
    ElMessage.success(`检查完成: ${response.data.products_checked} 个商品, ${response.data.changes_detected} 个变化`)
    await fetchStatus()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '检查失败')
  } finally {
    checking.value = false
  }
}

// 切换调度器
const toggleScheduler = async () => {
  try {
    if (status.value.is_running) {
      await stopInventoryScheduler()
      ElMessage.success('库存监控已停止')
    } else {
      await startInventoryScheduler()
      ElMessage.success('库存监控已启动')
    }
    await fetchStatus()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

// 添加商品
const addProduct = async () => {
  if (!newProduct.value.url) {
    ElMessage.warning('请输入商品URL')
    return
  }

  adding.value = true
  try {
    await addInventoryProduct(newProduct.value)
    ElMessage.success('商品添加成功')
    showAddDialog.value = false
    newProduct.value = { url: '', name: '', target_sizes: [] }
    await fetchStatus()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加失败')
  } finally {
    adding.value = false
  }
}

// 移除商品
const removeProduct = async (url) => {
  try {
    await ElMessageBox.confirm('确定要移除该商品的监控吗？', '确认', {
      type: 'warning'
    })
    await removeInventoryProduct(url)
    ElMessage.success('商品已移除')
    await fetchStatus()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '移除失败')
    }
  }
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return '从未'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN')
}

// 获取网站标签
const getWebsiteTag = (url) => {
  if (url.includes('scheels.com')) return 'Scheels'
  if (url.includes('arcteryx.com')) return "Arc'teryx官网"
  return '其他'
}

// 判断是否是目标尺码
const isTargetSize = (size, targetSizes) => {
  if (!targetSizes || targetSizes.length === 0) return false
  return targetSizes.includes(size)
}

// 获取状态类型（用于标签颜色）
const getStatusType = (status) => {
  switch (status) {
    case 'available': return 'success'
    case 'coming_soon': return 'warning'
    case 'unavailable': return 'danger'
    default: return 'info'
  }
}

// 获取状态文本
const getStatusText = (status) => {
  switch (status) {
    case 'available': return '已上架'
    case 'coming_soon': return '即将上架'
    case 'unavailable': return '已下架'
    default: return '未知'
  }
}

onMounted(() => {
  fetchStatus()
  // 每30秒刷新一次
  refreshTimer = setInterval(fetchStatus, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.inventory-container {
  padding: 20px;
}

.status-row {
  margin-bottom: 20px;
}

.status-card {
  height: 100%;
}

.stat-item {
  display: flex;
  align-items: center;
  padding: 10px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: white;
  margin-right: 15px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.control-buttons {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
}

.control-buttons .el-button {
  width: 100%;
}

.products-section {
  margin-top: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h3 {
  margin: 0;
  font-size: 18px;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}

.product-card {
  margin-bottom: 20px;
}

.product-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.product-info {
  flex: 1;
}

.product-name {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #303133;
}

.product-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.target-sizes {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 5px;
}

.product-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ebeef5;
}

.check-time {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 5px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.coming-soon-notice {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 30px 20px;
  background: linear-gradient(135deg, #fff3cd 0%, #ffeeba 100%);
  border-radius: 8px;
  color: #856404;
  font-size: 16px;
  font-weight: 500;
}

.coming-soon-notice .el-icon {
  font-size: 24px;
}
</style>
