<template>
  <div class="device-map">
    <div v-if="valid" class="map-wrapper">
      <div ref="mapRef" class="map-container" />
      <div class="map-info">
        <span class="map-coords">{{ latitude.toFixed(4) }}, {{ longitude.toFixed(4) }}</span>
      </div>
    </div>
    <div v-else class="map-placeholder">
      <el-icon :size="28" color="var(--text-muted)"><MapLocation /></el-icon>
      <span>暂无地图</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { MapLocation } from '@element-plus/icons-vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// 修复 Leaflet 默认图标在 Webpack/Vite 中的路径问题
import iconUrl from 'leaflet/dist/images/marker-icon.png'
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png'
import shadowUrl from 'leaflet/dist/images/marker-shadow.png'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl })

const props = defineProps<{
  latitude: number
  longitude: number
  deviceName: string
}>()

const mapRef = ref<HTMLDivElement>()
let mapInstance: L.Map | null = null

const valid = computed(() => {
  return (
    props.latitude != null &&
    props.longitude != null &&
    !isNaN(props.latitude) &&
    !isNaN(props.longitude) &&
    props.latitude >= -90 &&
    props.latitude <= 90 &&
    props.longitude >= -180 &&
    props.longitude <= 180
  )
})

function initMap() {
  if (!mapRef.value || !valid.value) return

  if (mapInstance) {
    mapInstance.remove()
  }

  mapInstance = L.map(mapRef.value, {
    center: [props.latitude, props.longitude],
    zoom: 15,
    zoomControl: true,
    attributionControl: false,
  })

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
  }).addTo(mapInstance)

  L.marker([props.latitude, props.longitude])
    .addTo(mapInstance)
    .bindPopup(`<b>${props.deviceName}</b><br/>${props.latitude.toFixed(4)}, ${props.longitude.toFixed(4)}`)
    .openPopup()

  // 延迟 invalidateSize 解决容器初始化时不可见的问题
  setTimeout(() => mapInstance?.invalidateSize(), 200)
}

onMounted(() => {
  initMap()
})

watch(() => [props.latitude, props.longitude], () => {
  if (mapInstance) {
    mapInstance.setView([props.latitude, props.longitude], mapInstance.getZoom())
    // 更新标记
    mapInstance.eachLayer((layer) => {
      if (layer instanceof L.Marker) {
        mapInstance!.removeLayer(layer)
      }
    })
    L.marker([props.latitude, props.longitude])
      .addTo(mapInstance)
      .bindPopup(`<b>${props.deviceName}</b><br/>${props.latitude.toFixed(4)}, ${props.longitude.toFixed(4)}`)
      .openPopup()
  } else {
    initMap()
  }
})

onBeforeUnmount(() => {
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
  }
})
</script>

<style scoped>
.device-map {
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  flex: 1;
  display: flex;
  flex-direction: column;
}

.map-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}

.map-container {
  flex: 1;
  min-height: 300px;
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
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  pointer-events: none;
}

.map-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 120px;
  background: var(--bg-card);
  color: var(--text-muted);
  font-size: 13px;
}
</style>
