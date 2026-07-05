<template>
  <div class="alert-item" @click="$emit('click')">
    <div class="alert-icon" :class="severity">
      <el-icon :size="18">
        <WarningFilled v-if="severity === 'high'" />
        <Bell v-else />
      </el-icon>
    </div>
    <div class="alert-body">
      <div class="alert-header">
        <span class="alert-device">{{ alert.device_name || alert.device_id }}</span>
        <span class="alert-time">{{ formatTime(alert.upload_time) }}</span>
      </div>
      <p class="alert-message">{{ parsedMessage }}</p>
      <!-- 录音播放 -->
      <div v-if="recordingId" class="alert-recording">
        <el-button
          :icon="playing ? VideoPause : Headset"
          :type="playing ? 'danger' : 'success'"
          size="small"
          round
          :loading="loadingAudio"
          @click.stop="togglePlay"
        >
          {{ playing ? '停止' : '播放录音' }}
        </el-button>
      </div>
    </div>
    <el-icon :size="14" class="alert-arrow"><ArrowRight /></el-icon>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { WarningFilled, Bell, ArrowRight, Headset, VideoPause } from '@element-plus/icons-vue'
import { fetchRecording } from '@/api/device'
import type { AlertItemData } from '@/types'

const props = defineProps<{
  alert: AlertItemData
}>()

defineEmits<{
  click: []
}>()

const playing = ref(false)
const loadingAudio = ref(false)
let audio: HTMLAudioElement | null = null

const severity = computed(() => {
  try {
    const obj = JSON.parse(props.alert.raw_json)
    return obj.severity || obj.level || 'normal'
  } catch {
    return 'normal'
  }
})

const recordingId = computed(() => {
  try {
    const obj = JSON.parse(props.alert.raw_json)
    return obj.recording_db_id ?? null
  } catch {
    return null
  }
})

const parsedMessage = computed(() => {
  try {
    const obj = JSON.parse(props.alert.raw_json)
    return obj.message || obj.msg || obj.alert || props.alert.raw_json
  } catch {
    return props.alert.raw_json
  }
})

function formatTime(time: string) {
  const now = new Date()
  const t = new Date(time.replace(' ', 'T'))
  const diff = now.getTime() - t.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  return time.substring(5, 16)
}

async function togglePlay() {
  if (playing.value) {
    audio?.pause()
    audio = null
    playing.value = false
    return
  }
  if (!recordingId.value) return
  loadingAudio.value = true
  try {
    const blob = await fetchRecording(props.alert.device_id, recordingId.value)
    const url = URL.createObjectURL(blob)
    audio = new Audio(url)
    audio.onended = () => { playing.value = false; audio = null }
    await audio.play()
    playing.value = true
  } catch {
    // ignore
  } finally {
    loadingAudio.value = false
  }
}
</script>

<style scoped>
.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px var(--space-md);
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-sm);
  cursor: pointer;
  transition: background 0.2s;
  box-shadow: var(--shadow-sm);
}

.alert-item:hover {
  background: var(--bg-card-hover);
}

.alert-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.alert-icon.high {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}
.alert-icon.normal,
.alert-icon.low {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.alert-body {
  flex: 1;
  min-width: 0;
}

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.alert-device {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.alert-time {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
  margin-left: 8px;
}

.alert-message {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.alert-recording {
  margin-top: 8px;
}

.alert-arrow {
  color: var(--text-muted);
  align-self: center;
  flex-shrink: 0;
}
</style>
