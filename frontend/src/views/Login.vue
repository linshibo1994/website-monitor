<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <div class="logo-icon">
          <el-icon><Monitor /></el-icon>
        </div>
        <h1 class="title">Arc'teryx Monitor</h1>
        <p class="subtitle">商品监控系统</p>
      </div>

      <el-tabs v-model="activeTab" class="login-tabs">
        <el-tab-pane label="密码登录" name="password">
          <el-form
            ref="passwordFormRef"
            :model="passwordForm"
            :rules="passwordRules"
            class="login-form"
          >
            <el-form-item prop="username">
              <el-input
                v-model="passwordForm.username"
                placeholder="用户名"
                size="large"
                :prefix-icon="User"
                clearable
              />
            </el-form-item>

            <el-form-item prop="password">
              <el-input
                v-model="passwordForm.password"
                type="password"
                placeholder="密码"
                size="large"
                :prefix-icon="Lock"
                show-password
                @keyup.enter="handlePasswordLogin"
              />
            </el-form-item>

            <el-button
              type="primary"
              size="large"
              class="login-button"
              :loading="loading"
              @click="handlePasswordLogin"
            >
              登录
            </el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="Token登录" name="token">
          <el-form
            ref="tokenFormRef"
            :model="tokenForm"
            :rules="tokenRules"
            class="login-form"
          >
            <el-form-item prop="token">
              <el-input
                v-model="tokenForm.token"
                type="textarea"
                placeholder="请输入 API Token"
                :rows="4"
                resize="none"
                clearable
              />
            </el-form-item>

            <el-button
              type="primary"
              size="large"
              class="login-button"
              :loading="loading"
              @click="handleTokenLogin"
            >
              登录
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Monitor, User, Lock } from '@element-plus/icons-vue'
import { useAuth } from '@/stores/auth'

const router = useRouter()
const { login, loginWithToken } = useAuth()

// 表单状态
const activeTab = ref('password')
const loading = ref(false)

const passwordFormRef = ref(null)
const tokenFormRef = ref(null)

const passwordForm = ref({
  username: '',
  password: ''
})

const tokenForm = ref({
  token: ''
})

// 验证规则
const passwordRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

const tokenRules = {
  token: [
    { required: true, message: '请输入 API Token', trigger: 'blur' }
  ]
}

// 密码登录
const handlePasswordLogin = async () => {
  if (!passwordFormRef.value) return

  try {
    await passwordFormRef.value.validate()
    loading.value = true

    const result = await login(passwordForm.value.username, passwordForm.value.password)

    if (result.success) {
      ElMessage.success('登录成功')
      router.push('/')
    } else {
      ElMessage.error(result.message || '登录失败')
    }
  } catch (error) {
    console.error('Login validation failed:', error)
  } finally {
    loading.value = false
  }
}

// Token登录
const handleTokenLogin = async () => {
  if (!tokenFormRef.value) return

  try {
    await tokenFormRef.value.validate()
    loading.value = true

    const result = await loginWithToken(tokenForm.value.token)

    if (result.success) {
      ElMessage.success('登录成功')
      router.push('/')
    } else {
      ElMessage.error(result.message || '登录失败')
    }
  } catch (error) {
    console.error('Token login validation failed:', error)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: white;
  border-radius: 16px;
  padding: 48px 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
}

.logo-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  font-size: 32px;
  color: white;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.title {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 8px 0;
}

.subtitle {
  font-size: 14px;
  color: #909399;
  margin: 0;
}

.login-tabs {
  margin-top: 32px;
}

.login-tabs :deep(.el-tabs__header) {
  margin-bottom: 32px;
}

.login-tabs :deep(.el-tabs__item) {
  font-size: 16px;
  font-weight: 500;
}

.login-form {
  margin-top: 24px;
}

.login-form .el-form-item {
  margin-bottom: 24px;
}

.login-button {
  width: 100%;
  margin-top: 12px;
  font-size: 16px;
  font-weight: 600;
  height: 48px;
}

.login-form :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #dcdfe6 inset;
  transition: all 0.3s;
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #c0c4cc inset;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #409eff inset;
}

.login-form :deep(.el-textarea__inner) {
  box-shadow: 0 0 0 1px #dcdfe6 inset;
  transition: all 0.3s;
}

.login-form :deep(.el-textarea__inner:hover) {
  box-shadow: 0 0 0 1px #c0c4cc inset;
}

.login-form :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px #409eff inset;
}
</style>
