import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { STORAGE_KEYS } from '@/constants/storage'

export const useAdminStore = defineStore('admin', () => {
  const token = ref(sessionStorage.getItem(STORAGE_KEYS.ADMIN_TOKEN) || '')
  const isLoggedIn = computed(() => !!token.value)
  function login(t: string) {
    token.value = t
    sessionStorage.setItem(STORAGE_KEYS.ADMIN_TOKEN, t)
  }
  function logout() {
    token.value = ''
    sessionStorage.removeItem(STORAGE_KEYS.ADMIN_TOKEN)
  }
  return { token, isLoggedIn, login, logout }
})
