<template>
  <div class="dash">
    <h1>管理首页</h1>

    <!-- 统计卡片行 -->
    <div class="cards">
      <div class="stat">
        <div class="num">{{ overview.device_total }}</div>
        <div class="lbl">设备总数</div>
      </div>
      <div class="stat">
        <div class="num">{{ overview.device_online }}</div>
        <div class="lbl">在线设备</div>
      </div>
      <div class="stat">
        <div class="num">{{ overview.user_total }}</div>
        <div class="lbl">用户总数</div>
      </div>
      <div class="stat">
        <div class="num">{{ overview.today_messages }}</div>
        <div class="lbl">今日消息</div>
      </div>
      <div class="stat">
        <div class="num" :class="{ green: emqx.reachable, red: !emqx.reachable }">{{ emqx.connections }}</div>
        <div class="lbl">EMQX 连接</div>
      </div>
      <div class="stat">
        <div class="num">{{ emqx.topics }}</div>
        <div class="lbl">MQTT 主题</div>
      </div>
    </div>

    <!-- 下半部分：三栏 -->
    <div class="panels">
      <!-- 左栏：系统状态 -->
      <div class="panel">
        <div class="panel-title">系统状态</div>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">设备概况</span>
            <span class="info-val">
              {{ overview.device_online }} 在线 / {{ overview.device_offline }} 离线 / {{ overview.device_total }} 总计
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">用户概况</span>
            <span class="info-val">
              {{ overview.user_active }} 启用 / {{ overview.user_disabled }} 禁用 / {{ overview.user_total }} 总计
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">今日消息</span>
            <span class="info-val">
              {{ overview.today_telemetry }} 遥测 / {{ overview.today_alerts }} 告警 / {{ overview.today_messages }} 总计
            </span>
          </div>
        </div>
      </div>

      <!-- 中栏：EMQX Broker -->
      <div class="panel">
        <div class="panel-title">
          EMQX Broker
          <span class="broker-tag" :class="{ up: emqx.reachable, down: !emqx.reachable }">
            {{ emqx.reachable ? '● 运行中' : '○ 不可达' }}
          </span>
        </div>
        <div v-if="emqx.reachable" class="info-grid">
          <div class="info-item">
            <span class="info-label">版本</span>
            <span class="info-val">{{ emqx.version }} ({{ emqx.edition }})</span>
          </div>
          <div class="info-item">
            <span class="info-label">运行时长</span>
            <span class="info-val">{{ emqx.uptime_display }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">连接数</span>
            <span class="info-val">{{ emqx.live_connections }} 活跃 / {{ emqx.connections }} 总数</span>
          </div>
          <div class="info-item">
            <span class="info-label">会话 / 订阅</span>
            <span class="info-val">{{ emqx.sessions }} / {{ emqx.subscriptions }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">主题 / 保留消息</span>
            <span class="info-val">{{ emqx.topics }} / {{ emqx.retained }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">内存使用</span>
            <span class="info-val">{{ emqx.memory_used }} / {{ emqx.memory_total }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">系统负载</span>
            <span class="info-val">{{ emqx.load1 }} / {{ emqx.load5 }} / {{ emqx.load15 }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">进程数</span>
            <span class="info-val">{{ emqx.process_used }} / {{ emqx.process_available }}</span>
          </div>
        </div>
        <div v-else class="emqx-offline">
          <p>EMQX Broker 不可达</p>
          <p class="hint">请检查 EMQX 服务是否启动 ({{ emqx.version || '无响应' }})</p>
        </div>
      </div>

      <!-- 右栏：最近操作 -->
      <div class="panel">
        <div class="panel-title">最近操作</div>
        <div v-if="overview.recent_logs.length === 0" style="color:#99a0b8;text-align:center;padding:20px">暂无操作记录</div>
        <div v-else class="log-list">
          <div v-for="l in overview.recent_logs" :key="l.id" class="log-item">
            <el-tag size="small" :type="tagType(l.action)">{{ actionLabel(l.action) }}</el-tag>
            <span class="log-target">{{ l.target || '-' }}</span>
            <span class="log-user">{{ l.user_id }}</span>
            <span class="log-time">{{ l.created_at }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { getOverview, getEmqxInfo, type EmqxInfo } from '@/api/admin'

const overview = reactive({
  device_total: 0, device_online: 0, device_offline: 0,
  user_total: 0, user_active: 0, user_disabled: 0,
  today_messages: 0, today_alerts: 0, today_telemetry: 0,
  recent_logs: [] as any[],
})

const emqx = reactive<EmqxInfo>({
  reachable: false, version: '', uptime_seconds: 0, uptime_display: '',
  node_status: '', edition: '', memory_used: '', memory_total: '',
  load1: 0, load5: 0, load15: 0, connections: 0, live_connections: 0,
  sessions: 0, topics: 0, subscriptions: 0, retained: 0, channels: 0,
  max_fds: 0, process_used: 0, process_available: 0,
})

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

onMounted(async () => {
  try {
    const r = await getOverview()
    if (r.code === 200 && r.data) Object.assign(overview, r.data)
  } catch {}
  try {
    const r = await getEmqxInfo()
    if (r.code === 200 && r.data) Object.assign(emqx, r.data)
  } catch {}
})
</script>

<style scoped>
.dash { width: 100% }
h1 { font-size: 24px; margin: 0 0 32px; color: #e2e6f0 }

/* 统计卡片 */
.cards {
  display: flex; justify-content: center; gap: 24px; flex-wrap: wrap; margin-bottom: 32px;
}
.stat {
  flex: 1; min-width: 150px; max-width: 220px;
  background: #23273a; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px;
  padding: 28px 16px; text-align: center; transition: all 0.3s;
}
.stat:hover {
  transform: translateY(-4px); border-color: rgba(64,158,255,0.3); box-shadow: 0 12px 40px rgba(0,0,0,0.3);
}
.num {
  font-family: 'JetBrains Mono', monospace; font-size: 40px; font-weight: 700;
  color: #409EFF; line-height: 1.1;
}
.num.green { color: #67c23a }
.num.red { color: #f56c6c }
.lbl {
  color: #99a0b8; font-size: 13px; margin-top: 8px; letter-spacing: 1px;
}

/* 下半部分 */
.panels {
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px;
}
.panel {
  background: #212538; border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 24px;
}
.panel-title {
  color: #b0b4c8; font-size: 15px; font-weight: 600; margin-bottom: 16px; padding-bottom: 12px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  display: flex; justify-content: space-between; align-items: center;
}

/* Broker 状态标签 */
.broker-tag {
  font-size: 12px; font-weight: 500; padding: 2px 10px; border-radius: 10px;
  font-family: inherit;
}
.broker-tag.up { color: #67c23a; background: rgba(103,194,58,0.1) }
.broker-tag.down { color: #f56c6c; background: rgba(245,108,108,0.1) }

.emqx-offline {
  text-align: center; padding: 20px; color: #f56c6c;
}
.emqx-offline p { margin: 0; font-size: 14px }
.emqx-offline .hint { font-size: 12px; color: #666; margin-top: 8px }

/* 系统状态 */
.info-grid { display: flex; flex-direction: column; gap: 12px }
.info-item { display: flex; justify-content: space-between; align-items: center }
.info-label { color: #99a0b8; font-size: 13px; flex-shrink: 0 }
.info-val { color: #e2e6f0; font-size: 13px; font-family: 'JetBrains Mono', monospace; text-align: right }

/* 最近操作 */
.log-list { display: flex; flex-direction: column; gap: 8px }
.log-item { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.03) }
.log-target { color: #e2e6f0; font-size: 13px; flex: 1 }
.log-user { color: #99a0b8; font-size: 12px }
.log-time { color: #99a0b8; font-size: 11px; font-family: 'JetBrains Mono', monospace }
</style>
