<template>
  <div class="page">
    <h1>用户管理</h1>
    <div class="bar">
      <el-button type="primary" @click="load" :loading="ld"><el-icon><Refresh /></el-icon> 刷新</el-button>
    </div>
    <el-table :data="list" class="data-table">
      <el-table-column prop="user_id" label="用户名" min-width="200" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">{{ row.status === 1 ? '已启用' : '已禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="200">
        <template #default="{ row }">
          <el-button :type="row.status === 1 ? 'warning' : 'success'" size="small" @click="toggle(row)">
            {{ row.status === 1 ? '禁用' : '启用' }}
          </el-button>
          <el-button type="primary" size="small" @click="showPwd(row.user_id)">重置密码</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="pvd" title="重置用户密码" width="400px">
      <el-form @submit.prevent="resetPwd">
        <el-form-item label="新密码">
          <el-input v-model="np" type="password" placeholder="至少6位" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pvd = false">取消</el-button>
        <el-button type="primary" @click="resetPwd" :loading="pl">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { listUsers, toggleUserStatus, resetPassword } from '@/api/admin'
import type { UserInfo } from '@/types'

const list = ref<UserInfo[]>([])
const ld = ref(false)

async function load() {
  ld.value = true
  try { const r = await listUsers(); list.value = r.data?.users || [] } catch {} finally { ld.value = false }
}

async function toggle(row: UserInfo) {
  const action = row.status === 1 ? '禁用' : '启用'
  try { await ElMessageBox.confirm(`确认${action}用户 ${row.user_id}？`, '确认', { type: 'warning' }) } catch { return }
  try { await toggleUserStatus({ user_id: row.user_id, is_disabled: row.status === 1 }); ElMessage.success('操作完成'); await load() } catch {}
}

const pvd = ref(false); const pu = ref(''); const np = ref(''); const pl = ref(false)
function showPwd(uid: string) { pu.value = uid; np.value = ''; pvd.value = true }
async function resetPwd() {
  if (np.value.length < 6) { ElMessage.warning('密码至少6位'); return }
  pl.value = true
  try { await resetPassword({ user_id: pu.value, new_password: np.value }); ElMessage.success('密码已重置'); pvd.value = false } catch {} finally { pl.value = false }
}
onMounted(load)
</script>

<style scoped>
.page { width: 100% }
h1 { font-size: 24px; margin: 0 0 16px; color: #e2e6f0 }
.bar { margin-bottom: 16px }
</style>

<style>
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
  color: #a0a4b8 !important;
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
.data-table .el-table__header .resize-line {
  display: none !important;
}
</style>
