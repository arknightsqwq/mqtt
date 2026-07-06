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
        <!-- 统计卡片（按分组，同组放在一张卡片内） -->
        <template v-if="groupEntries.length">
          <div
            v-for="[groupName, fields] in groupEntries"
            :key="groupName"
            class="stat-group-card"
            :style="{ borderLeftColor: groupColor(groupName), backgroundColor: groupColor(groupName) + '36' }"
          >
            <h3 class="group-title">{{ groupName }}</h3>
            <div class="stat-group-fields">
              <div v-for="f in fields" :key="f.key" class="stat-group-item">
                <span class="stat-group-value">{{ f.value }}</span>
                <span class="stat-group-label">{{ getLabel(f.key) }}</span>
              </div>
            </div>
          </div>
        </template>

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
import { useFieldLabel } from '@/composables/useFieldLabel'
import { FIELD_GROUPS, DEFAULT_GROUP } from '@/constants/fieldGroups'
import DeviceMap from '@/components/DeviceMap.vue'
import type { DeviceSummary } from '@/types'

const { translate } = useFieldLabel()
function getLabel(key: string) { return translate(props.device?.field_labels, key) }

/**
 * 按分组整理遥测字段。
 * 返回 Map<分组名, {key, value}[]>，按分组定义顺序排列。
 */
function groupFields(fields: { key: string; value: string }[]) {
  const map = new Map<string, { key: string; value: string }[]>()
  for (const f of fields) {
    const group = FIELD_GROUPS[f.key] || DEFAULT_GROUP
    if (!map.has(group)) map.set(group, [])
    map.get(group)!.push(f)
  }
  return map
}

const props = defineProps<{
  deviceId: string
  device: DeviceSummary | null
}>()

const emit = defineEmits<{
  unbind: []
}>()

const devicesStore = useDevicesStore()

/** 分组→卡片左侧色条颜色 */
const GROUP_COLORS: Record<string, string> = {
  '生命体征': '#FF6B6B',
  '环境':     '#4A90D9',
  '位置':     '#20BF6B',
  '设备':     '#E6A23C',
  '其他':     '#B0B4C8',
}

function groupColor(groupName: string): string {
  return GROUP_COLORS[groupName] || GROUP_COLORS['其他']
}

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

/** 已分组且含数据的遥测字段 */
const groupEntries = computed(() => {
  const map = groupFields(parsedFields.value)
  // 按代码中分组定义的顺序：生命体征 → 环境 → 位置 → 设备 → 其他
  const order = ['生命体征', '环境', '位置', '设备']
  const sorted = new Map<string, { key: string; value: string }[]>()
  for (const g of order) {
    if (map.has(g)) sorted.set(g, map.get(g)!)
  }
  // 追加不在 order 列表中的分组
  for (const [g, fields] of map) {
    if (!sorted.has(g)) sorted.set(g, fields)
  }
  return [...sorted.entries()]
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

.stat-group-card {
  background: var(--bg-card);
  border-left: 3px solid var(--color-primary);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 18px 20px;
  margin-bottom: var(--space-md);
}

.group-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 14px;
}

.stat-group-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 28px 32px;
}

.stat-group-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-group-value {
  font-size: 20px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-group-label {
  font-size: 12px;
  color: var(--text-secondary);
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
