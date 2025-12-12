<template>
  <div class="settings-page">
    <el-row :gutter="20">
      <!-- 监控配置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><Monitor /></el-icon>
              <span>监控配置</span>
            </div>
          </template>
          <el-form :model="settings.monitor" label-width="100px" v-loading="loading">
            <el-form-item label="监控URL">
              <el-input v-model="settings.monitor.url" disabled />
            </el-form-item>
            <el-form-item label="检测间隔">
              <el-input-number
                v-model="settings.monitor.interval_minutes"
                :min="1"
                :max="1440"
                style="width: 150px;"
              />
              <span style="margin-left: 10px;">分钟</span>
            </el-form-item>
            <el-form-item label="超时时间">
              <el-input-number
                v-model="settings.monitor.timeout_seconds"
                :min="10"
                :max="300"
                style="width: 150px;"
              />
              <span style="margin-left: 10px;">秒</span>
            </el-form-item>
            <el-form-item label="重试次数">
              <el-input-number
                v-model="settings.monitor.retry_times"
                :min="0"
                :max="10"
                style="width: 150px;"
              />
            </el-form-item>
            <el-form-item label="无头模式">
              <el-switch v-model="settings.monitor.headless" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 邮件配置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><Message /></el-icon>
              <span>邮件通知</span>
            </div>
          </template>
          <el-form :model="settings.email" label-width="100px" v-loading="loading">
            <el-form-item label="启用通知">
              <el-switch v-model="settings.email.enabled" />
            </el-form-item>
            <el-form-item label="SMTP服务器">
              <el-input v-model="settings.email.smtp_server" />
            </el-form-item>
            <el-form-item label="SMTP端口">
              <el-input-number
                v-model="settings.email.smtp_port"
                :min="1"
                :max="65535"
                style="width: 150px;"
              />
            </el-form-item>
            <el-form-item label="发件人">
              <el-input v-model="settings.email.sender" placeholder="your_qq@qq.com" />
            </el-form-item>
            <el-form-item label="授权码">
              <el-input
                v-model="settings.email.password"
                type="password"
                placeholder="QQ邮箱授权码"
                show-password
              />
            </el-form-item>
            <el-form-item label="收件人">
              <el-input v-model="settings.email.receiver" placeholder="接收通知的邮箱" />
            </el-form-item>
            <el-form-item>
              <el-button type="info" @click="handleTestEmail" :loading="testingEmail">
                <el-icon><Promotion /></el-icon>
                发送测试邮件
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 微信通知配置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><ChatDotRound /></el-icon>
              <span>微信通知 (ServerChan)</span>
            </div>
          </template>
          <el-form :model="settings.wechat" label-width="100px" v-loading="loading">
            <el-form-item label="启用通知">
              <el-switch v-model="settings.wechat.enabled" />
            </el-form-item>
            <el-form-item label="SendKey">
              <el-input
                v-model="settings.wechat.sendkey"
                type="password"
                placeholder="ServerChan SendKey"
                show-password
              />
            </el-form-item>
            <el-form-item>
              <el-link type="primary" href="https://sct.ftqq.com" target="_blank" rel="noopener noreferrer">
                获取 SendKey
              </el-link>
              <span class="form-tip">微信扫码登录后获取</span>
            </el-form-item>
            <el-form-item>
              <el-button type="info" @click="handleTestWechat" :loading="testingWechat" :disabled="!settings.wechat.sendkey || settings.wechat.sendkey === '******'">
                <el-icon><Promotion /></el-icon>
                发送测试消息
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- QQ通知配置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><ChatLineSquare /></el-icon>
              <span>QQ通知 (Qmsg酱)</span>
            </div>
          </template>
          <el-form :model="settings.qq" label-width="100px" v-loading="loading">
            <el-form-item label="启用通知">
              <el-switch v-model="settings.qq.enabled" />
            </el-form-item>
            <el-form-item label="Key">
              <el-input
                v-model="settings.qq.key"
                type="password"
                placeholder="Qmsg酱 Key"
                show-password
              />
            </el-form-item>
            <el-form-item label="QQ号">
              <el-input
                v-model="settings.qq.qq"
                placeholder="接收通知的QQ号"
              />
            </el-form-item>
            <el-form-item>
              <el-link type="primary" href="https://qmsg.zendee.cn" target="_blank" rel="noopener noreferrer">
                获取 Key
              </el-link>
              <span class="form-tip">注册后添加机器人为好友</span>
            </el-form-item>
            <el-form-item>
              <el-button type="info" @click="handleTestQQ" :loading="testingQQ" :disabled="!settings.qq.key || settings.qq.key === '******' || !settings.qq.qq">
                <el-icon><Promotion /></el-icon>
                发送测试消息
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 通知设置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><Bell /></el-icon>
              <span>通知设置</span>
            </div>
          </template>
          <el-form :model="settings.notification" label-width="120px" v-loading="loading">
            <el-form-item label="新增商品通知">
              <el-switch v-model="settings.notification.notify_on_added" />
              <span class="form-tip">商品数量增加时发送通知</span>
            </el-form-item>
            <el-form-item label="下架商品通知">
              <el-switch v-model="settings.notification.notify_on_removed" />
              <span class="form-tip">商品下架时发送通知</span>
            </el-form-item>
            <el-form-item label="异常告警通知">
              <el-switch v-model="settings.notification.notify_on_error" />
              <span class="form-tip">监控程序出错时发送通知</span>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 操作按钮 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><Operation /></el-icon>
              <span>操作</span>
            </div>
          </template>
          <div class="action-section">
            <el-button type="primary" size="large" @click="handleSave" :loading="saving" style="width: 200px;">
              <el-icon><Check /></el-icon>
              保存配置
            </el-button>
            <el-button size="large" @click="handleReload" :loading="reloading" style="width: 200px; margin-left: 20px;">
              <el-icon><RefreshRight /></el-icon>
              重新加载
            </el-button>
          </div>
          <el-divider />
          <el-alert
            title="配置说明"
            type="info"
            :closable="false"
          >
            <template #default>
              <ul style="margin: 10px 0; padding-left: 20px; line-height: 1.8;">
                <li>修改配置后需要点击"保存配置"按钮</li>
                <li>可同时启用多个通知渠道</li>
                <li>建议先发送测试消息验证配置是否正确</li>
                <li>QQ邮箱授权码需要在QQ邮箱设置中开启SMTP服务后获取</li>
              </ul>
            </template>
          </el-alert>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, updateSettings, sendTestEmail, sendTestWechat, sendTestQQ, reloadConfig } from '@/api'

const loading = ref(false)
const saving = ref(false)
const reloading = ref(false)
const testingEmail = ref(false)
const testingWechat = ref(false)
const testingQQ = ref(false)

const settings = reactive({
  monitor: {
    url: '',
    interval_minutes: 10,
    timeout_seconds: 60,
    retry_times: 3,
    headless: true
  },
  email: {
    enabled: true,
    smtp_server: 'smtp.qq.com',
    smtp_port: 465,
    sender: '',
    password: '',
    receiver: ''
  },
  wechat: {
    enabled: false,
    sendkey: ''
  },
  qq: {
    enabled: false,
    key: '',
    qq: ''
  },
  notification: {
    notify_on_added: true,
    notify_on_removed: true,
    notify_on_error: true
  }
})

const fetchSettings = async () => {
  loading.value = true
  try {
    const res = await getSettings()
    Object.assign(settings.monitor, res.data.monitor)
    Object.assign(settings.email, res.data.email)
    Object.assign(settings.notification, res.data.notification)
    // 加载微信和QQ配置（如果存在）
    if (res.data.wechat) {
      Object.assign(settings.wechat, res.data.wechat)
    }
    if (res.data.qq) {
      Object.assign(settings.qq, res.data.qq)
    }
  } catch (error) {
    console.error('获取设置失败:', error)
    ElMessage.error('获取设置失败')
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    await updateSettings({
      monitor: settings.monitor,
      email: settings.email,
      wechat: settings.wechat,
      qq: settings.qq,
      notification: settings.notification
    })
    ElMessage.success('配置已保存')
  } catch (error) {
    console.error('保存失败:', error)
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const handleReload = async () => {
  reloading.value = true
  try {
    await reloadConfig()
    await fetchSettings()
    ElMessage.success('配置已重新加载')
  } catch (error) {
    console.error('重新加载失败:', error)
    ElMessage.error('重新加载失败')
  } finally {
    reloading.value = false
  }
}

const handleTestEmail = async () => {
  testingEmail.value = true
  try {
    const res = await sendTestEmail()
    if (res.data.success) {
      ElMessage.success('测试邮件发送成功，请检查收件箱')
    } else {
      ElMessage.warning(res.data.message || '发送失败')
    }
  } catch (error) {
    console.error('发送测试邮件失败:', error)
    ElMessage.error('发送失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    testingEmail.value = false
  }
}

const handleTestWechat = async () => {
  testingWechat.value = true
  try {
    const res = await sendTestWechat()
    if (res.data.success) {
      ElMessage.success('微信测试消息发送成功')
    } else {
      ElMessage.warning(res.data.message || '发送失败')
    }
  } catch (error) {
    console.error('发送微信测试消息失败:', error)
    ElMessage.error('发送失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    testingWechat.value = false
  }
}

const handleTestQQ = async () => {
  testingQQ.value = true
  try {
    const res = await sendTestQQ()
    if (res.data.success) {
      ElMessage.success('QQ测试消息发送成功')
    } else {
      ElMessage.warning(res.data.message || '发送失败')
    }
  } catch (error) {
    console.error('发送QQ测试消息失败:', error)
    ElMessage.error('发送失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    testingQQ.value = false
  }
}

onMounted(() => {
  fetchSettings()
})
</script>

<style scoped>
.settings-page {
  padding: 0;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.form-tip {
  margin-left: 15px;
  color: #909399;
  font-size: 13px;
}

.action-section {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}
</style>
