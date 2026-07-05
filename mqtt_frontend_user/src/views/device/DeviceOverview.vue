<template>
  <div class="overview has-map">
    <!-- 在线状态横幅 -->
    <div class="status-banner" :class="device?.is_online ? 'online' : 'offline'">
      <span class="status-dot" :class="device?.is_online ? 'online' : 'offline'" />
      <div>
        <div class="status-label">{{ device?.is_online ? '设备在线' : '设备离线' }}</div>
        <div class="status-time" v-if="device?.latest_time">
          最新数据：{{ device.latest_time }}
        </div>
      </div>
    </div>

    <!-- 有地图时左右分栏，无地图时竖向排列 -->
    <div class="content-area">
      <div class="left-col">
        <!-- 统计卡片 -->
        <div v-if="parsedFields.length" class="stat-grid">
          <StatCard
            v-for="(f, i) in parsedFields"
            :key="f.key"
            :value="f.value"
            :label="f.key"
            :bg="statColors[i % statColors.length]"
          />
        </div>

        <!-- 无数据提示 -->
        <div v-else class="no-data-card">
          <el-icon :size="32" color="var(--text-muted)"><Warning /></el-icon>
          <p>暂无遥测数据</p>
          <span class="hint">等待设备上报数据...</span>
        </div>

        <!-- 设备信息 -->
        <div class="info-section">
          <h3>设备信息</h3>
          <div class="info-row">
            <span class="info-label">设备 ID</span>
            <span class="info-value">{{ device?.device_id }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">设备名称</span>
            <span class="info-value">{{ device?.device_name }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">在线状态</span>
            <el-tag :type="device?.is_online ? 'success' : 'info'" size="small">
              {{ device?.is_online ? '在线' : '离线' }}
            </el-tag>
          </div>
          <div v-if="device?.last_online_time" class="info-row">
            <span class="info-label">最后上线</span>
            <span class="info-value">{{ device.last_online_time }}</span>
          </div>
        </div>

        <!-- 解绑按钮 -->
        <div class="danger-zone">
          <el-button
            type="danger"
            plain
            size="large"
            :icon="Delete"
            class="unbind-btn"
            @click="handleUnbind"
          >
            解绑此设备
          </el-button>
        </div>
      </div>

      <!-- 设备位置 -->
      <div class="map-section">
        <h3>设备位置</h3>
        <DeviceMap
          :latitude="deviceLat ?? 0"
          :longitude="deviceLng ?? 0"
          :device-name="device?.device_name || deviceId"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Warning, Delete } from '@element-plus/icons-vue'
import { useDevicesStore } from '@/stores/devices'
import StatCard from '@/components/StatCard.vue'
import DeviceMap from '@/components/DeviceMap.vue'
import type { DeviceSummary } from '@/types'

const props = defineProps<{
  deviceId: string
  device: DeviceSummary | null
}>()

const emit = defineEmits<{
  unbind: []
}>()

const devicesStore = useDevicesStore()

/** 渐变色背景列表 */
const statColors = [
  'var(--gradient-primary)',
  'var(--gradient-success)',
  'linear-gradient(135deg, #2E86DE, #54A0FF)',
  'linear-gradient(135deg, #FF6B6B, #EE5A24)',
  'linear-gradient(135deg, #8854D0, #A55EEA)',
  'linear-gradient(135deg, #20BF6B, #26DE81)'
]

/** 从 latest_raw 解析数值字段 */
const parsedFields = computed(() => {
  if (!props.device?.latest_raw) return []
  try {
    const obj = JSON.parse(props.device.latest_raw)
    if (typeof obj !== 'object' || obj === null) return []
    return Object.entries(obj)
      .filter(([, v]) => typeof v === 'number')
      .map(([key, value]) => ({
        key,
        value: Number(value).toFixed(1)
      }))
  } catch {
    return []
  }
})

/** 从 latest_raw 提取经纬度 */
const deviceLat = computed(() => {
  if (!props.device?.latest_raw) return null
  try {
    const obj = JSON.parse(props.device.latest_raw)
    const lat = obj.gps_latitude ?? obj.latitude ?? obj.lat
    return typeof lat === 'number' ? lat : null
  } catch {
    return null
  }
})

const deviceLng = computed(() => {
  if (!props.device?.latest_raw) return null
  try {
    const obj = JSON.parse(props.device.latest_raw)
    const lng = obj.gps_longitude ?? obj.longitude ?? obj.lng ?? obj.lon
    return typeof lng === 'number' ? lng : null
  } catch {
    return null
  }
})

const hasMap = computed(() => deviceLat.value != null && deviceLng.value != null)

async function handleUnbind() {
  try {
    await ElMessageBox.confirm(
      `确定要解绑设备 "${props.device?.device_name || props.deviceId}" 吗？解绑后您将无法查看该设备的数据。`,
      '确认解绑',
      { type: 'warning', confirmButtonText: '确定解绑', cancelButtonText: '取消' }
    )
    await devicesStore.unbindDevice(props.deviceId)
    emit('unbind')
  } catch {
    // 用户取消
  }
}
</script>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

/* 有地图时左右分栏 */
.content-area {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.has-map .content-area {
  flex-direction: row;
  align-items: stretch;
}

.left-col {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.has-map .left-col {
  flex: 1;
  min-width: 0;
}

.map-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
}

.has-map .map-section {
  flex: 1;
  min-width: 0;
  position: sticky;
  top: 80px;
}

.map-section h3 {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: var(--space-sm);
}

.status-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: var(--radius-md);
  color: #fff;
}
.status-banner.online {
  background: var(--gradient-success);
}
.status-banner.offline {
  background: linear-gradient(135deg, #909399, #B0B3BB);
}

.status-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.online {
  background: #fff;
  box-shadow: 0 0 12px rgba(255,255,255,0.6);
  animation: pulse-white 2s infinite;
}
.status-dot.offline {
  background: rgba(255,255,255,0.5);
}

@keyframes pulse-white {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-label {
  font-size: 16px;
  font-weight: 600;
}

.status-time {
  font-size: 12px;
  opacity: 0.8;
  margin-top: 2px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-sm);
}

.no-data-card {
  text-align: center;
  padding: var(--space-xl);
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.no-data-card p {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: var(--space-sm);
}

.no-data-card .hint {
  font-size: 12px;
  color: var(--text-muted);
}

.info-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  box-shadow: var(--shadow-sm);
}

.info-section h3 {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: var(--space-sm);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}
.info-row:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.info-value {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.danger-zone {
  padding-top: var(--space-md);
}

.unbind-btn {
  width: 100%;
  height: 44px;
}
</style>
