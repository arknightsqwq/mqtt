import http from './index'
import type { ApiResponse, LoginData } from '@/types'

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
