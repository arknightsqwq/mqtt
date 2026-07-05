import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getDeviceLatest, bindDevice as apiBind, unbindDevice as apiUnbind } from '@/api/device'
import type { DeviceSummary, ApiResponse } from '@/types'

export const useDevicesStore = defineStore('devices', () => {
  const list = ref<DeviceSummary[]>([])
  const loading = ref(false)
  const currentConfig = ref<any>(null)

  /** 拉取所有绑定设备的最新状态 */
  async function fetchDevices(deviceIds: string[]) {
    if (!deviceIds.length) {
      list.value = []
      return
    }
    loading.value = true
    try {
      const results = await Promise.allSettled(
        deviceIds.map(id => getDeviceLatest(id))
      )
      const merged: DeviceSummary[] = []
      for (const r of results) {
        if (r.status === 'fulfilled' && r.value?.code === 200 && r.value.data) {
          merged.push(r.value.data as DeviceSummary)
        }
      }
      list.value = merged
    } finally {
      loading.value = false
    }
  }

  /** 获取单个设备最新数据 */
  async function fetchOneDevice(deviceId: string): Promise<DeviceSummary | null> {
    try {
      const res = await getDeviceLatest(deviceId)
      if (res.code === 200 && res.data) {
        const summary = res.data as DeviceSummary
        const idx = list.value.findIndex(d => d.device_id === deviceId)
        if (idx >= 0) {
          list.value[idx] = summary
        } else {
          list.value.push(summary)
        }
        return summary
      }
    } catch {
      // ignore
    }
    return null
  }

  /** 绑定设备 */
  async function bindDevice(deviceId: string) {
    await apiBind({ device_id: deviceId })
  }

  /** 解绑设备 */
  async function unbindDevice(deviceId: string) {
    await apiUnbind({ device_id: deviceId })
    list.value = list.value.filter(d => d.device_id !== deviceId)
  }

  return { list, loading, currentConfig, fetchDevices, fetchOneDevice, bindDevice, unbindDevice }
})
