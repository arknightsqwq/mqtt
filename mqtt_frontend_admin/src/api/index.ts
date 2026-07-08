import axios from 'axios'
import { ElMessage } from 'element-plus'
import { STORAGE_KEYS } from '@/constants/storage'

const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL, timeout: 10000 })

http.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(STORAGE_KEYS.ADMIN_TOKEN)
  if (token) config.headers['X-Admin-Token'] = token
  return config
})
http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    ElMessage.error(error.response?.data?.detail || '请求失败')
    return Promise.reject(error)
  }
)
export default http
