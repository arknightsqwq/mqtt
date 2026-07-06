import http from './index'
import type { ApiResponse, DeviceLatest, TimeSeriesData, TrajectoryData, AlertList, DeviceQueryResult, DeviceQueryParams } from '@/types'

/** 绑定设备 */
export function bindDevice(data: { device_id: string }): Promise<ApiResponse> {
  return http.post('/api/user/bind_device', data)
}

/** 解绑设备 */
export function unbindDevice(data: { device_id: string }): Promise<ApiResponse> {
  return http.post('/api/user/unbind_device', data)
}

/** 查询设备历史数据（分页） */
export function queryDeviceData(params: DeviceQueryParams): Promise<DeviceQueryResult> {
  return http.post('/api/device/query', params)
}

/** 向设备下发指令 */
export function sendCommand(data: { device_id: string; command: string }): Promise<ApiResponse> {
  return http.post('/api/device/send_cmd', data)
}

/** 向设备下发配置 */
export function sendConfig(data: { device_id: string; command: string }): Promise<ApiResponse> {
  return http.post('/api/device/send_config', data)
}

/** 获取设备最新遥测数据 */
export function getDeviceLatest(deviceId: string): Promise<ApiResponse<DeviceLatest>> {
  return http.get(`/api/device/${deviceId}/latest`)
}

/** 获取设备时间序列数据（用于图表） */
export function getDeviceTimeSeries(
  deviceId: string,
  params: { field: string; hours: number; limit: number }
): Promise<ApiResponse<TimeSeriesData>> {
  return http.get(`/api/device/${deviceId}/timeseries`, { params })
}

/** 获取设备 GPS 轨迹数据 */
export function getDeviceTrajectory(
  deviceId: string,
  params: { hours: number; limit: number }
): Promise<ApiResponse<TrajectoryData>> {
  return http.get(`/api/device/${deviceId}/trajectory`, { params })
}

/** 获取所有绑定设备的告警 */
export function getAlerts(params: { hours: number; limit: number }): Promise<ApiResponse<AlertList>> {
  return http.get('/api/alerts', { params })
}

/** 获取录音音频 Blob（直接返回二进制流） */
export async function fetchRecording(deviceId: string, recordingId: number): Promise<Blob> {
  const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const token = localStorage.getItem('user_token') || ''
  const resp = await fetch(`${base}/api/device/${deviceId}/recording/${recordingId}?fmt=wav`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!resp.ok) throw new Error('获取录音失败')
  return resp.blob()
}
