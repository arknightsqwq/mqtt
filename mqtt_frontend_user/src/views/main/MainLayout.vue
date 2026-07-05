<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand" @click="$router.push('/devices')">
        <span class="brand-dot"></span>
        <span class="brand-text">IoT 设备管家</span>
      </div>

      <nav class="sidebar-nav">
        <!-- 设备 -->
        <div class="nav-label">设备</div>
        <router-link to="/devices" class="nav-item" active-class="active">
          <el-icon><Monitor /></el-icon>
          <span>我的设备</span>
        </router-link>
        <template v-if="authStore.bindDevices.length">
          <router-link
            v-for="d in authStore.bindDevices"
            :key="d.device_id"
            :to="'/device/' + d.device_id"
            class="nav-item sub-item"
            :class="{ active: route.path === '/device/' + d.device_id }"
          >
            <span class="sub-dot" />
            <span class="sub-name">{{ d.device_name || d.device_id }}</span>
          </router-link>
        </template>
        <div v-else class="nav-hint">暂无绑定设备</div>

        <!-- 数据 -->
        <div class="nav-label">数据</div>
        <router-link to="/alerts" class="nav-item" active-class="active">
          <el-icon><Bell /></el-icon>
          <span>告警中心</span>
        </router-link>

        <!-- 账号 -->
        <div class="nav-label">账号</div>
        <router-link to="/profile" class="nav-item" active-class="active">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </router-link>
      </nav>

      <div class="user-bar">
        <div class="user-info">
          <span class="user-avatar">{{ authStore.userId?.charAt(0)?.toUpperCase() }}</span>
          <span class="user-name">{{ authStore.userId }}</span>
        </div>
        <el-button text class="logout-btn" @click="handleLogout">退出</el-button>
      </div>
    </aside>

    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Monitor, Bell, User } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

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
.layout { display: flex; height: 100vh; }

.sidebar {
  width: 220px;
  background: var(--bg-card);
  border-right: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  color: var(--color-primary);
  cursor: pointer;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.brand-dot {
  width: 10px; height: 10px;
  background: var(--gradient-primary);
  border-radius: 50%;
  box-shadow: var(--shadow-glow-orange);
}

.brand-text {
  background: var(--gradient-welcome);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.nav-label {
  font-size: 11px;
  color: var(--text-muted);
  padding: 16px 12px 4px;
  letter-spacing: 1px;
  font-weight: 600;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  transition: all 0.2s;
  margin-bottom: 2px;
}

.nav-item:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.nav-item.active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-weight: 600;
}

/* 子设备项 */
.sub-item {
  padding-left: 28px;
  font-size: 13px;
}

.sub-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--color-success);
  flex-shrink: 0;
}

.sub-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-hint {
  font-size: 12px;
  color: var(--text-muted);
  padding: 6px 12px 6px 28px;
}

/* 用户栏 */
.user-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.05);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-avatar {
  width: 32px; height: 32px;
  background: var(--gradient-primary);
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
}

.user-name {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.logout-btn {
  color: var(--color-danger) !important;
  font-size: 13px;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 28px;
  background: var(--bg-page);
}
</style>
