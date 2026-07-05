<template>
  <div>
    <div class="page-header">
      <h1>告警中心</h1>
      <p v-if="alertsStore.items.length" class="subtitle">
        最近 {{ selectedHours }} 小时共 {{ alertsStore.items.length }} 条告警
      </p>
    </div>

    <!-- 时间筛选 -->
    <div class="filter-bar">
      <el-radio-group v-model="selectedHours" size="default" @change="onFilterChange">
        <el-radio-button :value="1">1小时</el-radio-button>
        <el-radio-button :value="6">6小时</el-radio-button>
        <el-radio-button :value="24">24小时</el-radio-button>
        <el-radio-button :value="48">48小时</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 加载中 -->
    <div v-if="alertsStore.loading" class="loading-area">
      <el-icon :size="24" class="loading-icon"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <!-- 告警列表 -->
    <div v-else-if="alertsStore.items.length" class="alert-list">
      <AlertItem
        v-for="alert in alertsStore.items"
        :key="alert.id"
        :alert="alert"
        @click="goDevice(alert.device_id)"
      />
    </div>

    <!-- 空状态 -->
    <EmptyState
      v-else
      title="暂无告警"
      description="一切正常，设备运行良好"
    >
      <template #icon>
        <el-icon :size="48" color="var(--color-success)"><CircleCheckFilled /></el-icon>
      </template>
    </EmptyState>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Loading, CircleCheckFilled } from '@element-plus/icons-vue'
import { useAlertsStore } from '@/stores/alerts'
import AlertItem from '@/components/AlertItem.vue'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const alertsStore = useAlertsStore()
const selectedHours = ref(48)

async function loadAlerts() {
  await alertsStore.fetchAlerts(selectedHours.value)
}

function onFilterChange() {
  loadAlerts()
}

function goDevice(deviceId: string) {
  router.push(`/device/${deviceId}`)
}

onMounted(() => {
  loadAlerts()
})
</script>

<style scoped>
.page-header {
  margin-bottom: var(--space-lg);
}
.page-header h1 {
  font-size: 24px;
  font-weight: 700;
}
.page-header .subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: var(--space-xs);
}

.filter-bar {
  margin-bottom: var(--space-lg);
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

.alert-list {
  display: flex;
  flex-direction: column;
  max-width: 720px;
}
</style>
