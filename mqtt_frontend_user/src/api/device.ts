import http from './index'
import type { ApiResponse, DeviceLatest, TimeSeriesData, AlertList, DeviceQueryResult, DeviceQueryParams } from '@/types'

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

/** 获取所有绑定设备的告警 */
export function getAlerts(params: { hours: number; limit: number }): Promise<ApiResponse<AlertList>> {
  return http.get('/api/alerts', { params })
}
