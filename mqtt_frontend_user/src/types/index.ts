// ===== API 响应封装 =====
export interface ApiResponse<T = any> {
  code: number
  msg: string
  data?: T
}

// ===== 登录相关 =====
export interface LoginData {
  code: number
  msg: string
  access_token: string
  token_type: string
  user_id: string
  bind_devices: BindDevice[]
}

export interface BindDevice {
  device_id: string
  device_name: string
  device_desc: string | null
}

// ===== 设备实时数据 =====
export interface DeviceLatest {
  device_id: string
  device_name: string
  is_online: boolean
  last_online_time: string | null
  last_offline_time: string | null
  latest_raw: string | null
  latest_time: string | null
  field_labels?: Record<string, string> | null
}

// ===== 时间序列数据 =====
export interface TimeSeriesData {
  device_id: string
  field: string
  points: TimeSeriesPoint[]
}

export interface TimeSeriesPoint {
  time: string
  value: number | string
}

// ===== 告警 =====
export interface AlertList {
  alerts: AlertItemData[]
}

export interface AlertItemData {
  id: number
  device_id: string
  device_name: string | null
  raw_json: string
  upload_time: string
}

// ===== 设备数据查询 =====
export interface DeviceQueryResult {
  code: number
  msg: string
  data: {
    list: DeviceDataItem[]
    total: number
    page: number
    page_size: number
  }
}

export interface DeviceDataItem {
  id: number
  device_id: string
  device_name: string | null
  message_type: string
  raw_json: string
  upload_time: string
}

export interface DeviceQueryParams {
  device_id?: string
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}

// ===== GPS 轨迹数据 =====
export interface TrajectoryData {
  device_id: string
  points: TrajectoryPoint[]
}

export interface TrajectoryPoint {
  time: string
  lat: number
  lng: number
  speed: number | null
  alt: number | null
  cog: number | null
}

// ===== 设备概要（Store 用） =====
export interface DeviceSummary {
  device_id: string
  device_name: string
  device_desc?: string | null
  config_json?: any | null
  field_labels?: Record<string, string> | null
  current_config?: any | null
  is_online: boolean
  last_online_time: string | null
  last_offline_time: string | null
  latest_raw: string | null
  latest_time: string | null
}
