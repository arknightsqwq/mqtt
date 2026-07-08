import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { login as apiLogin, register as apiRegister, logout as apiLogout, fetchBindings } from '@/api/user'
import { STORAGE_KEYS } from '@/constants/storage'
import type { BindDevice } from '@/types'

function loadBindDevices(): BindDevice[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.BIND_DEVICES)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveBindDevices(devices: BindDevice[]) {
  localStorage.setItem(STORAGE_KEYS.BIND_DEVICES, JSON.stringify(devices))
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(STORAGE_KEYS.USER_TOKEN) || '')
  const userId = ref(localStorage.getItem(STORAGE_KEYS.USER_ID) || '')
  const bindDevices = ref<BindDevice[]>(loadBindDevices())

  const isLoggedIn = computed(() => !!token.value)

  // 自动持久化 bindDevices
  watch(bindDevices, (v) => saveBindDevices(v), { deep: true })

  async function login(user_id: string, password: string) {
    const res = await apiLogin({ user_id, password })
    token.value = res.access_token
    userId.value = res.user_id
    bindDevices.value = res.bind_devices || []
    localStorage.setItem(STORAGE_KEYS.USER_TOKEN, res.access_token)
    localStorage.setItem(STORAGE_KEYS.USER_ID, res.user_id)
  }

  async function register(user_id: string, password: string) {
    await apiRegister({ user_id, password })
  }

  async function logout() {
    try { await apiLogout() } catch { /* ignore */ }
    token.value = ''
    userId.value = ''
    bindDevices.value = []
    localStorage.removeItem(STORAGE_KEYS.USER_TOKEN)
    localStorage.removeItem(STORAGE_KEYS.USER_ID)
    localStorage.removeItem(STORAGE_KEYS.BIND_DEVICES)
  }

  function setBindDevices(devices: BindDevice[]) {
    bindDevices.value = devices
  }

  /** 从服务端刷新绑定设备列表，同步 localStorage */
  async function refreshBindings() {
    try {
      const res = await fetchBindings()
      if (res.code === 200 && res.data) {
        bindDevices.value = res.data.bind_devices || []
      }
    } catch {
      // 网络异常时保留本地缓存，不覆盖
    }
  }

  return { token, userId, bindDevices, isLoggedIn, login, register, logout, setBindDevices, refreshBindings }
})
