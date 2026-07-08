<template>
  <div class="page">
    <h1>设备管理</h1>
    <div class="bar">
      <el-button type="primary" @click="load" :loading="ld"><el-icon><Refresh /></el-icon> 刷新</el-button>
    </div>
    <el-table :data="list" class="data-table">
      <el-table-column prop="device_id" label="设备ID" min-width="140" />
      <el-table-column prop="device_name" label="名称" min-width="120" />
      <el-table-column prop="device_desc" label="描述" min-width="180">
        <template #default="{ row }">{{ row.device_desc || '-' }}</template>
      </el-table-column>
      <el-table-column prop="is_online" label="在线" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_online ? 'success' : 'info'" size="small">{{ row.is_online ? '在线' : '离线' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="bind_count" label="绑定数" width="90" />
      <el-table-column label="操作" width="230">
        <template #default="{ row }">
          <div class="action-btns">
            <el-button type="warning" size="small" @click="openConfig(row)">配置</el-button>
            <el-button size="small" @click="openFieldLabels(row)">标签</el-button>
            <el-button type="danger" size="small" @click="del(row.device_id)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 配置编辑弹窗 -->
    <el-dialog v-model="cfgVisible" title="编辑配置模板" width="600px" :close-on-click-modal="false">
      <p style="color:#99a0b8;font-size:13px;margin-bottom:8px">
        设备：<b>{{ cfgDeviceId }}</b> — 定义用户前端「配置页」的表单字段
      </p>
      <el-input v-model="cfgText" type="textarea" :rows="10"
        placeholder='JSON 格式，留空则清除配置模板'
      />
      <p v-if="cfgError" style="color:#F56C6C;font-size:12px;margin-top:4px">{{ cfgError }}</p>
      <template #footer>
        <el-button @click="cfgVisible = false">取消</el-button>
        <el-button type="primary" :loading="cfgSaving" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>

    <!-- 字段标签编辑弹窗 -->
    <el-dialog v-model="flVisible" title="编辑字段标签" width="600px" :close-on-click-modal="false">
      <p style="color:#99a0b8;font-size:13px;margin-bottom:8px">
        设备：<b>{{ flDeviceId }}</b> — 遥测字段的中文显示名称
      </p>
      <el-input v-model="flText" type="textarea" :rows="10"
        placeholder='JSON 格式，如 {"temperature":"温度","humidity":"湿度","lux":"光照度"}，留空则清除'
      />
      <p v-if="flError" style="color:#F56C6C;font-size:12px;margin-top:4px">{{ flError }}</p>
      <template #footer>
        <el-button @click="flVisible = false">取消</el-button>
        <el-button type="primary" :loading="flSaving" @click="saveFieldLabels">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { listDevices, deleteDevice, updateDeviceConfig, updateDeviceFieldLabels } from '@/api/admin'
import type { DeviceInfo } from '@/types'

const list = ref<DeviceInfo[]>([])
const ld = ref(false)

// ── 配置编辑 ──
const cfgVisible = ref(false)
const cfgText = ref('')
const cfgDeviceId = ref('')
const cfgError = ref('')
const cfgSaving = ref(false)

function openConfig(row: DeviceInfo) {
  cfgDeviceId.value = row.device_id
  cfgText.value = row.config_json ? JSON.stringify(row.config_json, null, 2) : ''
  cfgError.value = ''
  cfgVisible.value = true
}

async function saveConfig() {
  cfgError.value = ''
  let configJson: any = null
  if (cfgText.value.trim()) {
    try { configJson = JSON.parse(cfgText.value.trim()) }
    catch { cfgError.value = 'JSON 格式错误'; return }
  }
  cfgSaving.value = true
  try {
    await updateDeviceConfig(cfgDeviceId.value, configJson || {})
    // 更新本地列表中的 config_json
    const item = list.value.find(d => d.device_id === cfgDeviceId.value)
    if (item) (item as any).config_json = configJson
    ElMessage.success('配置已更新')
    cfgVisible.value = false
  } catch {} finally { cfgSaving.value = false }
}

// ── 字段标签编辑 ──
const flVisible = ref(false)
const flText = ref('')
const flDeviceId = ref('')
const flError = ref('')
const flSaving = ref(false)

function openFieldLabels(row: DeviceInfo) {
  flDeviceId.value = row.device_id
  flText.value = row.field_labels ? JSON.stringify(row.field_labels, null, 2) : ''
  flError.value = ''
  flVisible.value = true
}

async function saveFieldLabels() {
  flError.value = ''
  let fieldLabels: any = null
  if (flText.value.trim()) {
    try { fieldLabels = JSON.parse(flText.value.trim()) }
    catch { flError.value = 'JSON 格式错误'; return }
  }
  flSaving.value = true
  try {
    await updateDeviceFieldLabels(flDeviceId.value, fieldLabels || {})
    const item = list.value.find(d => d.device_id === flDeviceId.value)
    if (item) (item as any).field_labels = fieldLabels
    ElMessage.success('字段标签已更新')
    flVisible.value = false
  } catch {} finally { flSaving.value = false }
}

async function load() {
  ld.value = true
  try { const r = await listDevices(); list.value = r.data?.devices || [] } catch {} finally { ld.value = false }
}
async function del(id: string) {
  try { await ElMessageBox.confirm(`删除设备 ${id}？将同时清除绑定和数据。`, '警告', { type: 'warning', confirmButtonText: '确认删除' }) } catch { return }
  try { await deleteDevice(id); ElMessage.success('已删除'); list.value = list.value.filter(d => d.device_id !== id) } catch {}
}
onMounted(load)
</script>

<style scoped>
.page { width: 100% }
h1 { font-size: 24px; margin: 0 0 16px; color: #e2e6f0 }
.bar { margin-bottom: 16px }
.action-btns {
  display: flex;
  gap: 6px;
  flex-wrap: nowrap;
}
</style>

