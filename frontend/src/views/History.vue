<template>
  <div class="history-page">
    <!-- 筛选 -->
    <el-card class="filter-card">
      <el-row :gutter="20">
        <el-col :span="8">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            @change="handleSearch"
          />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 历史记录表格 -->
    <el-card class="table-card">
      <el-table
        :data="logs"
        v-loading="loading"
        stripe
        style="width: 100%"
      >
        <el-table-column label="检测时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.check_time) }}
          </template>
        </el-table-column>
        <el-table-column label="商品总数" width="120">
          <template #default="{ row }">
            <span class="total-count">{{ row.total_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="变化" width="150">
          <template #default="{ row }">
            <div class="change-info">
              <span v-if="row.added_count > 0" class="added">
                +{{ row.added_count }}
              </span>
              <span v-if="row.removed_count > 0" class="removed">
                -{{ row.removed_count }}
              </span>
              <span v-if="row.added_count === 0 && row.removed_count === 0" class="no-change">
                无变化
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="detection_method" label="检测方法" width="150">
          <template #default="{ row }">
            <el-tag size="small">{{ row.detection_method || '未知' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="100">
          <template #default="{ row }">
            {{ row.duration_seconds?.toFixed(2) || '-' }}秒
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              @click="viewDetail(row)"
              :disabled="row.added_count === 0 && row.removed_count === 0"
            >
              <el-icon><View /></el-icon>
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="dialogVisible" title="变化详情" width="700px">
      <div v-if="currentDetail" v-loading="detailLoading">
        <el-descriptions :column="2" border style="margin-bottom: 20px;">
          <el-descriptions-item label="检测时间">{{ formatDate(currentDetail.check_time) }}</el-descriptions-item>
          <el-descriptions-item label="商品总数">{{ currentDetail.total_count }}</el-descriptions-item>
          <el-descriptions-item label="新增数量">
            <span class="added">+{{ currentDetail.added_count }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="下架数量">
            <span class="removed">-{{ currentDetail.removed_count }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 新增商品列表 -->
        <div v-if="currentDetail.added_products?.length > 0">
          <h4 style="color: #67c23a; margin-bottom: 10px;">
            <el-icon><CirclePlus /></el-icon>
            新增商品 ({{ currentDetail.added_products.length }})
          </h4>
          <el-table :data="currentDetail.added_products" size="small" border>
            <el-table-column prop="product_name" label="商品名称" />
            <el-table-column label="价格" width="100">
              <template #default="{ row }">
                ${{ row.product_price?.toFixed(2) || '未知' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openUrl(row.product_url)">
                  查看
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 下架商品列表 -->
        <div v-if="currentDetail.removed_products?.length > 0" style="margin-top: 20px;">
          <h4 style="color: #f56c6c; margin-bottom: 10px;">
            <el-icon><RemoveFilled /></el-icon>
            下架商品 ({{ currentDetail.removed_products.length }})
          </h4>
          <el-table :data="currentDetail.removed_products" size="small" border>
            <el-table-column prop="product_name" label="商品名称" />
            <el-table-column label="价格" width="100">
              <template #default="{ row }">
                ${{ row.product_price?.toFixed(2) || '未知' }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import { getHistory, getHistoryDetail } from '@/api'

const logs = ref([])
const loading = ref(false)
const detailLoading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const dateRange = ref(null)
const dialogVisible = ref(false)
const currentDetail = ref(null)

const formatDate = (date) => {
  if (!date) return '-'
  return dayjs(date).format('YYYY-MM-DD HH:mm:ss')
}

const fetchHistory = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (dateRange.value) {
      params.start_date = dayjs(dateRange.value[0]).toISOString()
      params.end_date = dayjs(dateRange.value[1]).endOf('day').toISOString()
    }
    const res = await getHistory(params)
    logs.value = res.data.items
    total.value = res.data.total
  } catch (error) {
    console.error('获取历史记录失败:', error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchHistory()
}

const handleSizeChange = () => {
  currentPage.value = 1
  fetchHistory()
}

const handlePageChange = () => {
  fetchHistory()
}

const viewDetail = async (log) => {
  dialogVisible.value = true
  detailLoading.value = true
  try {
    const res = await getHistoryDetail(log.id)
    currentDetail.value = res.data
  } catch (error) {
    console.error('获取详情失败:', error)
  } finally {
    detailLoading.value = false
  }
}

const openUrl = (url) => {
  if (url) {
    window.open(url, '_blank')
  }
}

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
.history-page {
  padding: 0;
}

.filter-card {
  margin-bottom: 20px;
}

.table-card {
  min-height: 500px;
}

.total-count {
  font-weight: 600;
  font-size: 16px;
}

.change-info {
  display: flex;
  gap: 10px;
}

.added {
  color: #67c23a;
  font-weight: 600;
}

.removed {
  color: #f56c6c;
  font-weight: 600;
}

.no-change {
  color: #909399;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
</style>
