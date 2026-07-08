// ===== API 响应 =====
export interface ApiResponse<T = unknown> { code: number; msg: string; data?: T }

// ===== 用户 =====
export interface UserInfo { user_id: string; status: number }

// ===== 设备 =====
export interface DeviceConfigField {
  label?: string
  type?: string
  unit?: string
  default?: unknown
  min?: number
  max?: number
  options?: string[]
}

export interface DeviceInfo {
  device_id: string
  device_name: string
  device_desc: string | null
  config_json: Record<string, DeviceConfigField> | null
  field_labels: Record<string, string> | null
  is_online: number
  last_online_time: string | null
  last_offline_time: string | null
  bind_count: number
}

// ===== 日志 =====
export interface LogEntry {
  id: number
  user_id: string
  action: string
  target: string | null
  detail: string | null
  ip: string | null
  created_at: string
}
