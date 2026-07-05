export interface ApiResponse<T=any> { code: number; msg: string; data?: T }
export interface UserInfo { user_id: string; status: number }
export interface DeviceInfo { device_id: string; device_name: string; device_desc: string|null; is_online: number; last_online_time: string|null; last_offline_time: string|null; bind_count: number }
export interface LogEntry { id: number; user_id: string; action: string; target: string|null; detail: string|null; ip: string|null; created_at: string }
