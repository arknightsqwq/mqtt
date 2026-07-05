<template>
  <div>
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <h1 class="greeting">你好，{{ authStore.userId }}</h1>
      <p v-if="devicesStore.list.length" class="summary">
        <span class="count">{{ devicesStore.list.length }}</span> 台设备已连接，
        <span class="count online">{{ onlineCount }}</span> 台在线
      </p>
    </div>

    <!-- 加载中 -->
    <div v-if="devicesStore.loading && !devicesStore.list.length" class="loading-area">
      <el-icon :size="32" class="loading-icon"><Loading /></el-icon>
      <p>加载设备中...</p>
    </div>

    <!-- 设备卡片网格 -->
    <div v-else-if="devicesStore.list.length" class="device-grid">
      <DeviceCard
        v-for="device in devicesStore.list"
        :key="device.device_id"
        :device="device"
        @click="goDevice(device.device_id)"
      />
    </div>

    <!-- 空状态 -->
    <EmptyState
      v-else
      title="还没有绑定设备"
      description="联系管理员获取设备 ID，然后绑定到您的账号"
    >
      <template #action>
        <el-button type="primary" :icon="Plus" @click="showBindDialog = true">绑定设备</el-button>
      </template>
    </EmptyState>

    <!-- 绑定设备对话框 -->
    <el-dialog v-model="showBindDialog" title="绑定设备" width="420px">
      <el-form ref="bindFormRef" :model="bindForm" :rules="bindRules" @keyup.enter="handleBind">
        <el-form-item prop="device_id">
          <el-input v-model="bindForm.device_id" placeholder="请输入设备 ID" size="large" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBindDialog = false">取消</el-button>
        <el-button type="primary" :loading="bindLoading" @click="handleBind">确认绑定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Loading } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useDevicesStore } from '@/stores/devices'
import { usePolling } from '@/composables/usePolling'
import DeviceCard from '@/components/DeviceCard.vue'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const authStore = useAuthStore()
const devicesStore = useDevicesStore()

const showBindDialog = ref(false)
const bindLoading = ref(false)
const bindFormRef = ref<FormInstance>()
const bindForm = reactive({ device_id: '' })

const bindRules: FormRules = {
  device_id: [{ required: true, message: '请输入设备 ID', trigger: 'blur' }]
}

const onlineCount = computed(() => devicesStore.list.filter(d => d.is_online).length)

async function loadDevices() {
  if (!authStore.bindDevices.length) return
  const ids = authStore.bindDevices.map(d => d.device_id)
  await devicesStore.fetchDevices(ids)
}

usePolling(loadDevices, 10000).start()

function goDevice(deviceId: string) {
  router.push(`/device/${deviceId}`)
}

async function handleBind() {
  const valid = await bindFormRef.value?.validate().catch(() => false)
  if (!valid) return
  bindLoading.value = true
  try {
    await devicesStore.bindDevice(bindForm.device_id)
    ElMessage.success('设备绑定成功')
    showBindDialog.value = false
    const boundId = bindForm.device_id
    bindForm.device_id = ''
    const device = await devicesStore.fetchOneDevice(boundId)
    authStore.bindDevices.push({
      device_id: boundId,
      device_name: device?.device_name || boundId,
      device_desc: device?.device_desc || null
    })
  } catch { /* handled by interceptor */ } finally {
    bindLoading.value = false
  }
}
</script>

<style scoped>
.welcome-section {
  margin-bottom: var(--space-lg);
}

.greeting {
  font-size: 26px;
  font-weight: 700;
  background: var(--gradient-welcome);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.summary {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 6px;
}

.count {
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-primary);
}
.count.online {
  color: var(--color-success);
}

.loading-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-2xl);
  color: var(--text-muted);
  gap: var(--space-sm);
}

.loading-icon {
  animation: spin 1s linear infinite;
  color: var(--color-primary);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.device-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-md);
}

@media (min-width: 1200px) {
  .device-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (min-width: 1600px) {
  .device-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
</style>
