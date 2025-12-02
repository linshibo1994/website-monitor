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
        <el-button type="primary" size="small" :icon="Plus" @click="openAddDialog">
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

    <!-- 添加商品对话框（智能解析版 + 手动兜底） -->
    <el-dialog v-model="showAddDialog" title="添加监控商品" width="600px" @close="handleDialogClose">
      <el-form :model="newProduct" label-width="100px">
        <!-- 智能输入框 -->
        <el-form-item label="商品URL/Key" required>
          <el-input
            v-model="newProduct.input"
            placeholder="粘贴商品URL 或 输入商品Key"
            @input="debounceParseInput"
            clearable
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <div class="input-tips">
            <span>支持: Arc'teryx URL/Key (如 beta-sl-jacket-9685), SCHEELS URL/Key (如 62355529822)</span>
          </div>
        </el-form-item>

        <!-- 解析结果展示 -->
        <el-form-item v-if="parseResult.success || parseResult.error">
          <div class="parse-result" :class="{ success: parseResult.success, error: !parseResult.success }">
            <template v-if="parseResult.success">
              <div class="parse-info">
                <el-icon><SuccessFilled /></el-icon>
                <span class="parse-label">识别成功</span>
              </div>
              <div class="parse-details">
                <div class="detail-item">
                  <span class="label">站点:</span>
                  <el-tag size="small" type="primary">{{ parseResult.site_name }}</el-tag>
                </div>
                <div class="detail-item">
                  <span class="label">Key:</span>
                  <code>{{ parseResult.key }}</code>
                </div>
                <div class="detail-item" v-if="parseResult.categories && parseResult.categories.length > 0">
                  <span class="label">分类:</span>
                  <el-select v-model="newProduct.category" size="small" style="width: 120px" @change="updatePreviewUrl">
                    <el-option
                      v-for="cat in parseResult.categories"
                      :key="cat.value"
                      :label="cat.label"
                      :value="cat.value"
                    />
                  </el-select>
                </div>
              </div>
              <div class="preview-url">
                <span class="label">预览URL:</span>
                <el-link :href="previewUrl" target="_blank" type="primary" :underline="false">
                  {{ previewUrl }}
                </el-link>
              </div>
            </template>
            <template v-else>
              <div class="parse-info">
                <el-icon><WarningFilled /></el-icon>
                <span class="parse-label">识别失败</span>
              </div>
              <div class="error-message">{{ parseResult.error }}</div>
              <!-- 手动兜底：当自动解析失败时，显示手动选择选项 -->
              <div class="manual-fallback" v-if="availableSites.length > 0">
                <el-divider content-position="left">手动指定</el-divider>
                <div class="manual-inputs">
                  <el-select v-model="manualInput.site_id" placeholder="选择站点" size="small" style="width: 150px" @change="onManualSiteChange">
                    <el-option
                      v-for="site in availableSites"
                      :key="site.site_id"
                      :label="site.name"
                      :value="site.site_id"
                    />
                  </el-select>
                  <el-input v-model="manualInput.key" placeholder="输入商品Key" size="small" style="width: 200px; margin-left: 10px" />
                  <el-select
                    v-if="manualSiteCategories.length > 0"
                    v-model="manualInput.category"
                    placeholder="分类"
                    size="small"
                    style="width: 100px; margin-left: 10px"
                  >
                    <el-option
                      v-for="cat in manualSiteCategories"
                      :key="cat.value"
                      :label="cat.label"
                      :value="cat.value"
                    />
                  </el-select>
                </div>
                <div class="manual-tip">
                  <span v-if="selectedSiteExample">示例 Key: {{ selectedSiteExample }}</span>
                </div>
              </div>
            </template>
          </div>
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

        <el-form-item label="目标颜色">
          <el-select
            v-model="newProduct.target_colors"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入颜色名称 (如 Black, Void)"
            style="width: 100%"
          >
            <el-option label="Black" value="Black" />
            <el-option label="Void" value="Void" />
            <el-option label="Black Sapphire" value="Black Sapphire" />
          </el-select>
          <div class="form-tip">留空则监控所有颜色，可手动输入颜色名称</div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button
          type="primary"
          @click="addProduct"
          :loading="adding"
          :disabled="!canSubmit"
        >
          添加监控
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Monitor, VideoPlay, VideoPause, Clock, Goods, Plus, Delete,
  Check, Close, Link, Refresh, Search, SuccessFilled, WarningFilled
} from '@element-plus/icons-vue'
import {
  getInventoryStatus,
  triggerInventoryCheck,
  startInventoryScheduler,
  stopInventoryScheduler,
  addInventoryProduct,
  removeInventoryProduct,
  parseProductInput,
  getInventorySites
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

// 可用站点列表（从API获取）
const availableSites = ref([])

// 解析结果
const parseResult = ref({
  success: false,
  site_id: null,
  site_name: null,
  key: null,
  category: null,
  url: null,
  error: null,
  categories: null
})

// 预览URL（使用后端返回的URL或根据分类切换构建）
const previewUrl = ref('')

// 新商品表单
const newProduct = ref({
  input: '',
  name: '',
  category: '',
  target_sizes: [],
  target_colors: []
})

// 手动输入（兜底模式）
const manualInput = ref({
  site_id: '',
  key: '',
  category: ''
})

// 定时刷新
let refreshTimer = null
let parseDebounceTimer = null
let parseRequestId = 0  // 用于避免旧请求覆盖新输入

// 计算手动选择的站点分类
const manualSiteCategories = computed(() => {
  if (!manualInput.value.site_id) return []
  const site = availableSites.value.find(s => s.site_id === manualInput.value.site_id)
  return site?.categories || []
})

// 计算选中站点的Key示例
const selectedSiteExample = computed(() => {
  if (!manualInput.value.site_id) return ''
  const site = availableSites.value.find(s => s.site_id === manualInput.value.site_id)
  return site?.key_example || ''
})

// 计算是否可以提交
const canSubmit = computed(() => {
  // 自动解析成功
  if (parseResult.value.success) return true
  // 手动模式：需要站点和Key
  if (manualInput.value.site_id && manualInput.value.key) return true
  // 至少有输入（让后端尝试解析）
  if (newProduct.value.input.trim()) return true
  return false
})

// 打开添加对话框
const openAddDialog = async () => {
  resetForm()
  showAddDialog.value = true
  // 加载可用站点列表
  await loadAvailableSites()
}

// 关闭对话框时清理
const handleDialogClose = () => {
  // 清理防抖定时器
  if (parseDebounceTimer) {
    clearTimeout(parseDebounceTimer)
    parseDebounceTimer = null
  }
  // 增加请求ID，使旧请求失效
  parseRequestId++
}

// 加载可用站点列表
const loadAvailableSites = async () => {
  try {
    const response = await getInventorySites()
    availableSites.value = response.data.sites || []
  } catch (error) {
    console.error('获取站点列表失败:', error)
  }
}

// 重置表单
const resetForm = () => {
  newProduct.value = {
    input: '',
    name: '',
    category: '',
    target_sizes: [],
    target_colors: []
  }
  parseResult.value = {
    success: false,
    site_id: null,
    site_name: null,
    key: null,
    category: null,
    url: null,
    error: null,
    categories: null
  }
  manualInput.value = {
    site_id: '',
    key: '',
    category: ''
  }
  previewUrl.value = ''
}

// 智能解析输入（带防抖和请求序号）
const debounceParseInput = () => {
  if (parseDebounceTimer) {
    clearTimeout(parseDebounceTimer)
  }

  parseDebounceTimer = setTimeout(async () => {
    await parseInput()
  }, 300)
}

// 解析输入
const parseInput = async () => {
  const input = newProduct.value.input.trim()
  const currentRequestId = ++parseRequestId

  if (!input) {
    parseResult.value = {
      success: false,
      site_id: null,
      site_name: null,
      key: null,
      category: null,
      url: null,
      error: null,
      categories: null
    }
    previewUrl.value = ''
    return
  }

  try {
    const response = await parseProductInput(input)

    // 检查是否是最新请求，避免旧响应覆盖新输入
    if (currentRequestId !== parseRequestId) {
      return
    }

    parseResult.value = response.data

    // 如果解析成功，设置默认分类和预览URL
    if (parseResult.value.success) {
      if (parseResult.value.category) {
        newProduct.value.category = parseResult.value.category
      }
      previewUrl.value = parseResult.value.url || ''
    }
  } catch (error) {
    // 检查是否是最新请求
    if (currentRequestId !== parseRequestId) {
      return
    }

    parseResult.value = {
      success: false,
      error: error.response?.data?.detail || '解析失败'
    }
  }
}

// 当分类切换时更新预览URL
const updatePreviewUrl = () => {
  if (!parseResult.value.success) return

  const site = availableSites.value.find(s => s.site_id === parseResult.value.site_id)
  if (!site || !site.url_templates) {
    previewUrl.value = parseResult.value.url || ''
    return
  }

  const category = newProduct.value.category || parseResult.value.category
  const template = site.url_templates[category] || site.url_templates['default'] || ''
  if (template && parseResult.value.key) {
    previewUrl.value = template.replace('{key}', parseResult.value.key)
  } else {
    previewUrl.value = parseResult.value.url || ''
  }
}

// 手动站点切换时设置默认分类
const onManualSiteChange = () => {
  const site = availableSites.value.find(s => s.site_id === manualInput.value.site_id)
  if (site) {
    manualInput.value.category = site.default_category || ''
  }
}

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

// 等待检查完成的辅助函数（轮询状态）
const waitForCheckComplete = async (maxWaitSeconds = 90) => {
  const startTime = Date.now()
  const pollInterval = 5000 // 5秒轮询一次

  while ((Date.now() - startTime) < maxWaitSeconds * 1000) {
    await new Promise(resolve => setTimeout(resolve, pollInterval))
    await fetchStatus()

    // 检查是否可以触发新检查（不真正触发，只是试探）
    try {
      // 尝试触发检查来测试是否有检查在进行
      await triggerInventoryCheck()
      // 如果成功，说明之前的检查已完成，这次触发的检查也会更新数据
      return true
    } catch (error) {
      if (error.response?.status === 409) {
        // 仍在检查中，继续等待
        console.log('检查进行中，等待...')
        continue
      }
      // 其他错误，停止等待
      return false
    }
  }
  return false
}

// 添加商品
const addProduct = async () => {
  adding.value = true
  try {
    let data = {}

    // 优先使用自动解析成功的结果
    if (parseResult.value.success) {
      data = {
        input: newProduct.value.input,
        name: newProduct.value.name,
        category: newProduct.value.category,
        target_sizes: newProduct.value.target_sizes,
        target_colors: newProduct.value.target_colors
      }
    }
    // 其次使用手动输入（显式模式）
    else if (manualInput.value.site_id && manualInput.value.key) {
      data = {
        site_id: manualInput.value.site_id,
        key: manualInput.value.key,
        category: manualInput.value.category,
        name: newProduct.value.name,
        target_sizes: newProduct.value.target_sizes,
        target_colors: newProduct.value.target_colors
      }
    }
    // 最后尝试让后端解析
    else if (newProduct.value.input.trim()) {
      data = {
        input: newProduct.value.input,
        name: newProduct.value.name,
        target_sizes: newProduct.value.target_sizes,
        target_colors: newProduct.value.target_colors
      }
    } else {
      ElMessage.warning('请输入商品URL或Key')
      adding.value = false
      return
    }

    await addInventoryProduct(data)
    ElMessage.success('商品添加成功，正在获取商品信息...')
    showAddDialog.value = false
    resetForm()

    // 添加商品后，自动触发一次检查以获取商品名称和库存信息
    try {
      await triggerInventoryCheck()
      ElMessage.success('商品信息已更新')
    } catch (error) {
      // 如果返回 409 冲突，说明有其他检查在进行，等待完成后刷新
      if (error.response?.status === 409) {
        ElMessage.info('有检查任务正在进行，等待完成...')
        await waitForCheckComplete(60)
        ElMessage.success('商品信息已更新')
      } else {
        console.error('自动检查失败:', error)
      }
    }

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
  // 清理定时器
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (parseDebounceTimer) {
    clearTimeout(parseDebounceTimer)
    parseDebounceTimer = null
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

/* 智能解析相关样式 */
.input-tips {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.parse-result {
  padding: 15px;
  border-radius: 8px;
  width: 100%;
}

.parse-result.success {
  background: linear-gradient(135deg, #f0f9eb 0%, #e1f3d8 100%);
  border: 1px solid #b3e19d;
}

.parse-result.error {
  background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
  border: 1px solid #fab6b6;
}

.parse-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.parse-result.success .parse-info {
  color: #67c23a;
}

.parse-result.error .parse-info {
  color: #f56c6c;
}

.parse-info .el-icon {
  font-size: 20px;
}

.parse-label {
  font-weight: bold;
  font-size: 14px;
}

.parse-details {
  display: flex;
  flex-wrap: wrap;
  gap: 15px;
  margin-bottom: 10px;
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-item .label {
  color: #606266;
  font-size: 13px;
}

.detail-item code {
  background: #f5f7fa;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: monospace;
  color: #409eff;
}

.preview-url {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px dashed #dcdfe6;
}

.preview-url .label {
  color: #606266;
  font-size: 13px;
  white-space: nowrap;
}

.preview-url .el-link {
  word-break: break-all;
  font-size: 12px;
}

.error-message {
  color: #f56c6c;
  font-size: 13px;
  white-space: pre-line;
  margin-bottom: 10px;
}

/* 手动兜底样式 */
.manual-fallback {
  margin-top: 10px;
}

.manual-fallback .el-divider {
  margin: 15px 0 10px 0;
}

.manual-inputs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}

.manual-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}
</style>
