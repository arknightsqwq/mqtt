<template>
  <div>
    <!-- 顶部栏：返回 + 设备名 + 状态 -->
    <div class="detail-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" text size="large" @click="$router.back()">返回</el-button>
        <div class="header-info">
          <h1 class="device-name">{{ deviceName }}</h1>
          <span class="device-id">{{ deviceId }}</span>
        </div>
      </div>
      <el-tag
        :type="device?.is_online ? 'success' : 'info'"
        effect="dark"
        size="large"
      >
        <span class="tag-dot" :class="device?.is_online ? 'online' : 'offline'" />
        {{ device?.is_online ? '在线' : '离线' }}
      </el-tag>
    </div>

    <!-- Tab 导航 -->
    <div class="tab-bar">
      <div
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-item"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <el-icon :size="16"><component :is="tab.icon" /></el-icon>
        <span>{{ tab.label }}</span>
      </div>
    </div>

    <!-- Tab 内容 -->
    <div class="tab-content">
      <DeviceOverview
        v-if="activeTab === 'overview'"
        :device-id="deviceId"
        :device="device"
        @unbind="onUnbind"
      />
      <DeviceData
        v-else-if="activeTab === 'data'"
        :device-id="deviceId"
        :latest-raw="device?.latest_raw"
      />
      <DeviceAlerts
        v-else-if="activeTab === 'alerts'"
        :device-id="deviceId"
      />
      <DeviceControl
        v-else-if="activeTab === 'control'"
        :device-id="deviceId"
      />
      <DeviceConfig
        v-else-if="activeTab === 'config'"
        :device-id="deviceId"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Odometer, TrendCharts, Bell, SwitchButton, Setting } from '@element-plus/icons-vue'
import { useDevicesStore } from '@/stores/devices'
import { useAuthStore } from '@/stores/auth'
import { usePolling } from '@/composables/usePolling'
import DeviceOverview from './DeviceOverview.vue'
import DeviceData from './DeviceData.vue'
import DeviceAlerts from './DeviceAlerts.vue'
import DeviceControl from './DeviceControl.vue'
import DeviceConfig from './DeviceConfig.vue'
import type { DeviceSummary } from '@/types'

const route = useRoute()
const router = useRouter()
const devicesStore = useDevicesStore()
const authStore = useAuthStore()

const deviceId = computed(() => route.params.id as string)
const activeTab = ref('overview')
const device = ref<DeviceSummary | null>(null)

const tabs = [
  { key: 'overview', label: '概览', icon: Odometer },
  { key: 'data', label: '数据', icon: TrendCharts },
  { key: 'alerts', label: '告警', icon: Bell },
  { key: 'control', label: '控制', icon: SwitchButton },
  { key: 'config', label: '配置', icon: Setting }
]

const deviceName = computed(() => device.value?.device_name || deviceId.value)

async function fetchData() {
  const id = deviceId.value
  if (!id) return
  const result = await devicesStore.fetchOneDevice(id)
  // 防止异步返回时路由已切换导致数据错乱
  if (id === route.params.id) {
    if (result) device.value = result
  }
}

// 路由参数变化时重新加载（不置空旧数据，避免闪烁）
watch(() => route.params.id, () => {
  activeTab.value = 'overview'
  fetchData()
})

// 首次加载 + 轮询
const polling = usePolling(fetchData, 10000)
polling.start()

function onUnbind() {
  authStore.setBindDevices(authStore.bindDevices.filter(d => d.device_id !== deviceId.value))
  ElMessage.success('设备已解绑')
  router.push('/devices')
}
</script>

<style scoped>
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-lg);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-info {
  display: flex;
  flex-direction: column;
}

.device-name {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.device-id {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  margin-top: 2px;
}

.tag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 4px;
}
.tag-dot.online {
  background: #fff;
  box-shadow: 0 0 6px rgba(255,255,255,0.6);
}
.tag-dot.offline {
  background: rgba(255,255,255,0.5);
}

.tab-bar {
  display: flex;
  border-bottom: 2px solid rgba(0, 0, 0, 0.06);
  margin-bottom: var(--space-lg);
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.2s, border-color 0.2s;
}

.tab-item:hover {
  color: var(--color-primary);
}

.tab-item.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.tab-content {
  min-height: 400px;
}
</style>
