<template>
  <nav class="bottom-nav">
    <div
      v-for="tab in tabs"
      :key="tab.path"
      class="nav-item"
      :class="{ active: currentPath === tab.path }"
      @click="navigate(tab.path)"
    >
      <el-icon :size="22">
        <component :is="tab.icon" />
      </el-icon>
      <span class="nav-label">{{ tab.label }}</span>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Monitor, Bell, User } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const tabs = [
  { path: '/main/devices', label: '设备', icon: Monitor },
  { path: '/main/alerts', label: '告警', icon: Bell },
  { path: '/main/profile', label: '我的', icon: User }
]

const currentPath = computed(() => route.path)

function navigate(path: string) {
  router.push(path)
}
</script>

<style scoped>
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 480px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 8px 0 env(safe-area-inset-bottom, 8px);
  z-index: 100;
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 4px 16px;
  color: var(--text-muted);
  cursor: pointer;
  transition: color 0.2s;
  min-width: 64px;
  min-height: 44px;
  justify-content: center;
}

.nav-item.active {
  color: var(--color-primary);
}

.nav-label {
  font-size: 11px;
  font-weight: 500;
}
</style>
