<template>
  <div class="page">
    <h1>MQTT 消息查询</h1>
    <div class="filters">
      <el-input v-model="fDevice" placeholder="设备 ID" clearable style="width: 160px" @clear="load" />
      <el-select v-model="fType" placeholder="消息类型" clearable style="width: 140px" @change="load">
        <el-option label="GPS 定位 (gps)" value="gps" />
        <el-option label="慢遥测 (telemetry)" value="telemetry" />
        <el-option label="告警 (alert)" value="alert" />
        <el-option label="状态 (status)" value="status" />
      </el-select>
      <el-input v-model="fKeyword" placeholder="关键词搜索" clearable style="width: 200px" @clear="load" />
      <el-date-picker
        v-model="fTimeRange" type="datetimerange" range-separator="至"
        start-placeholder="开始时间" end-placeholder="结束时间"
        format="YYYY-MM-DD HH:mm:ss" value-format="YYYY-MM-DD HH:mm:ss"
        style="width: 380px"
        @change="load"
      />
      <el-button type="primary" @click="load" :loading="ld">
        <el-icon><Search /></el-icon> 查询
      </el-button>
    </div>

    <el-table :data="list" class="data-table" :default-sort="{ prop: 'upload_time', order: 'descending' }">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="upload_time" label="时间" width="180" sortable />
      <el-table-column prop="device_id" label="设备 ID" width="160" />
      <el-table-column prop="device_name" label="设备名称" width="140" />
      <el-table-column prop="message_type" label="类型" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="typeColor(row.message_type)">{{ row.message_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="raw_json" label="消息内容" min-width="400">
        <template #default="{ row }">
          <div class="json-cell">
            <code class="json">{{ formatJson(row.raw_json) }}</code>
            <el-button text size="small" @click="showDetail(row)" class="detail-btn">详情</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="page" v-model:page-size="ps" :total="total"
        :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next"
        @change="load"
      />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="dlg.visible" title="消息详情" width="600px" destroy-on-close>
      <div class="dlg-grid">
        <div><span class="dlg-key">ID</span><span>{{ dlg.row?.id }}</span></div>
        <div><span class="dlg-key">时间</span><span>{{ dlg.row?.upload_time }}</span></div>
        <div><span class="dlg-key">设备 ID</span><span>{{ dlg.row?.device_id }}</span></div>
        <div><span class="dlg-key">设备名称</span><span>{{ dlg.row?.device_name || '-' }}</span></div>
        <div><span class="dlg-key">消息类型</span><span>{{ dlg.row?.message_type }}</span></div>
      </div>
      <pre class="dlg-json">{{ dlg.row?.raw_json ? JSON.stringify(JSON.parse(dlg.row.raw_json), null, 2) : '{}' }}</pre>
      <template #footer>
        <el-button @click="dlg.visible = false">关闭</el-button>
        <el-button type="primary" @click="copyJson">复制 JSON</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { queryMessages, type MessageEntry } from '@/api/admin'

const list = ref<MessageEntry[]>([]); const total = ref(0)
const page = ref(1); const ps = ref(20)
const fDevice = ref(''); const fType = ref(''); const fKeyword = ref('')
const fTimeRange = ref<[string, string] | null>(null)
const ld = ref(false)

const dlg = reactive<{ visible: boolean; row: MessageEntry | null }>({ visible: false, row: null })

function typeColor(t: string): string {
  if (t === 'alert') return 'danger'
  if (t === 'gps') return ''
  if (t === 'telemetry') return 'success'
  if (t === 'status') return 'info'
  return ''
}

function formatJson(raw: string): string {
  try {
    const obj = JSON.parse(raw)
    return JSON.stringify(obj, null, 0)
  } catch {
    return raw.length > 120 ? raw.slice(0, 120) + '...' : raw
  }
}

function showDetail(row: MessageEntry) {
  dlg.row = row; dlg.visible = true
}

function copyJson() {
  if (!dlg.row?.raw_json) return
  try {
    const formatted = JSON.stringify(JSON.parse(dlg.row.raw_json), null, 2)
    navigator.clipboard.writeText(formatted)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function load() {
  ld.value = true
  try {
    const r = await queryMessages({
      page: page.value, page_size: ps.value,
      device_id: fDevice.value || undefined,
      message_type: fType.value || undefined,
      keyword: fKeyword.value || undefined,
      start_time: fTimeRange.value?.[0] || undefined,
      end_time: fTimeRange.value?.[1] || undefined,
    })
    list.value = r.data?.list || []; total.value = r.data?.total || 0
  } catch {} finally { ld.value = false }
}
onMounted(load)
</script>

<style scoped>
.page { width: 100% }
h1 { font-size: 24px; margin: 0 0 16px; color: #e2e6f0 }
.filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px }
.pager { margin-top: 16px; display: flex; justify-content: flex-end }

.json-cell { display: flex; align-items: flex-start; gap: 8px }
.json { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #99a0b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0 }
.detail-btn { flex-shrink: 0; padding: 0 4px; font-size: 12px; color: #409EFF }

/* 详情弹窗 */
.dlg-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; margin-bottom: 16px }
.dlg-key { display: inline-block; width: 70px; color: #99a0b8; font-size: 13px }
.dlg-json {
  background: #1a1e2c; border: 1px solid #333852; border-radius: 8px;
  padding: 16px; font-family: 'JetBrains Mono', monospace; font-size: 13px;
  color: #e2e6f0; max-height: 400px; overflow: auto; white-space: pre-wrap; word-break: break-all; margin: 0;
}
</style>

