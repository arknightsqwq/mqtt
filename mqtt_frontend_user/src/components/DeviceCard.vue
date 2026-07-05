<template>
  <div class="device-card" @click="$emit('click')">
    <!-- 顶部状态条 -->
    <div class="card-status-bar" :class="device.is_online ? 'online' : 'offline'" />

    <!-- 在线状态点 -->
    <div class="card-header">
      <span class="status-dot" :class="device.is_online ? 'online' : 'offline'" />
      <span class="status-text">{{ device.is_online ? '在线' : '离线' }}</span>
    </div>

    <!-- 设备信息 -->
    <div class="card-body">
      <h3 class="device-name">{{ device.device_name || device.device_id }}</h3>
      <p class="device-id">{{ device.device_id }}</p>

      <!-- 最新数据快照 -->
      <div v-if="latestFields.length" class="data-snapshot">
        <div v-for="f in latestFields.slice(0, 3)" :key="f.key" class="snapshot-item">
          <span class="snapshot-value">{{ f.value }}</span>
          <span class="snapshot-label">{{ f.key }}</span>
        </div>
      </div>
      <div v-else class="data-snapshot empty">
        <span class="no-data">暂无数据</span>
      </div>
    </div>

    <!-- 底部时间 -->
    <div class="card-footer">
      <span class="last-time">
        {{ device.latest_time ? formatTime(device.latest_time) : '—' }}
      </span>
      <el-icon :size="16" class="arrow-icon"><ArrowRight /></el-icon>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'
import type { DeviceSummary } from '@/types'

const props = defineProps<{
  device: DeviceSummary
}>()

defineEmits<{
  click: []
}>()

/** 从 latest_raw 中解析字段用于卡片快照展示 */
const latestFields = computed(() => {
  if (!props.device.latest_raw) return []
  try {
    const obj = JSON.parse(props.device.latest_raw)
    if (typeof obj !== 'object' || obj === null) return []
    return Object.entries(obj)
      .filter(([, v]) => v !== null && v !== undefined)
      .slice(0, 3)
      .map(([key, value]) => ({
        key,
        value: typeof value === 'number' ? value.toFixed(1) : String(value).substring(0, 10)
      }))
  } catch {
    return []
  }
})

function formatTime(time: string) {
  // "YYYY-MM-DD HH:MM:SS" -> "HH:MM:SS" or relative
  const now = new Date()
  const t = new Date(time.replace(' ', 'T'))
  const diff = now.getTime() - t.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  return time.substring(11, 19) || time
}
</script>

<style scoped>
.device-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
}

.device-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.device-card:active {
  transform: scale(0.98);
}

.card-status-bar {
  height: 3px;
  width: 100%;
}
.card-status-bar.online {
  background: var(--gradient-success);
}
.card-status-bar.offline {
  background: #ddd;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 14px 0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot.online {
  background: var(--color-success);
  box-shadow: var(--shadow-glow-green);
  animation: pulse 2s infinite;
}
.status-dot.offline {
  background: var(--text-muted);
}

.status-text {
  font-size: 12px;
  color: var(--text-secondary);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.card-body {
  padding: 10px 14px;
  flex: 1;
}

.device-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-id {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  margin-bottom: 10px;
}

.data-snapshot {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.data-snapshot.empty {
  justify-content: flex-start;
}

.no-data {
  font-size: 13px;
  color: var(--text-muted);
}

.snapshot-item {
  display: flex;
  flex-direction: column;
}

.snapshot-value {
  font-size: 18px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--color-primary);
}

.snapshot-label {
  font-size: 11px;
  color: var(--text-muted);
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-top: 1px solid rgba(0, 0, 0, 0.04);
}

.last-time {
  font-size: 12px;
  color: var(--text-muted);
}

.arrow-icon {
  color: var(--text-muted);
}
</style>
