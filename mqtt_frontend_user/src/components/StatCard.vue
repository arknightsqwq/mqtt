<template>
  <div class="stat-card" :style="cardStyle">
    <div class="stat-icon" v-if="icon">
      <el-icon :size="18"><component :is="icon" /></el-icon>
    </div>
    <div class="stat-content">
      <span class="stat-value">{{ value }}</span>
      <span class="stat-label">{{ label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  value: string | number
  label: string
  icon?: any
  color?: string
}>()

const cardStyle = computed(() => ({
  borderLeftColor: props.color || 'var(--color-primary)',
  backgroundColor: props.color ? `${props.color}0D` : undefined,
}))
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: var(--bg-card);
  border-left: 3px solid var(--color-primary);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  min-width: 0;
}

.stat-icon {
  color: var(--text-secondary);
  opacity: 0.7;
  flex-shrink: 0;
}

.stat-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
</style>
