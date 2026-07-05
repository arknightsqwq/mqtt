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
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button type="danger" size="small" @click="del(row.device_id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { listDevices, deleteDevice } from '@/api/admin'
import type { DeviceInfo } from '@/types'

const list = ref<DeviceInfo[]>([])
const ld = ref(false)

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
</style>

<style>
/* 全局覆盖 Element Plus 表格样式 — 管理后台深色主题 */
.data-table {
  width: 100% !important;
  table-layout: auto !important;
  background: #212538 !important;
  border: 1px solid #333852 !important;
  border-radius: 8px;
  overflow: hidden;
}
.data-table .el-table__header-wrapper {
  background: #292d43 !important;
}
.data-table th.el-table__cell {
  background: #292d43 !important;
  color: #b0b4c8 !important;
  font-weight: 600 !important;
  font-size: 13px !important;
  border-bottom: 1px solid #333852 !important;
  border-right: none !important;
  padding: 0 !important;
}
.data-table th.el-table__cell .cell {
  padding: 14px 16px !important;
}
.data-table td.el-table__cell {
  background: #212538 !important;
  color: #e2e6f0 !important;
  border-bottom: 1px solid #333852 !important;
  border-right: none !important;
  padding: 0 !important;
}
.data-table td.el-table__cell .cell {
  padding: 12px 16px !important;
  font-size: 14px !important;
}
.data-table .el-table__body tr:hover > td.el-table__cell {
  background: #2d324a !important;
}
/* 禁止列宽拖动 */
.data-table .el-table__header .resize-line {
  display: none !important;
}
</style>
