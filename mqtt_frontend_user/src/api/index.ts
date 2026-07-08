import axios from 'axios'
import { ElMessage } from 'element-plus'
import { STORAGE_KEYS } from '@/constants/storage'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 15000
})

// 请求拦截器：附加 JWT Bearer token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem(STORAGE_KEYS.USER_TOKEN)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：解包 data + 统一错误处理
http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.msg || error.response?.data?.detail || '请求失败'
    ElMessage.error(msg)
    // 401 自动登出
    if (error.response?.status === 401) {
      localStorage.removeItem(STORAGE_KEYS.USER_TOKEN)
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default http
