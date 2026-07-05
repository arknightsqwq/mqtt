import http from './index'
import type { ApiResponse, UserInfo, DeviceInfo, LogEntry } from '@/types'

export function adminLogin(token: string): Promise<ApiResponse> {
  return http.get('/admin/users', { headers: { 'X-Admin-Token': token } })
}
export function listUsers(): Promise<ApiResponse<{ users: UserInfo[] }>> {
  return http.get('/admin/users')
}
export function createUser(data: { user_id: string; new_password?: string }): Promise<ApiResponse> {
  return http.post('/admin/user/create', data)
}
export function resetPassword(data: { user_id: string; new_password: string }): Promise<ApiResponse> {
  return http.put('/admin/user/password', data)
}
export function toggleUserStatus(data: { user_id: string; is_disabled: boolean }): Promise<ApiResponse> {
  return http.put('/admin/user/status', data)
}
export function listDevices(): Promise<ApiResponse<{ devices: DeviceInfo[] }>> {
  return http.get('/admin/devices')
}
export function registerDevice(data: { device_id: string; device_name: string; device_desc?: string; config_json?: any }): Promise<ApiResponse> {
  return http.post('/device/register', data)
}
export function deleteDevice(deviceId: string): Promise<ApiResponse> {
  return http.delete(`/device/${deviceId}`)
}
export function updateDeviceConfig(deviceId: string, configJson: any): Promise<ApiResponse> {
  return http.put(`/admin/device/${deviceId}/config`, configJson)
}
export function queryLogs(params: { page?: number; page_size?: number; user_id?: string; action?: string }): Promise<ApiResponse<{ list: LogEntry[]; total: number }>> {
  return http.get('/admin/logs', { params })
}
export function batchRegisterDevices(items: { device_id: string; device_name: string; device_desc?: string }[]): Promise<ApiResponse<{ success: number; skipped: number }>> {
  return http.post('/admin/device/batch_register', items)
}
export function batchCreateUsers(items: { user_id: string; new_password?: string }[]): Promise<ApiResponse<{ success: number; skipped: number }>> {
  return http.post('/admin/user/batch_create', items)
}
export function getOverview(): Promise<ApiResponse<{
  device_total: number; device_online: number; device_offline: number
  user_total: number; user_active: number; user_disabled: number
  today_messages: number; today_alerts: number; today_telemetry: number
  recent_logs: { id: number; user_id: string; action: string; target: string; created_at: string }[]
}>> {
  return http.get('/admin/overview')
}

export interface EmqxInfo {
  reachable: boolean
  version: string
  uptime_seconds: number
  uptime_display: string
  node_status: string
  edition: string
  memory_used: string
  memory_total: string
  load1: number
  load5: number
  load15: number
  connections: number
  live_connections: number
  sessions: number
  topics: number
  subscriptions: number
  retained: number
  channels: number
  max_fds: number
  process_used: number
  process_available: number
}

export function getEmqxInfo(): Promise<ApiResponse<EmqxInfo>> {
  return http.get('/admin/emqx-info')
}

export interface MessageEntry {
  id: number
  device_id: string
  device_name: string | null
  message_type: string
  raw_json: string
  upload_time: string
}

export function queryMessages(params: {
  page?: number; page_size?: number; device_id?: string; message_type?: string
  keyword?: string; start_time?: string; end_time?: string
}): Promise<ApiResponse<{ list: MessageEntry[]; total: number }>> {
  return http.get('/admin/messages', { params })
}
