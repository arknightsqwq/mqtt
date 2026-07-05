<template>
  <div class="device-config">
    <el-alert
      title="配置将下发到 device/{device_id}/config，请确认后再发送"
      type="warning" show-icon :closable="false" class="warning-alert"
    />

    <!-- 无配置模板 → 回退到 JSON 文本框 -->
    <div v-if="!configFields.length" class="send-card">
      <h3>发送配置</h3>
      <el-input v-model="configText" type="textarea" :rows="6"
        placeholder='请输入配置内容（JSON 格式），如 {"report_interval": 30, "alarm_threshold": 80}' size="large"
      />
      <el-button type="primary" size="large" :icon="Promotion" :loading="sending"
        class="send-btn" @click="handleSendJson"
      >下发配置</el-button>
    </div>

    <!-- 有配置模板 → 动态表单 -->
    <div v-else class="send-card">
      <h3>设备配置</h3>
      <div v-for="field in configFields" :key="field.key" class="config-field">
        <label class="field-label">{{ field.label }}</label>
        <div class="field-input-row">
          <!-- number 类型 -->
          <el-input-number
            v-if="field.type === 'number'"
            v-model="formValues[field.key]"
            :min="field.min"
            :max="field.max"
            :precision="2"
            size="large"
            controls-position="right"
            class="field-input"
          />
          <!-- select 类型 -->
          <el-select
            v-else-if="field.type === 'select'"
            v-model="formValues[field.key]"
            size="large"
            class="field-input"
          >
            <el-option v-for="opt in field.options" :key="opt" :label="opt" :value="opt" />
          </el-select>
          <!-- text 类型（默认） -->
          <el-input
            v-else
            v-model="formValues[field.key]"
            size="large"
            class="field-input"
          />
          <span v-if="field.unit" class="field-unit">{{ field.unit }}</span>
        </div>
      </div>
      <el-button type="primary" size="large" :icon="Promotion"
        :loading="sending" class="send-btn" @click="handleSendForm"
      >下发配置</el-button>
    </div>

    <!-- 配置历史 -->
    <div class="history-card">
      <div class="history-header">
        <h3>配置历史</h3>
        <el-button :icon="Delete" text size="small" @click="history = []">清空</el-button>
      </div>
      <div v-if="history.length" class="history-list">
        <div v-for="(item, i) in history" :key="i" class="history-item">
          <div class="history-content"><code>{{ item.config }}</code></div>
          <span class="history-time">{{ item.time }}</span>
        </div>
      </div>
      <div v-else class="history-empty"><span>暂无配置记录</span></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion, Delete } from '@element-plus/icons-vue'
import { sendConfig } from '@/api/device'
import { useDevicesStore } from '@/stores/devices'

interface ConfigField {
  key: string
  label: string
  type: 'text' | 'number' | 'select'
  unit?: string
  default?: any
  min?: number
  max?: number
  options?: string[]
}

const props = defineProps<{ deviceId: string }>()
const devicesStore = useDevicesStore()

const sending = ref(false)
const configText = ref('')
const history = ref<{ config: string; time: string }[]>([])
const formValues = reactive<Record<string, any>>({})

/** 从 config_json 解析配置项 */
const configFields = computed<ConfigField[]>(() => {
  const raw = devicesStore.currentConfig
  if (!raw || typeof raw !== 'object') return []
  return Object.entries(raw).map(([key, def]: [string, any]) => ({
    key,
    label: def?.label || key,
    type: def?.type === 'number' ? 'number' : def?.type === 'select' ? 'select' : 'text',
    unit: def?.unit || '',
    default: def?.default,
    min: def?.min,
    max: def?.max,
    options: def?.options || [],
  }))
})

/** 初始化表单值：优先用设备上报的 current_config，其次用模板 default */
function initFormValues(currentConfig: Record<string, any> | null) {
  for (const field of configFields.value) {
    const curVal = currentConfig?.[field.key]
    formValues[field.key] = curVal ?? field.default ?? ''
  }
}

/** 表单模式下发 */
async function handleSendForm() {
  const payload: Record<string, any> = {}
  for (const field of configFields.value) {
    payload[field.key] = formValues[field.key]
  }
  await doSend(JSON.stringify(payload))
}

/** JSON 模式下发 */
async function handleSendJson() {
  if (!configText.value.trim()) { ElMessage.warning('请输入配置内容'); return }
  try { JSON.parse(configText.value.trim()) }
  catch { ElMessage.warning('配置内容必须是合法 JSON'); return }
  await doSend(configText.value.trim())
}

async function doSend(jsonStr: string) {
  sending.value = true
  try {
    await sendConfig({ device_id: props.deviceId, command: jsonStr })
    ElMessage.success('配置已下发')
    history.value.unshift({ config: jsonStr, time: new Date().toLocaleString('zh-CN') })
  } catch { /* 错误已在拦截器中处理 */ }
  finally { sending.value = false }
}

// 从 store 同步 config_json
onMounted(async () => {
  const result = await devicesStore.fetchOneDevice(props.deviceId)
  if (result?.config_json) {
    devicesStore.currentConfig = result.config_json
    initFormValues(result?.current_config ?? null)
  }
})

watch(() => props.deviceId, () => {
  configText.value = ''
  history.value = []
  for (const k of Object.keys(formValues)) delete formValues[k]
  devicesStore.currentConfig = null
  devicesStore.fetchOneDevice(props.deviceId).then(result => {
    if (result?.config_json) {
      devicesStore.currentConfig = result.config_json
      initFormValues(result?.current_config ?? null)
    }
  })
})
</script>

<style scoped>
.device-config { display: flex; flex-direction: column; gap: var(--space-md) }
.warning-alert { border-radius: var(--radius-md) }
.send-card { background: var(--bg-card); border-radius: var(--radius-md); padding: var(--space-md); box-shadow: var(--shadow-sm) }
.send-card h3 { font-size: 15px; font-weight: 600; margin-bottom: var(--space-sm) }

.config-field { margin-bottom: var(--space-md) }
.field-label { display: block; font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-bottom: 6px }
.field-input-row { display: flex; align-items: center; gap: 10px }
.field-input { flex: 1 }
.field-unit { font-size: 13px; color: var(--text-muted); flex-shrink: 0; min-width: 24px }

.send-btn { width: 100%; height: 46px; font-size: 15px; margin-top: var(--space-md) }

.history-card { background: var(--bg-card); border-radius: var(--radius-md); padding: var(--space-md); box-shadow: var(--shadow-sm) }
.history-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-sm) }
.history-header h3 { font-size: 15px; font-weight: 600 }
.history-empty { display: flex; align-items: center; justify-content: center; padding: var(--space-lg); color: var(--text-muted); font-size: 13px }
.history-list { display: flex; flex-direction: column; gap: var(--space-sm) }
.history-item { padding: 10px 12px; background: var(--bg-input); border-radius: var(--radius-sm) }
.history-content { margin-bottom: 4px }
.history-content code { font-family: var(--font-mono); font-size: 12px; color: var(--text-primary); word-break: break-all }
.history-time { font-size: 11px; color: var(--text-muted) }
</style>
