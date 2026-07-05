<template>
  <div class="page">
    <h1>创建用户</h1>

    <!-- 单个创建 -->
    <div class="card">
      <div class="card-title">单个创建</div>
      <el-form ref="fr" :model="f" :rules="r" label-width="90px" @submit.prevent="create">
        <el-form-item label="用户名" prop="user_id">
          <el-input v-model="f.user_id" placeholder="用户登录账号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="f.pwd" type="password" placeholder="留空则默认为 123456" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="ld">
            <el-icon><User /></el-icon> 创建
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
        <p class="hint">CSV 表头: user_id,password（password 可选，默认 123456）</p>
        <input type="file" ref="fileInput" accept=".csv,.json" @change="handleFile" style="display:none" />
        <el-button @click="($refs.fileInput as HTMLInputElement).click()">选择文件</el-button>
      </div>
      <div v-if="preview.length" class="preview">
        <div class="card-title">预览（{{ preview.length }} 条）</div>
        <el-table :data="preview" size="small" max-height="200">
          <el-table-column prop="user_id" label="用户名" width="200" />
          <el-table-column prop="new_password" label="密码" min-width="150">
            <template #default="{ row }">{{ row.new_password || '123456（默认）' }}</template>
          </el-table-column>
        </el-table>
        <el-button type="success" @click="batchCreate" :loading="bld" style="margin-top:12px">
          <el-icon><Upload /></el-icon> 批量创建
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { User, UploadFilled, Upload } from '@element-plus/icons-vue'
import { createUser, batchCreateUsers } from '@/api/admin'
import type { FormInstance, FormRules } from 'element-plus'

const fr = ref<FormInstance>()
const ld = ref(false)
const bld = ref(false)
const f = reactive({ user_id: '', pwd: '' })
const r: FormRules = {
  user_id: [{ required: true, message: '请输入用户名' }, { min: 2, max: 50, message: '2-50字符' }],
}

// ── 单个创建 ──
async function create() {
  if (!await fr.value?.validate().catch(() => false)) return
  ld.value = true
  try {
    const p: any = { user_id: f.user_id }; if (f.pwd) p.new_password = f.pwd
    await createUser(p)
    ElMessage.success('创建成功')
    f.user_id = ''; f.pwd = ''
    fr.value?.resetFields()
  } catch {} finally { ld.value = false }
}

// ── 批量导入 ──
const fileInput = ref<HTMLInputElement>()
const dragging = ref(false)
const preview = ref<{ user_id: string; new_password?: string }[]>([])

function parseCSV(text: string) {
  const lines = text.split('\n').filter(l => l.trim())
  if (lines.length < 2) { ElMessage.error('CSV 至少需要表头 + 1 行数据'); return }
  const headers = lines[0].split(',').map(h => h.trim().toLowerCase())
  const idIdx = headers.indexOf('user_id')
  const pwdIdx = headers.indexOf('password')
  if (idIdx < 0) { ElMessage.error('CSV 需包含 user_id 列'); return }
  const items: typeof preview.value = []
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(',').map(c => c.trim().replace(/^"(.*)"$/, '$1'))
    if (cols[idIdx]) items.push({ user_id: cols[idIdx], new_password: pwdIdx >= 0 ? (cols[pwdIdx] || '123456') : '123456' })
  }
  preview.value = items
}

function parseJSON(text: string) {
  try {
    const arr = JSON.parse(text)
    if (!Array.isArray(arr)) { ElMessage.error('JSON 必须是数组格式'); return }
    const items: typeof preview.value = []
    for (const u of arr) {
      if (!u.user_id) { ElMessage.warning('跳过缺少 user_id 的条目'); continue }
      items.push({ user_id: String(u.user_id), new_password: u.password ? String(u.password) : undefined })
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

async function batchCreate() {
  if (!preview.value.length) { ElMessage.warning('没有可导入的数据'); return }
  bld.value = true
  try {
    const r = await batchCreateUsers(preview.value)
    if (r.code === 200) {
      ElMessage.success(`导入完成：成功 ${r.data?.success} 个, 跳过 ${r.data?.skipped} 个`)
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
</style>
