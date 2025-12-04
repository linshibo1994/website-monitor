<template>
  <div class="token-manage-view">
    <el-card shadow="never" class="header-card">
      <div class="header-content">
        <div class="header-left">
          <h2 class="page-title">API Token 管理</h2>
          <p class="page-desc">管理您的 API Token，用于系统访问认证</p>
        </div>
        <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">
          创建 Token
        </el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-table
        v-loading="loading"
        :data="tokenList"
        stripe
        style="width: 100%"
      >
        <el-table-column label="备注" prop="name" min-width="150">
          <template #default="{ row }">
            <div class="token-name">
              <el-icon class="mr-1"><Key /></el-icon>
              {{ row.name || '未命名' }}
            </div>
          </template>
        </el-table-column>

        <el-table-column label="有效期" prop="expires_at" width="120">
          <template #default="{ row }">
            <el-tag v-if="!row.expires_at" type="success" size="small">
              永久有效
            </el-tag>
            <el-tag v-else-if="isExpired(row.expires_at)" type="danger" size="small">
              已过期
            </el-tag>
            <el-tag v-else type="info" size="small">
              {{ formatExpiresAt(row.expires_at) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="创建时间" prop="created_at" width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="最后使用" prop="last_used_at" width="160">
          <template #default="{ row }">
            {{ row.last_used_at ? formatTime(row.last_used_at) : '从未使用' }}
          </template>
        </el-table-column>

        <el-table-column label="状态" prop="status" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.expires_at && isExpired(row.expires_at)" type="danger" size="small">已过期</el-tag>
            <el-tag v-else-if="row.is_revoked" type="info" size="small">已撤销</el-tag>
            <el-tag v-else type="success" size="small">正常</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              size="small"
              :icon="Edit"
              @click="handleEditToken(row)"
            >
              编辑
            </el-button>
            <el-button
              link
              type="danger"
              size="small"
              :icon="Delete"
              :disabled="row.is_revoked"
              @click="handleDeleteToken(row)"
            >
              撤销
            </el-button>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无 Token">
            <el-button type="primary" @click="showCreateDialog = true">
              创建第一个 Token
            </el-button>
          </el-empty>
        </template>
      </el-table>
    </el-card>

    <!-- 创建 Token 对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建 API Token"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="80px"
      >
        <el-form-item label="备注" prop="name">
          <el-input
            v-model="createForm.name"
            placeholder="请输入备注，便于识别"
            clearable
          />
        </el-form-item>

        <el-form-item label="有效期" prop="expiresIn">
          <el-select v-model="createForm.expiresIn" style="width: 100%">
            <el-option label="1 天" value="1d" />
            <el-option label="7 天" value="7d" />
            <el-option label="30 天" value="30d" />
            <el-option label="90 天" value="90d" />
            <el-option label="永久有效" value="forever" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreateToken">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- Token 创建成功对话框 -->
    <el-dialog
      v-model="showTokenDialog"
      title="Token 创建成功"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="warning"
        :closable="false"
        show-icon
      >
        <template #title>
          <div class="alert-title">请立即复制保存您的 Token</div>
        </template>
        <div class="alert-desc">
          出于安全考虑，Token 只会显示一次，关闭后将无法再次查看。
        </div>
      </el-alert>

      <div class="token-display">
        <el-input
          v-model="newToken"
          type="textarea"
          :rows="4"
          readonly
          class="token-textarea"
        />
        <el-button
          type="primary"
          :icon="CopyDocument"
          class="copy-button"
          @click="handleCopyToken"
        >
          复制 Token
        </el-button>
      </div>

      <template #footer>
        <el-button type="primary" @click="showTokenDialog = false">
          我已保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑 Token 对话框 -->
    <el-dialog
      v-model="showEditDialog"
      title="编辑 Token"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="editFormRef"
        :model="editForm"
        :rules="editRules"
        label-width="80px"
      >
        <el-form-item label="备注" prop="name">
          <el-input
            v-model="editForm.name"
            placeholder="请输入备注"
            clearable
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleUpdateToken">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Key, Edit, Delete, CopyDocument } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import {
  getTokenList,
  createToken,
  updateToken,
  deleteToken
} from '@/api'

// 状态
const loading = ref(false)
const submitting = ref(false)
const tokenList = ref([])

// 对话框状态
const showCreateDialog = ref(false)
const showTokenDialog = ref(false)
const showEditDialog = ref(false)
const newToken = ref('')

// 表单引用
const createFormRef = ref(null)
const editFormRef = ref(null)

// 创建表单
const createForm = ref({
  name: '',
  expiresIn: '30d'
})

const createRules = {
  name: [
    { required: true, message: '请输入备注', trigger: 'blur' }
  ],
  expiresIn: [
    { required: true, message: '请选择有效期', trigger: 'change' }
  ]
}

// 编辑表单
const editForm = ref({
  id: null,
  name: ''
})

const editRules = {
  name: [
    { required: true, message: '请输入备注', trigger: 'blur' }
  ]
}

// 获取 Token 列表
const fetchTokenList = async () => {
  loading.value = true
  try {
    const res = await getTokenList()
    // 后端直接返回数组
    tokenList.value = Array.isArray(res.data) ? res.data : []
  } catch (error) {
    console.error('Failed to fetch token list:', error)
    ElMessage.error('获取 Token 列表失败')
  } finally {
    loading.value = false
  }
}

// 创建 Token
const handleCreateToken = async () => {
  if (!createFormRef.value) return

  try {
    await createFormRef.value.validate()
    submitting.value = true

    const res = await createToken(createForm.value.name, createForm.value.expiresIn)

    // 后端返回: { token, token_info }
    if (res.data && res.data.token) {
      ElMessage.success('Token 创建成功')
      newToken.value = res.data.token
      showCreateDialog.value = false
      showTokenDialog.value = true

      // 重置表单
      createForm.value = { name: '', expiresIn: '30d' }

      // 刷新列表
      fetchTokenList()
    } else {
      ElMessage.error('Token 创建失败')
    }
  } catch (error) {
    console.error('Token creation failed:', error)
    ElMessage.error(error.response?.data?.detail || 'Token 创建失败')
  } finally {
    submitting.value = false
  }
}

// 编辑 Token
const handleEditToken = (row) => {
  editForm.value = {
    id: row.id,
    name: row.name
  }
  showEditDialog.value = true
}

// 更新 Token
const handleUpdateToken = async () => {
  if (!editFormRef.value) return

  try {
    await editFormRef.value.validate()
    submitting.value = true

    const res = await updateToken(editForm.value.id, editForm.value.name)

    // 后端返回更新后的 token 对象
    if (res.data && res.data.id) {
      ElMessage.success('Token 更新成功')
      showEditDialog.value = false
      fetchTokenList()
    } else {
      ElMessage.error('Token 更新失败')
    }
  } catch (error) {
    console.error('Token update failed:', error)
    ElMessage.error(error.response?.data?.detail || 'Token 更新失败')
  } finally {
    submitting.value = false
  }
}

// 删除 Token
const handleDeleteToken = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要撤销 Token "${row.name}"吗？撤销后该 Token 将无法再使用。`,
      '撤销 Token',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const res = await deleteToken(row.id)

    // 后端返回撤销后的 token 对象
    if (res.data && res.data.id) {
      ElMessage.success('Token 已撤销')
      fetchTokenList()
    } else {
      ElMessage.error('Token 撤销失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Token deletion failed:', error)
      ElMessage.error(error.response?.data?.detail || 'Token 撤销失败')
    }
  }
}

// 复制 Token
const handleCopyToken = async () => {
  try {
    await navigator.clipboard.writeText(newToken.value)
    ElMessage.success('Token 已复制到剪贴板')
  } catch (error) {
    console.error('Failed to copy token:', error)
    ElMessage.error('复制失败，请手动复制')
  }
}

// 格式化时间
const formatTime = (time) => {
  if (!time) return '-'
  return dayjs(time).format('YYYY-MM-DD HH:mm')
}

// 判断是否过期
const isExpired = (expiresAt) => {
  if (!expiresAt) return false
  return dayjs(expiresAt).isBefore(dayjs())
}

// 格式化过期时间
const formatExpiresAt = (expiresAt) => {
  if (!expiresAt) return '永久'
  return dayjs(expiresAt).format('MM-DD HH:mm')
}

onMounted(() => {
  fetchTokenList()
})
</script>

<style scoped>
.token-manage-view {
  max-width: 1400px;
  margin: 0 auto;
}

.header-card {
  margin-bottom: 20px;
  border: none;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  flex: 1;
}

.page-title {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.page-desc {
  margin: 0;
  font-size: 14px;
  color: #909399;
}

.table-card {
  border: none;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}

.token-name {
  display: flex;
  align-items: center;
  font-weight: 500;
}

.mr-1 {
  margin-right: 4px;
}

.alert-title {
  font-weight: 600;
  font-size: 14px;
}

.alert-desc {
  margin-top: 8px;
  font-size: 13px;
}

.token-display {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.token-textarea :deep(.el-textarea__inner) {
  font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
  font-size: 12px;
  background-color: #f5f7fa;
}

.copy-button {
  align-self: flex-end;
}
</style>
