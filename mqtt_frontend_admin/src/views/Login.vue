<template>
  <div class="bg">
    <div class="card">
      <div class="logo"><span class="dot"></span> Admin Panel</div>
      <h2>管理后台</h2>
      <p class="sub">请输入管理员令牌以继续</p>
      <el-input v-model="token" type="password" placeholder="Admin Token" size="large" show-password @keyup.enter="login" />
      <el-button type="primary" size="large" :loading="ld" @click="login" class="btn">进入后台</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'; import { useRouter } from 'vue-router'; import { ElMessage } from 'element-plus'
import { adminLogin } from '@/api/admin'; import { useAdminStore } from '@/stores/admin'

const router = useRouter(); const store = useAdminStore()
const token = ref(''); const ld = ref(false)

async function login() {
  if (!token.value.trim()) { ElMessage.warning('请输入令牌'); return }
  ld.value = true
  try {
    await adminLogin(token.value.trim())
    store.login(token.value.trim()); ElMessage.success('验证通过'); router.push('/admin')
  } catch { token.value = '' } finally { ld.value = false }
}
</script>

<style scoped>
.bg{display:flex;justify-content:center;align-items:center;min-height:100vh;background:radial-gradient(ellipse at 70% 50%, #282d5a 0%, #1a1e2c 70%)}
.card{width:400px;padding:40px;background:rgba(22,24,42,0.9);border:1px solid rgba(64,158,255,0.15);border-radius:16px;backdrop-filter:blur(20px)}
.logo{display:flex;align-items:center;gap:8px;font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;color:#409EFF;margin-bottom:8px}
.dot{width:10px;height:10px;background:#409EFF;border-radius:50%;box-shadow:0 0 10px #409EFF}
h2{color:#e2e6f0;font-size:24px;margin:0 0 4px}.sub{color:#99a0b8;font-size:14px;margin:0 0 24px}
.btn{width:100%;margin-top:16px;height:44px;font-size:16px}
:deep(.el-input__wrapper){background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);box-shadow:none}
:deep(.el-input__inner){color:#e2e6f0}
</style>
