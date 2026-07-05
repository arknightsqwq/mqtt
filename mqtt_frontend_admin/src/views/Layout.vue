<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand" @click="$router.push('/admin/dashboard')"><span class="dot"></span> Admin Panel</div>
      <nav>
        <router-link to="/admin/dashboard" class="nav-item" active-class="active"><el-icon><Odometer /></el-icon><span>管理首页</span></router-link>
        <div class="label">设备管理</div>
        <router-link to="/admin/devices" class="nav-item" active-class="active"><el-icon><Monitor /></el-icon><span>设备列表</span></router-link>
        <router-link to="/admin/register-device" class="nav-item" active-class="active"><el-icon><CirclePlus /></el-icon><span>注册设备</span></router-link>
        <div class="label">用户管理</div>
        <router-link to="/admin/users" class="nav-item" active-class="active"><el-icon><UserFilled /></el-icon><span>用户列表</span></router-link>
        <router-link to="/admin/create-user" class="nav-item" active-class="active"><el-icon><User /></el-icon><span>创建用户</span></router-link>
        <div class="label">数据</div>
        <router-link to="/admin/messages" class="nav-item" active-class="active"><el-icon><ChatDotSquare /></el-icon><span>消息查询</span></router-link>
        <div class="label">系统</div>
        <router-link to="/admin/logs" class="nav-item" active-class="active"><el-icon><Document /></el-icon><span>操作日志</span></router-link>
      </nav>
      <div class="user-bar"><span>管理员</span><el-button text @click="logout" style="color:#ff5252">退出</el-button></div>
    </aside>
    <main><router-view /></main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'; import { useAdminStore } from '@/stores/admin'
import { Odometer, Monitor, CirclePlus, UserFilled, User, Document, ChatDotSquare } from '@element-plus/icons-vue'
const router = useRouter(); const store = useAdminStore()
function logout() { store.logout(); router.push('/login') }
</script>

<style scoped>
.layout{display:flex;height:100vh}
.sidebar{width:220px;background:#1e2232;border-right:1px solid rgba(64,158,255,0.08);display:flex;flex-direction:column;flex-shrink:0}
.brand{display:flex;align-items:center;gap:10px;padding:20px;font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;color:#409EFF;cursor:pointer;border-bottom:1px solid rgba(255,255,255,0.05)}
.dot{width:10px;height:10px;background:#409EFF;border-radius:50%;box-shadow:0 0 10px #409EFF}
nav{flex:1;overflow-y:auto;padding:12px}
.label{font-size:11px;text-transform:uppercase;color:#556;padding:16px 12px 4px;letter-spacing:1px}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;color:#8892b0;text-decoration:none;font-size:14px;transition:all 0.2s;margin-bottom:2px}
.nav-item:hover{background:rgba(64,158,255,0.06);color:#e0e6ff}
.nav-item.active{background:rgba(64,158,255,0.12);color:#409EFF}
.user-bar{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-top:1px solid rgba(255,255,255,0.05);color:#8892b0;font-size:13px}
main{flex:1;overflow-y:auto;padding:24px}
</style>
