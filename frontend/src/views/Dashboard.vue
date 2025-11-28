<template>
  <div class="dashboard">
    <!-- 状态卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
            <el-icon :size="28"><Goods /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.currentActive }}</div>
            <div class="stat-label">在售商品</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
            <el-icon :size="28"><TrendCharts /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.totalTracked }}</div>
            <div class="stat-label">累计追踪</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
            <el-icon :size="28"><Clock /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ status.interval_minutes }}分钟</div>
            <div class="stat-label">检测间隔</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" :style="statusStyle">
            <el-icon :size="28"><CircleCheck v-if="status.is_running" /><CircleClose v-else /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ status.is_running ? '运行中' : '已停止' }}</div>
            <div class="stat-label">监控状态</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作按钮和趋势图 -->
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>商品数量趋势</span>
              <el-radio-group v-model="chartDays" size="small" @change="fetchStatistics">
                <el-radio-button :value="7">7天</el-radio-button>
                <el-radio-button :value="30">30天</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="chartRef" class="trend-chart"></div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="action-card">
          <template #header>
            <span>快捷操作</span>
          </template>
          <div class="action-buttons">
            <el-button type="primary" :loading="checking" @click="handleTriggerCheck" size="large" style="width: 100%;">
              <el-icon><Refresh /></el-icon>
              立即检测
            </el-button>
            <el-button
              :type="status.is_running ? 'danger' : 'success'"
              @click="handleToggleScheduler"
              size="large"
              style="width: 100%; margin-top: 15px;"
            >
              <el-icon><VideoPlay v-if="!status.is_running" /><VideoPause v-else /></el-icon>
              {{ status.is_running ? '停止调度' : '启动调度' }}
            </el-button>
          </div>
          <el-divider />
          <div class="last-check-info">
            <p><strong>最后检测:</strong></p>
            <p>{{ formatTime(status.last_check_time) }}</p>
            <p v-if="lastResult">
              <el-tag :type="lastResult.success ? 'success' : 'danger'" size="small">
                {{ lastResult.success ? '成功' : '失败' }}
              </el-tag>
              <span v-if="lastResult.success" style="margin-left: 8px;">
                共 {{ lastResult.total_count }} 件
              </span>
            </p>
          </div>
        </el-card>

        <el-card class="recent-card" style="margin-top: 20px;">
          <template #header>
            <span>最近变化</span>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="change in recentChanges"
              :key="change.id"
              :timestamp="formatTime(change.check_time)"
              :type="change.added_count > 0 ? 'success' : 'danger'"
              placement="top"
            >
              <span v-if="change.added_count > 0" style="color: #67c23a;">
                +{{ change.added_count }} 新增
              </span>
              <span v-if="change.removed_count > 0" style="color: #f56c6c; margin-left: 8px;">
                -{{ change.removed_count }} 下架
              </span>
            </el-timeline-item>
            <el-timeline-item v-if="recentChanges.length === 0">
              <span style="color: #909399;">暂无变化记录</span>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import {
  getMonitorStatus,
  triggerCheck,
  startScheduler,
  stopScheduler,
  getStatistics,
  getRecentChanges
} from '@/api'

const chartRef = ref(null)
const chartDays = ref(7)
let chartInstance = null

const status = ref({
  is_running: false,
  last_check_time: null,
  interval_minutes: 10,
  last_total_count: 0
})

const stats = ref({
  currentActive: 0,
  totalTracked: 0,
  trendData: []
})

const recentChanges = ref([])
const checking = ref(false)
const lastResult = ref(null)

const statusStyle = computed(() => ({
  background: status.value.is_running
    ? 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'
    : 'linear-gradient(135deg, #eb3349 0%, #f45c43 100%)'
}))

const formatTime = (time) => {
  if (!time) return '暂无'
  return dayjs(time).format('MM-DD HH:mm:ss')
}

const fetchStatus = async () => {
  try {
    const res = await getMonitorStatus()
    status.value = res.data
  } catch (error) {
    console.error('获取状态失败:', error)
  }
}

const fetchStatistics = async () => {
  try {
    const res = await getStatistics(chartDays.value)
    stats.value = {
      currentActive: res.data.current_active,
      totalTracked: res.data.total_tracked,
      trendData: res.data.trend_data
    }
    updateChart()
  } catch (error) {
    console.error('获取统计失败:', error)
  }
}

const fetchRecentChanges = async () => {
  try {
    const res = await getRecentChanges(5)
    recentChanges.value = res.data.changes || []
  } catch (error) {
    console.error('获取最近变化失败:', error)
  }
}

const handleTriggerCheck = async () => {
  checking.value = true
  try {
    const res = await triggerCheck()
    lastResult.value = res.data
    if (res.data.success) {
      ElMessage.success(`检测完成，共 ${res.data.total_count} 件商品`)
      fetchStatus()
      fetchStatistics()
      fetchRecentChanges()
    } else {
      ElMessage.error(res.data.error || '检测失败')
    }
  } catch (error) {
    ElMessage.error('检测失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    checking.value = false
  }
}

const handleToggleScheduler = async () => {
  try {
    if (status.value.is_running) {
      await stopScheduler()
      ElMessage.success('调度器已停止')
    } else {
      await startScheduler()
      ElMessage.success('调度器已启动')
    }
    fetchStatus()
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message))
  }
}

const initChart = () => {
  if (!chartRef.value) return
  chartInstance = echarts.init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chartInstance) return

  const data = stats.value.trendData || []
  const xData = data.map(d => dayjs(d.time).format('MM-DD HH:mm'))
  const yData = data.map(d => d.count)

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params[0]
        return `${p.name}<br/>商品数量: ${p.value}`
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: xData,
      axisLabel: {
        rotate: 45,
        fontSize: 10
      }
    },
    yAxis: {
      type: 'value',
      min: (value) => Math.max(0, value.min - 5)
    },
    series: [{
      name: '商品数量',
      type: 'line',
      smooth: true,
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(102, 126, 234, 0.5)' },
          { offset: 1, color: 'rgba(102, 126, 234, 0.05)' }
        ])
      },
      lineStyle: {
        color: '#667eea',
        width: 2
      },
      itemStyle: {
        color: '#667eea'
      },
      data: yData
    }]
  }

  chartInstance.setOption(option)
}

onMounted(() => {
  fetchStatus()
  fetchStatistics()
  fetchRecentChanges()
  nextTick(initChart)

  // 定时刷新
  setInterval(fetchStatus, 30000)
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

.stat-cards {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 10px;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  width: 100%;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-right: 15px;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 5px;
}

.chart-card {
  height: 450px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.trend-chart {
  height: 350px;
}

.action-card :deep(.el-card__body) {
  padding-top: 15px;
}

.last-check-info {
  font-size: 13px;
  color: #606266;
}

.last-check-info p {
  margin: 8px 0;
}

.recent-card :deep(.el-timeline) {
  padding-left: 5px;
}
</style>
