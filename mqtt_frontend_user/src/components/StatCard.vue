<template>
  <div class="stat-card" :style="{ background: bg }">
    <div class="stat-icon" v-if="icon">
      <el-icon :size="20"><component :is="icon" /></el-icon>
    </div>
    <div class="stat-content">
      <span class="stat-value">{{ value }}</span>
      <span class="stat-label">{{ label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  value: string | number
  label: string
  icon?: any
  bg?: string
}>()
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  min-width: 0;
}

.stat-icon {
  color: var(--text-on-gradient);
  opacity: 0.9;
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
  color: var(--text-on-gradient);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 2px;
}
</style>
