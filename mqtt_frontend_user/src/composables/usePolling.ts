import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 轮询 composable：定时执行回调，页面不可见时暂停
 * @param callback 异步回调函数
 * @param intervalMs 轮询间隔（毫秒），默认 10000
 */
export function usePolling(callback: () => Promise<void>, intervalMs: number = 10000) {
  const isActive = ref(false)
  let timer: ReturnType<typeof setInterval> | null = null
  let paused = false

  function start() {
    if (timer) return
    isActive.value = true
    // 立即执行一次
    callback()
    timer = setInterval(() => {
      if (!paused) {
        callback()
      }
    }, intervalMs)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    isActive.value = false
  }

  function onVisibilityChange() {
    if (document.hidden) {
      paused = true
    } else {
      paused = false
      // 页面恢复可见时立即刷新
      callback()
    }
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', onVisibilityChange)
  })

  onUnmounted(() => {
    stop()
    document.removeEventListener('visibilitychange', onVisibilityChange)
  })

  return { isActive, start, stop }
}
