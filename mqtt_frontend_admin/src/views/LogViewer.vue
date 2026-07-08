<template>
  <div class="page">
    <h1>操作日志</h1>
    <div class="filters">
      <el-input v-model="fUser" placeholder="操作人" clearable style="width: 160px" />
      <el-select v-model="fAction" placeholder="操作类型" clearable style="width: 160px">
        <el-option v-for="a in actions" :key="a" :label="actionLabel(a)" :value="a" />
      </el-select>
      <el-button type="primary" @click="load" :loading="ld"><el-icon><Search /></el-icon> 查询</el-button>
    </div>
    <el-table :data="list" class="data-table" :default-sort="{ prop: 'created_at', order: 'descending' }">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="created_at" label="时间" width="180" sortable />
      <el-table-column prop="user_id" label="操作人" width="120" />
      <el-table-column prop="action" label="操作类型" width="130">
        <template #default="{ row }">
          <el-tag size="small" :type="tagType(row.action)">{{ actionLabel(row.action) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="target" label="操作对象" width="150" />
      <el-table-column prop="detail" label="详情" min-width="180">
        <template #default="{ row }">{{ row.detail || '-' }}</template>
      </el-table-column>
      <el-table-column prop="ip" label="来源IP" width="140" />
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="page" v-model:page-size="ps" :total="total"
        :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next"
        @change="load"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { queryLogs } from '@/api/admin'
import type { LogEntry } from '@/types'

const list = ref<LogEntry[]>([]); const total = ref(0)
const page = ref(1); const ps = ref(20)
const fUser = ref(''); const fAction = ref(''); const ld = ref(false)

const actions = ['login', 'register_device', 'delete_device', 'batch_register_device', 'create_user', 'batch_create_user', 'disable_user', 'enable_user', 'reset_pwd']

function actionLabel(a: string): string {
  const m: Record<string, string> = {
    login: '登录', register_device: '注册设备', delete_device: '删除设备',
    batch_register_device: '批量注册设备', create_user: '创建用户', batch_create_user: '批量创建用户',
    disable_user: '禁用用户', enable_user: '启用用户', reset_pwd: '重置密码',
  }
  return m[a] || a
}
function tagType(a: string): string {
  if (a.includes('delete') || a.includes('disable')) return 'danger'
  if (a.includes('create') || a.includes('register') || a.includes('enable')) return 'success'
  if (a.includes('reset')) return 'warning'
  return 'info'
}

async function load() {
  ld.value = true
  try {
    const r = await queryLogs({
      page: page.value, page_size: ps.value,
      user_id: fUser.value || undefined, action: fAction.value || undefined,
    })
    list.value = r.data?.list || []; total.value = r.data?.total || 0
  } catch {} finally { ld.value = false }
}
onMounted(load)
</script>

<style scoped>
.page { width: 100% }
h1 { font-size: 24px; margin: 0 0 16px; color: #e2e6f0 }
.filters { display: flex; gap: 8px; margin-bottom: 16px }
.pager { margin-top: 16px; display: flex; justify-content: flex-end }
</style>

