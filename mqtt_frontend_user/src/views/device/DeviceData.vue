<template>
  <div class="device-data">
    <!-- 控件栏 -->
    <div class="controls">
      <div class="control-row field-row">
        <span class="control-label">数据字段</span>
        <el-select
          v-model="selectedFields"
          placeholder="选择字段（可多选）"
          size="default"
          multiple
          class="field-select"
          @change="onFieldChange"
        >
          <el-option
            v-for="f in availableFields"
            :key="f"
            :label="f"
            :value="f"
          />
        </el-select>
      </div>
      <div class="control-row time-row">
        <span class="control-label">时间范围</span>
        <el-select v-model="selectedHours" size="default" class="time-select" @change="onParamChange">
          <el-option :value="1" label="近 1 小时" />
          <el-option :value="6" label="近 6 小时" />
          <el-option :value="24" label="近 24 小时" />
          <el-option :value="168" label="近 7 天" />
        </el-select>
      </div>
      <el-button :icon="Refresh" size="default" @click="onParamChange" class="refresh-btn" :loading="loading">
        刷新
      </el-button>
    </div>

    <!-- 空状态 -->
    <div v-if="!selectedFields.length" class="chart-placeholder">
      <span>请选择要查看的数据字段</span>
    </div>

    <!-- 每个选中字段一个独立图表（按 availableFields 固定顺序排列） -->
    <div
      v-for="c in orderedCharts"
      :key="c.field"
      class="chart-card"
    >
      <div class="chart-card-header">
        <span class="chart-dot" :style="{ background: palette[c.colorIdx % palette.length] }" />
        <span class="chart-field-name">{{ c.field }}</span>
        <span class="chart-field-unit" v-if="c.field === 'battery'">(%)</span>
        <span class="chart-field-unit" v-else-if="c.field === 'temperature'">(°C)</span>
        <span class="chart-field-unit" v-else-if="c.field === 'humidity' || c.field === 'rssi'">(%)</span>
        <span class="chart-field-unit" v-else-if="c.field === 'pressure'">(hPa)</span>
        <span class="chart-field-unit" v-else-if="c.field === 'pm25' || c.field === 'pm10'">(µg/m³)</span>
        <span class="chart-field-unit" v-else-if="c.field === 'co2'">(ppm)</span>
      </div>
      <TimeSeriesChart
        :series="[{
          name: c.field,
          points: fieldDataMap[c.field] || [],
          color: palette[c.colorIdx % palette.length]
        }]"
        :smooth="true"
        height="300px"
        :merge="isMergeUpdate"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { getDeviceTimeSeries } from '@/api/device'
import TimeSeriesChart from '@/components/charts/TimeSeriesChart.vue'
import { usePolling } from '@/composables/usePolling'
import type { TimeSeriesPoint } from '@/types'

const props = defineProps<{
  deviceId: string
  latestRaw?: string | null
}>()

const palette = [
  '#FF6B35', '#00C48C', '#4A90D9', '#FFD93D',
  '#FF4757', '#A55EEA', '#2ED573', '#FF6348',
]

const selectedFields = ref<string[]>([])
const selectedHours = ref(24)
const loading = ref(false)
const fieldDataMap = ref<Record<string, TimeSeriesPoint[]>>({})
const isMergeUpdate = ref(false)

/** 按 availableFields 固定顺序排列 + 固定颜色索引（原始位置，不受勾选组合影响） */
const orderedCharts = computed(() => {
  const all = availableFields.value
  const set = new Set(selectedFields.value)
  return all
    .map((f, idx) => set.has(f) ? { field: f, colorIdx: idx } : null)
    .filter(Boolean) as { field: string; colorIdx: number }[]
})
const availableFields = computed(() => {
  if (!props.latestRaw) return ['value']
  try {
    const obj = JSON.parse(props.latestRaw)
    if (typeof obj !== 'object' || obj === null) return ['value']
    const keys = Object.keys(obj).filter(k => typeof obj[k] === 'number')
    return keys.length ? keys.sort() : ['value']
  } catch {
    return ['value']
  }
})

function initFields() {
  const fields = availableFields.value
  if (fields.length && !selectedFields.value.length) {
    selectedFields.value = [fields[0]]
  }
}
initFields()

/** 拉取所有选中字段的时序数据 */
async function fetchAllSeries() {
  const id = props.deviceId
  const fields = selectedFields.value.slice()
  if (!id || !fields.length) return

  loading.value = true
  try {
    const results = await Promise.allSettled(
      fields.map(f =>
        getDeviceTimeSeries(id, {
          field: f,
          hours: selectedHours.value,
          limit: 500
        })
      )
    )

    if (id !== props.deviceId) return

    const map: Record<string, TimeSeriesPoint[]> = {}
    results.forEach((r, i) => {
      const field = fields[i]
      let points: TimeSeriesPoint[] = []
      if (r.status === 'fulfilled' && r.value.code === 200 && r.value.data) {
        points = r.value.data.points || []
      }
      map[field] = points
    })
    fieldDataMap.value = map
  } finally {
    if (id === props.deviceId) loading.value = false
  }
}

function onFieldChange() {
  isMergeUpdate.value = false
  fetchAllSeries()
}

function onParamChange() {
  isMergeUpdate.value = false
  fetchAllSeries()
}

async function pollRefresh() {
  if (!Object.keys(fieldDataMap.value).length) return
  isMergeUpdate.value = true
  await fetchAllSeries()
}

watch(() => props.deviceId, () => {
  fieldDataMap.value = {}
  isMergeUpdate.value = false
  initFields()
  fetchAllSeries()
}, { immediate: true })

const polling = usePolling(pollRefresh, 10000)
polling.start()

onUnmounted(() => {
  polling.stop()
})
</script>

<style scoped>
.device-data {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.controls {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
  align-items: center;
}

.control-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

.control-label {
  font-size: 13px;
  color: var(--text-muted);
  white-space: nowrap;
  flex-shrink: 0;
}

.field-select {
  width: 260px;
}

.time-select {
  width: 150px;
}

.refresh-btn {
  flex-shrink: 0;
  align-self: center;
}

/* 图表卡片 */
.chart-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: var(--space-md);
}

.chart-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.chart-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.chart-field-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.chart-field-unit {
  font-size: 12px;
  color: var(--text-muted);
}

.chart-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  color: var(--text-muted);
  font-size: 14px;
}
</style>
