<template>
  <div class="device-alerts">
    <!-- 时间筛选 -->
    <div class="filter-bar">
      <el-radio-group v-model="hours" size="small" @change="loadAlerts">
        <el-radio-button :value="1">1小时</el-radio-button>
        <el-radio-button :value="6">6小时</el-radio-button>
        <el-radio-button :value="24">24小时</el-radio-button>
        <el-radio-button :value="48">48小时</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-area">
      <el-icon :size="24" class="loading-icon"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <!-- 告警列表 -->
    <div v-else-if="filteredAlerts.length">
      <AlertItem
        v-for="alert in filteredAlerts"
        :key="alert.id"
        :alert="alert"
      />
    </div>

    <!-- 空状态 -->
    <div v-else class="empty">
      <el-icon :size="40" color="var(--color-success)"><CircleCheckFilled /></el-icon>
      <p>该设备暂无告警</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { Loading, CircleCheckFilled } from '@element-plus/icons-vue'
import { getAlerts } from '@/api/device'
import AlertItem from '@/components/AlertItem.vue'
import type { AlertItemData } from '@/types'

const props = defineProps<{
  deviceId: string
}>()

const alerts = ref<AlertItemData[]>([])
const loading = ref(false)
const hours = ref(48)

const filteredAlerts = computed(() =>
  alerts.value.filter(a => a.device_id === props.deviceId)
)

async function loadAlerts() {
  // 仅在首次加载（无缓存数据）时显示 loading，后续静默刷新避免闪烁
  if (alerts.value.length === 0) loading.value = true
  try {
    const res = await getAlerts({ hours: hours.value, limit: 200 })
    if (res.code === 200 && res.data) {
      alerts.value = res.data.alerts || []
    }
  } finally {
    loading.value = false
  }
}

watch(() => props.deviceId, () => { alerts.value = []; loadAlerts() }, { immediate: true })

// 每 15 秒轮询刷新告警列表
const timer = setInterval(loadAlerts, 15000)
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.device-alerts {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.filter-bar {
  margin-bottom: var(--space-xs);
}

.loading-area {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-2xl);
  color: var(--text-muted);
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-2xl);
  color: var(--text-secondary);
  gap: var(--space-sm);
}
</style>
