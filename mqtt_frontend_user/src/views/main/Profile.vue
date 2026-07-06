<template>
  <div class="profile-page">
    <h1 class="page-title">个人中心</h1>

    <div class="profile-grid">
      <!-- 左栏 -->
      <div class="left-col">
        <!-- 用户信息卡片 -->
        <div class="info-card">
          <div class="avatar">{{ authStore.userId.charAt(0).toUpperCase() }}</div>
          <div class="info-text">
            <h2>{{ authStore.userId }}</h2>
            <p>设备监测系统用户</p>
          </div>
        </div>

        <!-- 已绑定设备 -->
        <div class="section-card">
          <div class="card-header">
            <h3>已绑定设备</h3>
            <el-button :icon="Plus" size="small" type="primary" @click="showBindDialog = true">
              绑定设备
            </el-button>
          </div>

          <div v-if="authStore.bindDevices.length" class="device-list">
            <div
              v-for="device in authStore.bindDevices"
              :key="device.device_id"
              class="device-row"
            >
              <div class="device-main" @click="goDevice(device.device_id)">
                <div class="device-icon">
                  <el-icon :size="20"><Monitor /></el-icon>
                </div>
                <div class="device-info">
                  <span class="device-name">{{ device.device_name || device.device_id }}</span>
                  <span class="device-id">{{ device.device_id }}</span>
                </div>
              </div>
              <el-button
                :icon="Close"
                text
                size="small"
                class="unbind-btn"
                @click.stop="handleUnbind(device.device_id)"
              />
            </div>
          </div>

          <div v-else class="empty-box">
            <p>暂无绑定设备</p>
            <span>点击右上角按钮绑定</span>
          </div>
        </div>
      </div>

      <!-- 右栏 -->
      <div class="right-col">
        <!-- 账号操作 -->
        <div class="section-card">
          <div class="card-header">
            <h3>账号操作</h3>
          </div>
          <div class="action-list">
            <div class="action-row" @click="showBindDialog = true">
              <el-icon :size="18"><Plus /></el-icon>
              <span>绑定新设备</span>
              <el-icon :size="14" class="arrow"><ArrowRight /></el-icon>
            </div>
            <div class="action-row danger" @click="handleLogout">
              <el-icon :size="18"><SwitchButton /></el-icon>
              <span>退出登录</span>
              <el-icon :size="14" class="arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 绑定设备对话框 -->
    <el-dialog v-model="showBindDialog" title="绑定设备" width="420px">
      <el-form ref="bindFormRef" :model="bindForm" :rules="bindRules" @keyup.enter="handleBind">
        <el-form-item prop="device_id">
          <el-input v-model="bindForm.device_id" placeholder="请输入设备 ID" size="large" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBindDialog = false">取消</el-button>
        <el-button type="primary" :loading="bindLoading" @click="handleBind">确认绑定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Close, SwitchButton, ArrowRight, Monitor } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useDevicesStore } from '@/stores/devices'

const router = useRouter()
const authStore = useAuthStore()
const devicesStore = useDevicesStore()

const showBindDialog = ref(false)
const bindLoading = ref(false)
const bindFormRef = ref<FormInstance>()
const bindForm = reactive({ device_id: '' })
const bindRules: FormRules = {
  device_id: [{ required: true, message: '请输入设备 ID', trigger: 'blur' }]
}

function goDevice(id: string) {
  router.push(`/device/${id}`)
}

async function handleUnbind(id: string) {
  try {
    await ElMessageBox.confirm(`确定解绑设备 "${id}"？`, '确认解绑', {
      type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消'
    })
    await devicesStore.unbindDevice(id)
    authStore.setBindDevices(authStore.bindDevices.filter(d => d.device_id !== id))
    ElMessage.success('已解绑')
  } catch { /* 取消 */ }
}

async function handleBind() {
  const valid = await bindFormRef.value?.validate().catch(() => false)
  if (!valid) return
  bindLoading.value = true
  try {
    await devicesStore.bindDevice(bindForm.device_id)
    ElMessage.success('绑定成功')
    authStore.bindDevices.push({
      device_id: bindForm.device_id,
      device_name: bindForm.device_id,
      device_desc: null
    })
    showBindDialog.value = false
    bindForm.device_id = ''
  } catch { /* handled */ } finally {
    bindLoading.value = false
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出确认', {
      type: 'warning', confirmButtonText: '退出', cancelButtonText: '取消'
    })
    await authStore.logout()
    router.push('/login')
  } catch { /* 取消 */ }
}
</script>

<style scoped>
.page-title {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: var(--space-lg);
}

.profile-grid {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: var(--space-lg);
  align-items: start;
}

@media (max-width: 900px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}

/* ===== 卡片通用 ===== */
.section-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.card-header h3 {
  font-size: 15px;
  font-weight: 600;
}

/* ===== 用户信息卡片 ===== */
.info-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px;
  background: var(--gradient-welcome);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-lg);
  box-shadow: var(--shadow-glow-orange);
}

.avatar {
  width: 56px;
  height: 56px;
  background: rgba(255,255,255,0.3);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  border: 3px solid rgba(255,255,255,0.5);
  flex-shrink: 0;
}

.info-text h2 {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
}
.info-text p {
  font-size: 13px;
  color: rgba(255,255,255,0.7);
  margin-top: 2px;
}

/* ===== 设备列表 ===== */
.device-list {
  display: flex;
  flex-direction: column;
}

.device-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid rgba(0,0,0,0.04);
}
.device-row:last-child {
  border-bottom: none;
}

.device-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  cursor: pointer;
  min-width: 0;
  padding: 4px 0;
}

.device-icon {
  width: 40px;
  height: 40px;
  background: var(--color-primary-bg);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  flex-shrink: 0;
}

.device-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.device-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.device-id {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  margin-top: 1px;
}

.unbind-btn {
  color: var(--text-muted);
  flex-shrink: 0;
}
.unbind-btn:hover {
  color: var(--color-danger);
}

.empty-box {
  text-align: center;
  padding: var(--space-lg);
  color: var(--text-muted);
  font-size: 14px;
}
.empty-box span {
  font-size: 12px;
}

/* ===== 操作列表 ===== */
.action-list {
  display: flex;
  flex-direction: column;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-primary);
  font-size: 14px;
  transition: background 0.15s;
}
.action-row:hover {
  background: var(--bg-card-hover);
}

.action-row .arrow {
  margin-left: auto;
  color: var(--text-muted);
}

.action-row.danger {
  color: var(--color-danger);
}
.action-row.danger:hover {
  background: var(--color-danger-bg);
}
</style>
