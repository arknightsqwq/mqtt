import http from './index'
import type { ApiResponse, LoginData, BindDevice } from '@/types'

/** 用户登录 */
export function login(data: { user_id: string; password: string }): Promise<LoginData> {
  return http.post('/api/user/login', data)
}

/** 用户注册 */
export function register(data: { user_id: string; password: string }): Promise<ApiResponse> {
  return http.post('/api/user/register', data)
}

/** 用户退出 */
export function logout(): Promise<ApiResponse> {
  return http.post('/api/user/logout')
}

/** 获取当前用户绑定的设备列表（从服务端实时查询） */
export function fetchBindings(): Promise<ApiResponse<{ bind_devices: BindDevice[] }>> {
  return http.get('/api/user/bindings')
}
