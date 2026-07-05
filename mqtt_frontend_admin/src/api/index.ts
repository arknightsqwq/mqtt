import axios from 'axios'; import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL, timeout: 10000 })

http.interceptors.request.use((c) => {
  const t = sessionStorage.getItem('admin_token')
  if (t) c.headers['X-Admin-Token'] = t
  return c
})
http.interceptors.response.use((r) => r.data, (e) => {
  ElMessage.error(e.response?.data?.detail || '请求失败'); return Promise.reject(e)
})
export default http
