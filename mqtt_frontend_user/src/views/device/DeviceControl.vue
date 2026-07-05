<template>
  <div class="device-control">
    <!-- 警告提示 -->
    <el-alert
      title="指令将直接下发到设备，请确认后再发送"
      type="warning"
      show-icon
      :closable="false"
      class="warning-alert"
    />

    <!-- 发送指令 -->
    <div class="send-card">
      <h3>发送指令</h3>
      <el-input
        v-model="command"
        type="textarea"
        :rows="4"
        placeholder="请输入指令内容（JSON 格式或纯文本），具体格式取决于目标设备"
        size="large"
      />
      <el-button
        type="primary"
        size="large"
        :icon="Promotion"
        :loading="sending"
        class="send-btn"
        @click="handleSend"
      >
        下发指令
      </el-button>
    </div>

    <!-- 指令历史 -->
    <div class="history-card">
      <div class="history-header">
        <h3>指令历史</h3>
        <el-button :icon="Refresh" text size="small" @click="loadHistory">刷新</el-button>
      </div>
      <div v-if="loading" class="history-loading">
        <el-icon :size="20" class="loading-icon"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      <div v-else-if="history.length" class="history-list">
        <div v-for="(item, i) in history" :key="i" class="history-item">
          <div class="history-content">
            <code>{{ item.command }}</code>
          </div>
          <span class="history-time">{{ item.time }}</span>
        </div>
      </div>
      <div v-else class="history-empty">
        <span>暂无指令记录</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion, Refresh, Loading } from '@element-plus/icons-vue'
import { sendCommand, queryDeviceData } from '@/api/device'

const props = defineProps<{
  deviceId: string
}>()

const command = ref('')
const sending = ref(false)
const loading = ref(false)
const history = ref<{ command: string; time: string }[]>([])

/** 发送指令 */
async function handleSend() {
  if (!command.value.trim()) {
    ElMessage.warning('请输入指令内容')
    return
  }

  sending.value = true
  try {
    await sendCommand({ device_id: props.deviceId, command: command.value.trim() })
    ElMessage.success('指令已下发')
    // 添加到本地历史
    history.value.unshift({
      command: command.value.trim(),
      time: new Date().toLocaleString('zh-CN')
    })
    command.value = ''
  } catch {
    // 错误已在拦截器中处理
  } finally {
    sending.value = false
  }
}

/** 加载指令历史（查询最近的操作数据作为指令人为记录） */
async function loadHistory() {
  loading.value = true
  try {
    // 使用 device/query 来获取这个设备最近的命令记录
    const res = await queryDeviceData({
      device_id: props.deviceId,
      page: 1,
      page_size: 20
    })
    if (res.code === 200 && res.data) {
      // 这里展示的是设备数据，指令历史主要靠本地记录
      // 因为后端没有单独的指令历史 API
    }
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

watch(() => props.deviceId, () => { command.value = ''; history.value = []; loadHistory() }, { immediate: true })
</script>

<style scoped>
.device-control {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.warning-alert {
  border-radius: var(--radius-md);
}

.send-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  box-shadow: var(--shadow-sm);
}

.send-card h3 {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: var(--space-sm);
}

.send-btn {
  width: 100%;
  height: 46px;
  font-size: 15px;
  margin-top: var(--space-md);
}

.history-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  box-shadow: var(--shadow-sm);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-sm);
}

.history-header h3 {
  font-size: 15px;
  font-weight: 600;
}

.history-loading,
.history-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-lg);
  color: var(--text-muted);
  font-size: 13px;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.history-item {
  padding: 10px 12px;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.history-content {
  margin-bottom: 4px;
}

.history-content code {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-primary);
  word-break: break-all;
}

.history-time {
  font-size: 11px;
  color: var(--text-muted);
}
</style>
