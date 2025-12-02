<template>
  <div class="dashboard-view">
    <!-- Key Metrics -->
    <el-row :gutter="20" class="mb-4">
      <el-col :span="6">
        <el-card shadow="never" class="metric-card">
          <div class="metric-content">
            <div class="metric-title">监控商品总数</div>
            <div class="metric-value">{{ stats.totalTracked + inventoryStatus.monitored_products }}</div>
            <div class="metric-footer">
              <span>Legacy: {{ stats.totalTracked }}</span>
              <el-divider direction="vertical" />
              <span>Inventory: {{ inventoryStatus.monitored_products }}</span>
            </div>
          </div>
          <div class="metric-icon bg-blue-light">
            <el-icon class="text-blue"><Goods /></el-icon>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="never" class="metric-card">
          <div class="metric-content">
            <div class="metric-title">在售/活跃</div>
            <div class="metric-value">{{ stats.currentActive }}</div>
            <div class="metric-footer text-green">
              <el-icon><Top /></el-icon> 正常运行
            </div>
          </div>
          <div class="metric-icon bg-green-light">
            <el-icon class="text-green"><Shop /></el-icon>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="never" class="metric-card">
          <div class="metric-content">
            <div class="metric-title">监控频率</div>
            <div class="metric-value">{{ status.interval_minutes }} <span class="unit">分钟</span></div>
            <div class="metric-footer">
              <span>下次检测: {{ getNextCheckTime() }}</span>
            </div>
          </div>
          <div class="metric-icon bg-orange-light">
            <el-icon class="text-orange"><Timer /></el-icon>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="never" class="metric-card">
          <div class="metric-content">
            <div class="metric-title">系统状态</div>
            <div class="metric-value" :class="status.is_running ? 'text-green' : 'text-red'">
              {{ status.is_running ? '运行中' : '已停止' }}
            </div>
            <div class="metric-footer">
               Last: {{ formatTime(status.last_check_time).split(' ')[1] }}
            </div>
          </div>
          <div class="metric-icon" :class="status.is_running ? 'bg-green-light' : 'bg-red-light'">
            <el-icon :class="status.is_running ? 'text-green' : 'text-red'">
              <VideoPlay v-if="status.is_running" />
              <VideoPause v-else />
            </el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Main Charts & Logs -->
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span class="title">商品数量趋势</span>
              <el-radio-group v-model="chartDays" size="small" @change="fetchStatistics">
                <el-radio-button :value="7">7天</el-radio-button>
                <el-radio-button :value="30">30天</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="chartRef" class="chart-container"></div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never" class="control-card mb-4">
          <template #header>
            <div class="card-header">
              <span class="title">系统控制</span>
            </div>
          </template>
          <div class="control-grid">
             <el-button type="primary" size="large" :loading="checking" @click="handleTriggerCheck">
               <el-icon class="mr-2"><Refresh /></el-icon> 立即检测
             </el-button>
             <el-button 
               :type="status.is_running ? 'danger' : 'success'" 
               size="large" 
               @click="handleToggleScheduler"
             >
               <el-icon class="mr-2"><SwitchButton /></el-icon> 
               {{ status.is_running ? '停止调度' : '启动调度' }}
             </el-button>
          </div>
        </el-card>

        <el-card shadow="never" class="log-card">
          <template #header>
            <div class="card-header">
              <span class="title">最近变动</span>
              <el-button link type="primary" @click="$router.push('/history')">查看全部</el-button>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="change in recentChanges"
              :key="change.id"
              :timestamp="formatTime(change.check_time)"
              :type="getChangeType(change)"
              size="large"
              :hollow="true"
            >
              <div class="log-content">
                <span v-if="change.added_count > 0" class="text-green">+{{ change.added_count }} 上架</span>
                <span v-if="change.removed_count > 0" class="text-red ml-2">-{{ change.removed_count }} 下架</span>
              </div>
            </el-timeline-item>
            <el-timeline-item v-if="!recentChanges.length">
              <span class="text-gray">暂无近期变动</span>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { Goods, Shop, Timer, VideoPlay, VideoPause, Refresh, SwitchButton, Top } from '@element-plus/icons-vue'
import {
  getMonitorStatus,
  triggerCheck,
  startScheduler,
  stopScheduler,
  getStatistics,
  getRecentChanges,
  getInventoryStatus
} from '@/api'

// State
const chartRef = ref(null)
const chartDays = ref(7)
let chartInstance = null

const status = ref({ is_running: false, last_check_time: null, interval_minutes: 10 })
const inventoryStatus = ref({ monitored_products: 0 })
const stats = ref({ currentActive: 0, totalTracked: 0, trendData: [] })
const recentChanges = ref([])
const checking = ref(false)

// Methods
const fetchAllData = async () => {
  try {
    const [monitorRes, invRes, statRes, recentRes] = await Promise.all([
      getMonitorStatus(),
      getInventoryStatus(),
      getStatistics(chartDays.value),
      getRecentChanges(5)
    ])
    
    status.value = monitorRes.data
    inventoryStatus.value = invRes.data
    stats.value = {
      currentActive: statRes.data.current_active,
      totalTracked: statRes.data.total_tracked,
      trendData: statRes.data.trend_data
    }
    recentChanges.value = recentRes.data.changes || []
    
    updateChart()
  } catch (error) {
    console.error('Data fetch failed', error)
  }
}

const fetchStatistics = async () => {
  try {
    const res = await getStatistics(chartDays.value)
    stats.value.trendData = res.data.trend_data
    updateChart()
  } catch (e) {}
}

const handleTriggerCheck = async () => {
  checking.value = true
  try {
    const res = await triggerCheck()
    if (res.data.success) {
      ElMessage.success(`检测完成: ${res.data.total_count} 件`)
      fetchAllData()
    } else {
      ElMessage.error('检测失败')
    }
  } catch (e) {
    ElMessage.error('请求失败')
  } finally {
    checking.value = false
  }
}

const handleToggleScheduler = async () => {
  try {
    if (status.value.is_running) {
      await stopScheduler()
    } else {
      await startScheduler()
    }
    fetchAllData()
    ElMessage.success(status.value.is_running ? '已停止' : '已启动')
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

// Chart
const initChart = () => {
  if (!chartRef.value) return
  chartInstance = echarts.init(chartRef.value)
  window.addEventListener('resize', () => chartInstance.resize())
}

const updateChart = () => {
  if (!chartInstance) return
  
  const xData = stats.value.trendData.map(d => dayjs(d.time).format('MM-DD'))
  const yData = stats.value.trendData.map(d => d.count)

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: xData },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
    series: [{
      name: '商品数量',
      type: 'line',
      smooth: true,
      symbol: 'none',
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64, 158, 255, 0.2)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0)' }
        ])
      },
      data: yData,
      color: '#409eff'
    }]
  })
}

// Helpers
const formatTime = (t) => t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-'
const getNextCheckTime = () => {
  if (!status.value.last_check_time || !status.value.is_running) return '-'
  return dayjs(status.value.last_check_time).add(status.value.interval_minutes, 'minute').format('HH:mm')
}
const getChangeType = (c) => c.added_count > 0 ? 'success' : 'danger'

onMounted(() => {
  initChart()
  fetchAllData()
  setInterval(fetchAllData, 30000)
})
</script>

<style scoped>
.dashboard-view {
  max-width: 1400px;
  margin: 0 auto;
}

.mb-4 { margin-bottom: 24px; }
.mr-2 { margin-right: 8px; }
.ml-2 { margin-left: 8px; }

/* Metric Cards */
.metric-card {
  border: none;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}
.metric-card :deep(.el-card__body) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
}

.metric-content { flex: 1; }
.metric-title { font-size: 14px; color: #909399; margin-bottom: 8px; }
.metric-value { font-size: 28px; font-weight: 600; color: #303133; line-height: 1.2; }
.metric-value.unit { font-size: 14px; color: #909399; font-weight: normal; }
.metric-footer { margin-top: 8px; font-size: 12px; color: #909399; display: flex; align-items: center; gap: 8px; }

.metric-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

/* Colors */
.text-blue { color: #409eff; }
.bg-blue-light { background-color: #ecf5ff; }
.text-green { color: #67c23a; }
.bg-green-light { background-color: #f0f9eb; }
.text-orange { color: #e6a23c; }
.bg-orange-light { background-color: #fdf6ec; }
.text-red { color: #f56c6c; }
.bg-red-light { background-color: #fef0f0; }
.text-gray { color: #909399; }

/* Control Card */
.control-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.control-grid .el-button { width: 100%; margin: 0; }

/* Chart */
.chart-container { height: 320px; }

/* Card Headers */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title { font-weight: 600; font-size: 16px; }
</style>