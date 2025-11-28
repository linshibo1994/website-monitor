<template>
  <div class="products-page">
    <!-- 搜索和筛选 -->
    <el-card class="filter-card">
      <el-row :gutter="20">
        <el-col :span="8">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索商品名称..."
            clearable
            @clear="handleSearch"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="6">
          <el-select v-model="statusFilter" placeholder="状态筛选" clearable @change="handleSearch">
            <el-option label="全部" value="" />
            <el-option label="在售" value="active" />
            <el-option label="已下架" value="removed" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
        </el-col>
        <el-col :span="6" style="text-align: right;">
          <el-tag type="info" size="large">
            共 {{ total }} 件商品
          </el-tag>
        </el-col>
      </el-row>
    </el-card>

    <!-- 商品表格 -->
    <el-card class="table-card">
      <el-table
        :data="products"
        v-loading="loading"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="product_id" label="商品ID" width="120" />
        <el-table-column prop="name" label="商品名称" min-width="250">
          <template #default="{ row }">
            <a :href="row.url" target="_blank" class="product-link">
              {{ row.name }}
            </a>
          </template>
        </el-table-column>
        <el-table-column label="价格" width="150">
          <template #default="{ row }">
            <div>
              <span class="current-price">${{ row.price?.toFixed(2) || '未知' }}</span>
              <span v-if="row.original_price && row.original_price > row.price" class="original-price">
                ${{ row.original_price.toFixed(2) }}
              </span>
            </div>
            <el-tag v-if="row.is_on_sale" type="danger" size="small" style="margin-top: 5px;">
              促销
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '在售' : '已下架' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="首次发现" width="160">
          <template #default="{ row }">
            {{ formatDate(row.first_seen_at) }}
          </template>
        </el-table-column>
        <el-table-column label="最后更新" width="160">
          <template #default="{ row }">
            {{ formatDate(row.last_seen_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewProduct(row)">
              <el-icon><View /></el-icon>
              查看
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

    <!-- 商品详情弹窗 -->
    <el-dialog v-model="dialogVisible" title="商品详情" width="500px">
      <el-descriptions :column="1" border v-if="currentProduct">
        <el-descriptions-item label="商品ID">{{ currentProduct.product_id }}</el-descriptions-item>
        <el-descriptions-item label="商品名称">{{ currentProduct.name }}</el-descriptions-item>
        <el-descriptions-item label="当前价格">${{ currentProduct.price?.toFixed(2) || '未知' }}</el-descriptions-item>
        <el-descriptions-item label="原价" v-if="currentProduct.original_price">
          ${{ currentProduct.original_price.toFixed(2) }}
        </el-descriptions-item>
        <el-descriptions-item label="是否促销">
          <el-tag :type="currentProduct.is_on_sale ? 'danger' : 'info'" size="small">
            {{ currentProduct.is_on_sale ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="currentProduct.status === 'active' ? 'success' : 'info'">
            {{ currentProduct.status === 'active' ? '在售' : '已下架' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="首次发现">{{ formatDate(currentProduct.first_seen_at) }}</el-descriptions-item>
        <el-descriptions-item label="最后更新">{{ formatDate(currentProduct.last_seen_at) }}</el-descriptions-item>
        <el-descriptions-item label="下架时间" v-if="currentProduct.removed_at">
          {{ formatDate(currentProduct.removed_at) }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="openProductPage">
          <el-icon><Link /></el-icon>
          查看原页面
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import { getProducts } from '@/api'

const products = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const statusFilter = ref('')
const dialogVisible = ref(false)
const currentProduct = ref(null)

const formatDate = (date) => {
  if (!date) return '-'
  return dayjs(date).format('YYYY-MM-DD HH:mm')
}

const fetchProducts = async () => {
  loading.value = true
  try {
    const res = await getProducts({
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchKeyword.value || undefined,
      status: statusFilter.value || undefined
    })
    products.value = res.data.items
    total.value = res.data.total
  } catch (error) {
    console.error('获取商品失败:', error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchProducts()
}

const handleSizeChange = () => {
  currentPage.value = 1
  fetchProducts()
}

const handlePageChange = () => {
  fetchProducts()
}

const viewProduct = (product) => {
  currentProduct.value = product
  dialogVisible.value = true
}

const openProductPage = () => {
  if (currentProduct.value?.url) {
    window.open(currentProduct.value.url, '_blank')
  }
}

onMounted(() => {
  fetchProducts()
})
</script>

<style scoped>
.products-page {
  padding: 0;
}

.filter-card {
  margin-bottom: 20px;
}

.table-card {
  min-height: 500px;
}

.product-link {
  color: #409eff;
  text-decoration: none;
}

.product-link:hover {
  text-decoration: underline;
}

.current-price {
  font-weight: 600;
  color: #303133;
}

.original-price {
  text-decoration: line-through;
  color: #909399;
  margin-left: 8px;
  font-size: 12px;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
</style>
