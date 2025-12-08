<template>
  <div class="inventory-view">
    <!-- Overview Cards -->
    <el-row :gutter="20" class="overview-row">
      <el-col :span="6">
        <div class="stat-card">
          <div class="icon-wrapper bg-blue">
            <el-icon><Box /></el-icon>
          </div>
          <div class="content">
            <div class="value">{{ status.monitored_products }}</div>
            <div class="label">监控商品</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="icon-wrapper" :class="status.is_running ? 'bg-green' : 'bg-red'">
            <el-icon v-if="status.is_running"><VideoPlay /></el-icon>
            <el-icon v-else><VideoPause /></el-icon>
          </div>
          <div class="content">
            <div class="value">{{ status.is_running ? '运行中' : '已停止' }}</div>
            <div class="label">监控状态</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="icon-wrapper bg-purple">
            <el-icon><Timer /></el-icon>
          </div>
          <div class="content">
            <div class="value">{{ formatTime(status.last_check_time) }}</div>
            <div class="label">上次检查</div>
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
          立即检查
        </el-button>
        <el-button
          :type="status.is_running ? 'danger' : 'success'"
          @click="toggleScheduler"
          :icon="status.is_running ? VideoPause : VideoPlay"
          class="action-btn"
          plain
        >
          {{ status.is_running ? '停止' : '启动' }}
        </el-button>
      </el-col>
    </el-row>

    <!-- Main Table Card -->
    <el-card class="table-card" shadow="never">
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <el-icon><List /></el-icon>
            <span>监控列表</span>
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
        row-key="url"
      >
        <el-table-column type="expand">
          <template #default="props">
            <div class="variants-container">
              <div v-if="props.row.status === 'coming_soon'" class="coming-soon-alert">
                <el-alert
                  title="商品即将上架"
                  type="warning"
                  description="该商品目前标记为即将上架，正在持续监控中。"
                  show-icon
                  :closable="false"
                />
              </div>
              <el-table v-else :data="getFilteredVariants(props.row)" size="small" border>
                <el-table-column prop="size" label="尺码" width="120" align="center">
                  <template #default="{ row }">
                    <el-tag :type="isTargetSize(row.size, props.row.target_sizes) ? 'warning' : 'info'" size="small">
                      {{ row.size }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="color_name" label="颜色" width="180" show-overflow-tooltip />
                <el-table-column prop="stock_status" label="库存状态" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.is_available ? 'success' : 'danger'" effect="dark" size="small">
                      {{ row.is_available ? '有货' : '缺货' }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="商品名称" min-width="200">
          <template #default="{ row }">
            <div class="product-name-cell">
              <span class="name-text">{{ row.name || '正在获取...' }}</span>
              <el-tag size="small" effect="plain" type="info">{{ getWebsiteTag(row.url) }}</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="目标" width="200">
          <template #default="{ row }">
             <div class="tags-wrapper">
               <el-tag v-for="size in row.target_sizes" :key="size" size="small" type="warning" effect="plain">{{ size }}</el-tag>
               <span v-if="!row.target_sizes.length" class="text-gray">全尺码</span>
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

        <el-table-column label="最后更新" width="180">
          <template #default="{ row }">
            <span class="text-gray">{{ formatTime(row.last_check_time) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150" align="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button link type="primary" :icon="Link" @click="openLink(row.url)">访问</el-button>
              <el-button link type="danger" :icon="Delete" @click="removeProduct(row.url)">移除</el-button>
            </el-button-group>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无监控商品" />
        </template>
      </el-table>
    </el-card>

    <!-- Add Product Dialog -->
    <el-dialog v-model="showAddDialog" title="添加监控商品" width="600px" @close="handleDialogClose" destroy-on-close>
      <el-tabs v-model="addMode" class="add-tabs">
        <el-tab-pane label="智能解析" name="smart">
          <div class="tab-content">
            <el-input
              v-model="newProduct.input"
              placeholder="粘贴商品链接或输入 Key (例如: beta-lt-jacket)"
              :prefix-icon="Search"
              @input="debounceParseInput"
              clearable
            />
            <div class="tip-text">支持 Arc'teryx 和 Scheels 链接/Key</div>

            <div v-if="parseResult.success" class="parse-success-card">
              <div class="header">
                <el-icon><CircleCheckFilled /></el-icon> 识别成功
              </div>
              <div class="info-grid">
                <div class="item"><span class="label">站点:</span> {{ parseResult.site_name }}</div>
                <div class="item"><span class="label">Key:</span> {{ parseResult.key }}</div>
                <div class="item full" v-if="parseResult.categories?.length">
                  <span class="label">分类:</span>
                  <el-radio-group v-model="newProduct.category" size="small" @change="updatePreviewUrl">
                    <el-radio-button v-for="c in parseResult.categories" :key="c.value" :value="c.value">{{ c.label }}</el-radio-button>
                  </el-radio-group>
                </div>
              </div>
              <div class="preview-link">
                 <el-link :href="previewUrl" target="_blank" type="primary">{{ previewUrl }}</el-link>
              </div>
            </div>
            <div v-else-if="parseResult.error" class="parse-error-msg">
              {{ parseResult.error }}
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="手动填写" name="manual">
           <el-form label-position="top">
             <el-form-item label="商品链接 (URL)">
               <el-input v-model="newProduct.input" placeholder="https://..." />
             </el-form-item>
           </el-form>
        </el-tab-pane>
      </el-tabs>

      <el-divider content-position="center">监控选项</el-divider>

      <el-form label-width="80px">
        <el-form-item label="商品名称">
          <el-input v-model="newProduct.name" placeholder="可选，默认自动获取" />
        </el-form-item>
        <el-form-item label="目标尺码">
          <el-select v-model="newProduct.target_sizes" multiple placeholder="所有尺码" style="width: 100%">
            <el-option v-for="s in ['XS','S','M','L','XL','2XL','XXL']" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标颜色">
          <el-select
            v-model="newProduct.target_colors"
            multiple
            filterable
            allow-create
            default-first-option
            :loading="loadingColors"
            placeholder="所有颜色 (支持手动输入)"
            style="width: 100%"
          >
            <el-option 
              v-for="color in availableColors" 
              :key="color.value" 
              :label="color.label" 
              :value="color.label" 
            />
          </el-select>
          <div v-if="parseResult.success && !loadingColors && availableColors.length === 0" class="color-hint">
            未获取到可选颜色，可手动输入
          </div>
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
  Box, VideoPlay, VideoPause, Timer, Refresh, Plus, List, Link, Delete, Search, CircleCheckFilled 
} from '@element-plus/icons-vue'
import {
  getInventoryStatus,
  triggerInventoryCheck,
  startInventoryScheduler,
  stopInventoryScheduler,
  addInventoryProduct,
  removeInventoryProduct,
  parseProductInput,
  getProductColors
} from '@/api'

const status = ref({
  is_running: false,
  last_check_time: null,
  monitored_products: 0,
  products: []
})

const loading = ref(false)
const checking = ref(false)
const adding = ref(false)
const showAddDialog = ref(false)
const addMode = ref('smart')
const availableColors = ref([])
const loadingColors = ref(false)
let refreshTimer = null

// Add Product Form
const newProduct = ref({
  input: '',
  name: '',
  category: '',
  target_sizes: [],
  target_colors: []
})

const parseResult = ref({ success: false, error: null })
const previewUrl = ref('')
let parseTimer = null

const canSubmit = computed(() => {
  if (addMode.value === 'manual') return !!newProduct.value.input;
  return parseResult.value.success || (newProduct.value.input && !parseResult.value.error);
})

// Methods
const fetchStatus = async () => {
  try {
    const res = await getInventoryStatus()
    status.value = res.data
  } catch (err) {
    console.error(err)
  }
}

const triggerCheck = async () => {
  checking.value = true
  try {
    const res = await triggerInventoryCheck()
    ElMessage.success(`检查完成: 变动 ${res.data.changes_detected}`)
    await fetchStatus()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '检查失败')
  } finally {
    checking.value = false
  }
}

const toggleScheduler = async () => {
  try {
    if (status.value.is_running) {
      await stopInventoryScheduler()
      ElMessage.success('监控已停止')
    } else {
      await startInventoryScheduler()
      ElMessage.success('监控已启动')
    }
    await fetchStatus()
  } catch (err) {
    ElMessage.error('操作失败')
  }
}

// Parsing
const debounceParseInput = () => {
  if (parseTimer) clearTimeout(parseTimer)
  parseTimer = setTimeout(parseInput, 500)
}

const parseInput = async () => {
  const input = newProduct.value.input.trim()
  availableColors.value = []  // 清空旧颜色数据
  if (!input) {
    parseResult.value = { success: false, error: null }
    return
  }
  
  try {
    const res = await parseProductInput(input)
    parseResult.value = res.data
    if (res.data.success) {
      previewUrl.value = res.data.url
      if (res.data.category) newProduct.value.category = res.data.category
      if (res.data.url) {
        fetchColors(res.data.url)
      }
    }
  } catch (err) {
    parseResult.value = { success: false, error: err.response?.data?.detail || '无法解析' }
  }
}

const fetchColors = async (url) => {
  loadingColors.value = true
  try {
    const res = await getProductColors(url)
    if (res.data.success && res.data.colors) {
      availableColors.value = res.data.colors
    }
  } catch (err) {
    console.error('获取颜色失败:', err)
    // 失败时保持空数组，用户可通过手动输入添加颜色
    availableColors.value = []
  } finally {
    loadingColors.value = false
  }
}

const updatePreviewUrl = () => {
  // Simplified update logic - mostly relies on backend parse response for now
}

const addProduct = async () => {
  adding.value = true
  try {
    await addInventoryProduct({
      input: newProduct.value.input,
      name: newProduct.value.name,
      category: newProduct.value.category,
      target_sizes: newProduct.value.target_sizes,
      target_colors: newProduct.value.target_colors
    })
    ElMessage.success('添加成功')
    showAddDialog.value = false
    // Trigger initial check
    triggerCheck()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '添加失败')
  } finally {
    adding.value = false
  }
}

const removeProduct = async (url) => {
  try {
    await ElMessageBox.confirm('确定移除该商品吗?', '警告', { type: 'warning' })
    await removeInventoryProduct(url)
    ElMessage.success('已移除')
    fetchStatus()
  } catch (e) {}
}

const openLink = (url) => window.open(url, '_blank')

// Helpers
const formatTime = (t) => {
  if (!t) return '从未'
  return new Date(t).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const getWebsiteTag = (url) => {
  if (url.includes('scheels')) return 'Scheels'
  if (url.includes('arcteryx')) return "Arc'teryx"
  return 'Site'
}

const isTargetSize = (size, targets) => {
  if (!targets || !targets.length) return true
  return targets.includes(size)
}

const getFilteredVariants = (row) => {
  // 调试日志
  console.log('[getFilteredVariants] row.target_colors:', row.target_colors)
  console.log('[getFilteredVariants] row.variants count:', row.variants?.length)

  // 防护：variants 为空时返回空数组
  if (!row.variants || !row.variants.length) {
    return []
  }
  // 未设置目标颜色时返回所有变体
  if (!row.target_colors || !row.target_colors.length) {
    console.log('[getFilteredVariants] No target_colors, returning all variants')
    return row.variants
  }
  // 过滤出匹配目标颜色的变体
  const filtered = row.variants.filter(v => v.color_name && row.target_colors.includes(v.color_name))
  console.log('[getFilteredVariants] Filtered count:', filtered.length)
  return filtered
}

const getStatusType = (s) => ({ available: 'success', coming_soon: 'warning', unavailable: 'danger' }[s] || 'info')
const getStatusText = (s) => ({ available: '现货', coming_soon: '即将上架', unavailable: '缺货' }[s] || s)

const openAddDialog = () => {
  newProduct.value = { input: '', name: '', category: '', target_sizes: [], target_colors: [] }
  parseResult.value = { success: false }
  availableColors.value = []
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
.inventory-view {
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
.bg-red { background: linear-gradient(135deg, #ff4d4f, #ff7875); }
.bg-purple { background: linear-gradient(135deg, #722ed1, #b37feb); }

.content .value { font-size: 20px; font-weight: 600; color: #262626; }
.content .label { font-size: 12px; color: #8c8c8c; margin-top: 4px; }

.actions-col {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.action-btn {
  width: 100%;
  height: 100%;
  margin: 0 !important;
  margin-bottom: 10px !important;
}
.action-btn:last-child { margin-bottom: 0 !important; }

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

.tags-wrapper {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.text-gray { color: #909399; font-size: 13px; }

.variants-container {
  padding: 16px;
  background-color: #fafafa;
}

.add-tabs {
  margin-bottom: 20px;
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

.info-grid .item.full { grid-column: span 2; }
.info-grid .label { color: #8c8c8c; }

.parse-error-msg {
  margin-top: 12px;
  color: #ff4d4f;
  font-size: 13px;
}

.color-hint {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}
</style>
