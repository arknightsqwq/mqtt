<template>
  <header class="app-header">
    <div class="header-left">
      <el-button v-if="showBack" :icon="ArrowLeft" text circle @click="goBack" />
      <slot name="left" />
    </div>
    <div class="header-center">
      <span class="header-title">{{ title }}</span>
      <span v-if="subtitle" class="header-subtitle">{{ subtitle }}</span>
    </div>
    <div class="header-right">
      <slot name="right" />
    </div>
  </header>
</template>

<script setup lang="ts">
import { ArrowLeft } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

defineProps<{
  title: string
  subtitle?: string
  showBack?: boolean
}>()

const router = useRouter()

function goBack() {
  router.back()
}
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px var(--space-md);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  position: sticky;
  top: 0;
  z-index: 100;
  min-height: 52px;
}

.header-left,
.header-right {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  min-width: 40px;
}

.header-center {
  flex: 1;
  text-align: center;
  overflow: hidden;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  display: block;
}

.header-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  display: block;
  margin-top: 2px;
}
</style>
