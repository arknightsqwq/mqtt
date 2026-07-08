<template>
  <div class="trajectory-page">
    <!-- 控件栏 -->
    <div class="controls">
      <div class="control-row">
        <span class="control-label">时间范围</span>
        <el-select v-model="selectedHours" size="default" class="time-select" @change="onTimeRangeChange">
          <el-option :value="0.083" label="近 5 分钟" />
          <el-option :value="1" label="近 1 小时" />
          <el-option :value="6" label="近 6 小时" />
          <el-option :value="24" label="近 24 小时" />
          <el-option :value="168" label="近 7 天" />
        </el-select>
        <span v-if="isCustomZoom" class="custom-badge">自定义</span>
        <el-button v-if="isCustomZoom" size="default" @click="resetZoom">
          重置范围
        </el-button>
        <el-button :icon="Refresh" size="default" @click="fetchTrajectory" :loading="loading">
          刷新
        </el-button>
      </div>
    </div>

    <!-- 地图区域 -->
    <div class="map-section">
      <div v-if="hasData" class="map-wrapper">
        <div ref="mapRef" class="map-container" />
        <div class="map-info">
          <span class="map-coords">{{ filteredPoints.length }} 个轨迹点</span>
        </div>
      </div>
      <div v-else class="map-placeholder">
        <el-icon :size="32" color="var(--text-muted)"><MapLocation /></el-icon>
        <p>{{ loading ? '加载中...' : '暂无轨迹数据' }}</p>
        <span v-if="!loading" class="hint">该时间段内设备无 GPS 数据</span>
      </div>
    </div>

    <!-- 速度折线图（带 dataZoom 时间滑块） -->
    <div v-if="hasData && speedSeries.length" class="chart-section">
      <div ref="chartRef" class="chart-container" />
    </div>

    <!-- 统计栏 -->
    <div v-if="hasData" class="stats-bar">
      <div class="stat-item">
        <span class="stat-value">{{ totalDistance }}</span>
        <span class="stat-label">总里程 (km)</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ allPoints.length }}</span>
        <span class="stat-label">GPS 点数</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ avgSpeed }}</span>
        <span class="stat-label">平均速度 (km/h)</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ maxSpeed }}</span>
        <span class="stat-label">最高速度 (km/h)</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Refresh, MapLocation } from '@element-plus/icons-vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import * as echarts from 'echarts'
import { getDeviceTrajectory } from '@/api/device'
import type { TrajectoryPoint } from '@/types'

// 修复 Leaflet 默认图标路径
import iconUrl from 'leaflet/dist/images/marker-icon.png'
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png'
import shadowUrl from 'leaflet/dist/images/marker-shadow.png'
// @ts-expect-error Leaflet 内部属性 _getIconUrl 不在公开类型中
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl })

const props = defineProps<{
  deviceId: string
}>()

// ---- 状态 ----
const loading = ref(false)
const selectedHours = ref(24)
const allPoints = ref<TrajectoryPoint[]>([])
const filteredPoints = ref<TrajectoryPoint[]>([])
const isCustomZoom = ref(false)

const mapRef = ref<HTMLDivElement>()
const chartRef = ref<HTMLDivElement>()
let mapInstance: L.Map | null = null
let trajectoryLine: L.Polyline | null = null
let startMarker: L.CircleMarker | null = null
let endMarker: L.CircleMarker | null = null
let chartInstance: echarts.ECharts | null = null

const hasData = computed(() => allPoints.value.length > 0)

// ---- 统计 ----
const totalDistance = computed(() => {
  const pts = filteredPoints.value
  if (pts.length < 2) return '0.00'
  let dist = 0
  for (let i = 1; i < pts.length; i++) {
    dist += haversine(pts[i - 1].lat, pts[i - 1].lng, pts[i].lat, pts[i].lng)
  }
  return dist.toFixed(2)
})

const avgSpeed = computed(() => {
  const pts = filteredPoints.value.filter(p => p.speed != null)
  if (!pts.length) return '--'
  const sum = pts.reduce((s, p) => s + (p.speed ?? 0), 0)
  return (sum / pts.length).toFixed(1)
})

const maxSpeed = computed(() => {
  const speeds = filteredPoints.value.map(p => p.speed).filter(s => s != null) as number[]
  if (!speeds.length) return '--'
  return Math.max(...speeds).toFixed(1)
})

// ---- 速度折线图数据 ----
const speedSeries = computed(() => {
  const pts = allPoints.value.filter(p => p.speed != null)
  return [{
    name: '速度',
    points: pts.map(p => ({ time: p.time, value: p.speed ?? 0 })),
    color: '#FF6B35',
  }]
})

// ---- 工具函数 ----
function haversine(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLng = (lng2 - lng1) * Math.PI / 180
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

// ---- API ----
async function fetchTrajectory() {
  loading.value = true
  try {
    const res = await getDeviceTrajectory(props.deviceId, {
      hours: Math.round(selectedHours.value * 1000) / 1000,
      limit: 2000,
    })
    allPoints.value = res.data?.points ?? []
    filteredPoints.value = [...allPoints.value]
    await nextTick()
    initMap()
    initSpeedChart()
  } catch {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}

// ---- 地图 ----
function initMap() {
  if (!mapRef.value || !hasData.value) return
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
  }

  mapInstance = L.map(mapRef.value, {
    zoomControl: true,
    attributionControl: false,
  })

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
  }).addTo(mapInstance)

  drawTrajectory(filteredPoints.value)

  setTimeout(() => mapInstance?.invalidateSize(), 200)
}

function clearTrajectoryLayers() {
  if (trajectoryLine) { mapInstance?.removeLayer(trajectoryLine); trajectoryLine = null }
  if (startMarker) { mapInstance?.removeLayer(startMarker); startMarker = null }
  if (endMarker) { mapInstance?.removeLayer(endMarker); endMarker = null }
}

function drawTrajectory(pts: TrajectoryPoint[]) {
  if (!mapInstance || pts.length === 0) return

  clearTrajectoryLayers()

  const latlngs = pts.map(p => [p.lat, p.lng] as [number, number])

  // 折线
  trajectoryLine = L.polyline(latlngs, {
    color: '#FF6B35',
    weight: 4,
    opacity: 0.8,
  }).addTo(mapInstance)

  // 起点
  const first = latlngs[0]
  startMarker = L.circleMarker(first, {
    radius: 8,
    color: '#fff',
    fillColor: '#20BF6B',
    fillOpacity: 1,
    weight: 3,
  }).addTo(mapInstance)
  startMarker.bindTooltip(`起点<br/>${pts[0].time}`)

  // 终点
  if (pts.length > 1) {
    const last = latlngs[latlngs.length - 1]
    endMarker = L.circleMarker(last, {
      radius: 8,
      color: '#fff',
      fillColor: '#FF4757',
      fillOpacity: 1,
      weight: 3,
    }).addTo(mapInstance)
    endMarker.bindTooltip(`终点<br/>${pts[pts.length - 1].time}`)
  }

  // 自动适配视野
  mapInstance.fitBounds(latlngs, { padding: [30, 30] })
}

// ---- 速度折线图 ----
function initSpeedChart() {
  if (!chartRef.value || !speedSeries.value.length) return

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const s = speedSeries.value[0]
  const data = s.points.map(p => [new Date(p.time).getTime(), typeof p.value === 'string' ? parseFloat(p.value) : (p.value as number)])

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#eee',
      textStyle: { color: '#1A1A2E', fontSize: 13 },
      appendToBody: true,
    },
    grid: { left: 50, right: 16, top: 16, bottom: 52 },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: '#eee' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#ADB5BD',
        fontSize: 11,
        formatter: (v: number) => {
          const d = new Date(v)
          return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
        },
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'km/h',
      nameTextStyle: { color: '#ADB5BD', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f5f5f5', type: 'dashed' } },
      axisLabel: { color: '#ADB5BD', fontSize: 11 },
    },
    dataZoom: [
      {
        type: 'slider',
        xAxisIndex: 0,
        bottom: 8,
        height: 28,
        borderColor: '#eee',
        fillerColor: '#FF6B351F',
        handleStyle: { color: '#FF6B35', borderColor: '#FF6B35' },
        selectedDataBackground: {
          lineStyle: { color: '#FF6B35' },
          areaStyle: { color: '#FF6B3514' },
        },
        textStyle: { color: '#ADB5BD', fontSize: 10 },
      },
      {
        type: 'inside',
        xAxisIndex: 0,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        moveOnMouseWheel: false,
      },
    ],
    series: [{
      name: '速度',
      type: 'line',
      smooth: true,
      symbol: 'none',
      data,
      lineStyle: { color: '#FF6B35', width: 2 },
      areaStyle: { color: 'rgba(255,107,53,0.08)' },
    }],
  }, true)

  // 监听 dataZoom 事件，按时间范围过滤地图轨迹点
  interface DataZoomPayload { start?: number; end?: number; batch?: { start: number; end: number }[] }
  chartInstance.off('dataZoom')
  chartInstance.on('dataZoom', (params: unknown) => {
    // ECharts dataZoom 事件：用百分比反算时间范围
    const p = params as DataZoomPayload
    const item = p.batch ? p.batch[0] : p
    if (!item) return

    // start/end 是百分比 (0-100)，可靠；startValue/endValue 在 time 轴上可能缺失
    const startPct = item.start ?? 0
    const endPct = item.end ?? 100

    // 判断是否偏离全量范围（允许 ±1% 浮点误差）
    isCustomZoom.value = startPct > 1 || endPct < 99

    const times = allPoints.value.map(p => new Date(p.time).getTime())
    if (times.length === 0) return
    const minTime = times[0]
    const maxTime = times[times.length - 1]
    const range = maxTime - minTime || 1
    const startMs = minTime + (startPct / 100) * range
    const endMs = minTime + (endPct / 100) * range

    filteredPoints.value = allPoints.value.filter(p => {
      const t = new Date(p.time).getTime()
      return t >= startMs && t <= endMs
    })
    if (mapInstance) {
      drawTrajectory(filteredPoints.value)
    }
  })
}

function handleResize() {
  chartInstance?.resize()
  if (mapInstance) {
    setTimeout(() => mapInstance?.invalidateSize(), 100)
  }
}

// ---- 生命周期 ----
onMounted(() => {
  fetchTrajectory()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
  }
})

// ---- 时间范围切换 ----
function onTimeRangeChange() {
  isCustomZoom.value = false
  fetchTrajectory()
}

// ---- 重置缩放 ----
function resetZoom() {
  isCustomZoom.value = false
  filteredPoints.value = [...allPoints.value]
  if (chartInstance) {
    chartInstance.dispatchAction({ type: 'dataZoom', start: 0, end: 100 })
  }
  if (mapInstance) {
    drawTrajectory(filteredPoints.value)
  }
}
</script>

<style scoped>
.custom-badge {
  font-size: 12px;
  color: #FF6B35;
  background: rgba(255, 107, 53, 0.1);
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 500;
}
</style>

<style scoped>
.trajectory-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

/* ---- 控件栏 ---- */
.controls {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  box-shadow: var(--shadow-sm);
}

.control-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.control-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.time-select {
  width: 140px;
}

/* ---- 地图 ---- */
.map-section {
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.map-wrapper {
  position: relative;
}

.map-container {
  width: 100%;
  height: 420px;
  background: #e8eaed;
}

.map-info {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: var(--font-mono);
  pointer-events: none;
  z-index: 1000;
}

.map-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 200px;
  background: var(--bg-card);
  color: var(--text-muted);
  font-size: 14px;
}

.map-placeholder .hint {
  font-size: 12px;
  color: var(--text-muted);
}

/* ---- 速度图表 ---- */
.chart-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 12px 8px 4px;
  box-shadow: var(--shadow-sm);
}

.chart-container {
  width: 100%;
  height: 200px;
}

/* ---- 统计栏 ---- */
.stats-bar {
  display: flex;
  gap: 32px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 16px 20px;
  box-shadow: var(--shadow-sm);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
