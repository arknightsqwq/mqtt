import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getAlerts } from '@/api/device'
import type { AlertItemData } from '@/types'

export const useAlertsStore = defineStore('alerts', () => {
  const items = ref<AlertItemData[]>([])
  const loading = ref(false)

  async function fetchAlerts(hours: number = 48, limit: number = 100) {
    loading.value = true
    try {
      const res = await getAlerts({ hours, limit })
      if (res.code === 200 && res.data) {
        items.value = res.data.alerts || []
      }
    } finally {
      loading.value = false
    }
  }

  return { items, loading, fetchAlerts }
})
