<template>
  <div class="auth-page">
    <!-- 背景装饰 -->
    <div class="bg-blob" />

    <div class="auth-card">
      <!-- Logo 区 -->
      <div class="logo-section">
        <div class="logo-icon">
          <el-icon :size="36" color="#fff"><Monitor /></el-icon>
        </div>
        <h1 class="app-name">IoT 设备管家</h1>
        <p class="app-tagline">随时随地管理您的设备</p>
      </div>

      <!-- 表单 -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="auth-form"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="user_id">
          <el-input
            v-model="form.user_id"
            placeholder="请输入用户名"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="submit-btn"
          :loading="loading"
          @click="handleLogin"
        >
          登 录
        </el-button>
      </el-form>

      <!-- 底部链接 -->
      <div class="auth-footer">
        还没有账号？
        <router-link to="/register" class="link">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Monitor } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  user_id: '',
  password: ''
})

const rules: FormRules = {
  user_id: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login(form.user_id, form.password)
    ElMessage.success('登录成功')
    router.push((route.query.redirect as string) || '/devices')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-lg);
  position: relative;
  overflow: hidden;
}

.bg-blob {
  position: absolute;
  top: -20%;
  right: -30%;
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(255,107,53,0.15) 0%, rgba(255,217,61,0.08) 50%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.auth-card {
  width: 100%;
  max-width: 380px;
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  padding: 40px 32px;
  position: relative;
  z-index: 1;
}

.logo-section {
  text-align: center;
  margin-bottom: 32px;
}

.logo-icon {
  width: 64px;
  height: 64px;
  background: var(--gradient-primary);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  box-shadow: var(--shadow-glow-orange);
}

.app-name {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.app-tagline {
  font-size: 14px;
  color: var(--text-muted);
}

.auth-form .el-form-item {
  margin-bottom: 18px;
}

.submit-btn {
  width: 100%;
  height: 46px;
  font-size: 16px;
  margin-top: 8px;
}

.auth-footer {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
  color: var(--text-muted);
}

.link {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
}
</style>
