<template>
  <div class="page">
    <h1>注册设备</h1>

    <!-- 单个注册 -->
    <div class="card">
      <div class="card-title">单个注册</div>
      <el-form ref="fr" :model="f" :rules="r" label-width="90px" @submit.prevent="reg">
        <el-form-item label="设备 ID" prop="device_id">
          <el-input v-model="f.device_id" placeholder="设备唯一标识（对应 EMQX 设备账号）" />
        </el-form-item>
        <el-form-item label="设备名称" prop="device_name">
          <el-input v-model="f.device_name" placeholder="设备名称" />
        </el-form-item>
        <el-form-item label="设备描述">
          <el-input v-model="f.device_desc" type="textarea" :rows="2" placeholder="安装位置、型号等（可选）" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="ld">
            <el-icon><CirclePlus /></el-icon> 注册
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 批量导入 -->
    <div class="card">
      <div class="card-title">批量导入</div>
      <div
        class="dropzone"
        :class="{ over: dragging }"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="handleDrop"
      >
        <el-icon :size="40"><UploadFilled /></el-icon>
        <p>拖拽 CSV 或 JSON 文件到此处</p>
        <p class="hint">或点击下方选择文件</p>
        <input type="file" ref="fileInput" accept=".csv,.json" @change="handleFile" style="display:none" />
        <el-button @click="($refs.fileInput as HTMLInputElement).click()">选择文件</el-button>
      </div>
      <div v-if="preview.length" class="preview">
        <div class="card-title">预览（{{ preview.length }} 条）</div>
        <el-table :data="preview" size="small" max-height="200">
          <el-table-column prop="device_id" label="设备ID" width="160" />
          <el-table-column prop="device_name" label="名称" min-width="150" />
          <el-table-column prop="device_desc" label="描述" min-width="180" />
        </el-table>
        <el-button type="success" @click="batchReg" :loading="bld" style="margin-top:12px">
          <el-icon><Upload /></el-icon> 批量注册
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { CirclePlus, UploadFilled, Upload } from '@element-plus/icons-vue'
import { registerDevice, batchRegisterDevices } from '@/api/admin'
import type { FormInstance, FormRules } from 'element-plus'

const fr = ref<FormInstance>()
const ld = ref(false)
const bld = ref(false)
const f = reactive({ device_id: '', device_name: '', device_desc: '' })
const r: FormRules = {
  device_id: [{ required: true, message: '请输入设备ID' }],
  device_name: [{ required: true, message: '请输入设备名称' }],
}

// ── 单个注册 ──
async function reg() {
  if (!await fr.value?.validate().catch(() => false)) return
  ld.value = true
  try {
    await registerDevice({ device_id: f.device_id, device_name: f.device_name, device_desc: f.device_desc })
    ElMessage.success('注册成功')
    f.device_id = ''; f.device_name = ''; f.device_desc = ''
    fr.value?.resetFields()
  } catch {} finally { ld.value = false }
}

// ── 批量导入 ──
const fileInput = ref<HTMLInputElement>()
const dragging = ref(false)
const preview = ref<{ device_id: string; device_name: string; device_desc: string }[]>([])

function parseCSV(text: string) {
  const lines = text.split('\n').filter(l => l.trim())
  if (lines.length < 2) { ElMessage.error('CSV 至少需要表头 + 1 行数据'); return }
  const headers = lines[0].split(',').map(h => h.trim().toLowerCase())
  const idIdx = headers.indexOf('device_id')
  const nameIdx = headers.indexOf('device_name')
  const descIdx = headers.indexOf('device_desc')
  if (idIdx < 0 || nameIdx < 0) { ElMessage.error('CSV 需包含 device_id, device_name 列'); return }
  const items: typeof preview.value = []
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(',').map(c => c.trim().replace(/^"(.*)"$/, '$1'))
    if (cols[idIdx]) items.push({ device_id: cols[idIdx], device_name: cols[nameIdx] || cols[idIdx], device_desc: descIdx >= 0 ? (cols[descIdx] || '') : '' })
  }
  preview.value = items
}

function parseJSON(text: string) {
  try {
    const arr = JSON.parse(text)
    if (!Array.isArray(arr)) { ElMessage.error('JSON 必须是数组格式'); return }
    const items: typeof preview.value = []
    for (const d of arr) {
      if (!d.device_id || !d.device_name) { ElMessage.warning(`跳过缺少 device_id/device_name 的条目`); continue }
      items.push({ device_id: String(d.device_id), device_name: String(d.device_name), device_desc: d.device_desc ? String(d.device_desc) : '' })
    }
    preview.value = items
  } catch { ElMessage.error('JSON 格式解析失败') }
}

function handleDrop(e: DragEvent) {
  dragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) readFile(file)
}
function handleFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) readFile(file)
}
function readFile(file: File) {
  const reader = new FileReader()
  reader.onload = (e) => {
    const text = e.target?.result as string
    if (file.name.endsWith('.json')) parseJSON(text)
    else parseCSV(text)
  }
  reader.readAsText(file)
}

async function batchReg() {
  if (!preview.value.length) { ElMessage.warning('没有可导入的数据'); return }
  bld.value = true
  try {
    const r = await batchRegisterDevices(preview.value)
    if (r.code === 200) {
      ElMessage.success(`导入完成：成功 ${r.data?.success} 台, 跳过 ${r.data?.skipped} 台`)
      preview.value = []
    }
  } catch {} finally { bld.value = false }
}
</script>

<style scoped>
.page { width: 100% }
h1 { font-size: 24px; margin: 0 0 24px; color: #e2e6f0; text-align: center }

.card {
  background: #23273a; border: 1px solid rgba(255,255,255,0.07); border-radius: 14px;
  padding: 28px; margin-bottom: 20px;
}
.card-title { color: #b0b4c8; font-size: 14px; font-weight: 600; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.06) }

.dropzone {
  border: 2px dashed rgba(64,158,255,0.3); border-radius: 12px;
  padding: 36px; text-align: center; cursor: pointer; transition: all 0.3s;
  color: #99a0b8;
}
.dropzone.over { border-color: #409EFF; background: rgba(64,158,255,0.05) }
.dropzone p { margin: 8px 0 0; font-size: 14px }
.dropzone .hint { font-size: 12px; color: #666 }
.preview { margin-top: 16px }

:deep(.el-input__wrapper) { background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.08); box-shadow: none }
:deep(.el-input__inner) { color: #e2e6f0 }
:deep(.el-textarea__inner) { background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.08); color: #e2e6f0 }
</style>
