import { defineStore } from 'pinia'; import { ref, computed } from 'vue'

export const useAdminStore = defineStore('admin', () => {
  const token = ref(sessionStorage.getItem('admin_token') || '')
  const isLoggedIn = computed(() => !!token.value)
  function login(t: string) { token.value = t; sessionStorage.setItem('admin_token', t) }
  function logout() { token.value = ''; sessionStorage.removeItem('admin_token') }
  return { token, isLoggedIn, login, logout }
})
