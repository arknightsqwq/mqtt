<template>
  <div ref="chartRef" class="chart-container" :style="{ height: height }" />
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { TimeSeriesPoint } from '@/types'

export interface SeriesData {
  name: string
  points: TimeSeriesPoint[]
  color: string
}

const props = withDefaults(defineProps<{
  series: SeriesData[]
  height?: string
  smooth?: boolean
  title?: string
  /** merge 模式：只更新数据，保留缩放/平移状态（轮询刷新用） */
  merge?: boolean
}>(), {
  height: '380px',
  smooth: true,
  merge: false
})

const chartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

/** 调色板 — 多系列时按序分配，单系列用主色 */
const PALETTE = [
  '#FF6B35',  // 活力橙
  '#00C48C',  // 薄荷绿
  '#4A90D9',  // 蓝
  '#FFD93D',  // 阳光黄
  '#FF4757',  // 珊瑚红
  '#A55EEA',  // 紫
  '#2ED573',  // 翠绿
  '#FF6348',  // 橙红
]

function initChart() {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  // 无数据
  if (!props.series.length || props.series.every(s => !s.points.length)) {
    chart.setOption({
      title: props.title ? {
        text: props.title, left: 'center', top: 8,
        textStyle: { fontSize: 14, color: '#6C757D', fontWeight: 500 }
      } : undefined,
      xAxis: { show: false },
      yAxis: { show: false },
      series: [],
      graphic: [{
        type: 'text', left: 'center', top: 'middle',
        style: { text: '暂无数据', fill: '#ADB5BD', fontSize: 14 }
      }]
    })
    return
  }

  // 组装 ECharts series
  const echartsSeries = props.series.map((s, i) => {
    // 时间字符串 → 时间戳，ECharts time 轴需要
    const data = s.points.map(p => {
      const t = new Date(p.time).getTime()
      const v = typeof p.value === 'string' ? parseFloat(p.value) : p.value
      return [t, isNaN(v) ? 0 : v]
    })
    const color = s.color || PALETTE[i % PALETTE.length]
    return {
      name: s.name,
      type: 'line' as const,
      smooth: props.smooth,
      symbol: 'circle',
      symbolSize: 4,
      data,
      lineStyle: { color, width: 2.5 },
      itemStyle: { color },
      emphasis: { focus: 'series' as const }
    }
  })

  // 计算 Y 轴范围（统一所有系列的 min/max，避免切换系列时轴跳动）
  let yMin = Infinity, yMax = -Infinity
  for (const s of props.series) {
    for (const p of s.points) {
      const v = typeof p.value === 'string' ? parseFloat(p.value) : p.value
      if (!isNaN(v)) {
        if (v < yMin) yMin = v
        if (v > yMax) yMax = v
      }
    }
  }
  if (!isFinite(yMin)) { yMin = 0; yMax = 100 }
  const pad = Math.max((yMax - yMin) * 0.08, 1)

  // 滑块颜色跟随系列主色
  const sliderColor = props.series[0]?.color || '#FF6B35'

  chart.setOption({
    title: props.title ? {
      text: props.title, left: 'center', top: 8,
      textStyle: { fontSize: 14, color: '#6C757D', fontWeight: 500 }
    } : undefined,
    color: PALETTE,
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#eee',
      textStyle: { color: '#1A1A2E', fontSize: 13 },
      appendToBody: true
    },
    legend: props.series.length > 1 ? {
      top: 0,
      left: 'center',
      textStyle: { fontSize: 12, color: '#6C757D' },
      itemWidth: 16,
      itemHeight: 8
    } : undefined,
    grid: {
      left: 60,
      right: 20,
      top: props.series.length > 1 ? 36 : 16,
      bottom: 52
    },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: '#eee' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#ADB5BD',
        fontSize: 11,
        formatter: (v: number) => {
          const d = new Date(v)
          const hh = String(d.getHours()).padStart(2, '0')
          const mm = String(d.getMinutes()).padStart(2, '0')
          const ss = String(d.getSeconds()).padStart(2, '0')
          return `${hh}:${mm}:${ss}`
        }
      },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      min: yMin - pad,
      max: yMax + pad,
      splitLine: { lineStyle: { color: '#f5f5f5', type: 'dashed' as const } },
      axisLabel: { color: '#ADB5BD', fontSize: 11 }
    },
    dataZoom: [
      {
        type: 'slider',
        xAxisIndex: 0,
        bottom: 8,
        height: 28,
        borderColor: '#eee',
        fillerColor: sliderColor + '1F',
        handleStyle: { color: sliderColor, borderColor: sliderColor },
        selectedDataBackground: {
          lineStyle: { color: sliderColor },
          areaStyle: { color: sliderColor + '14' }
        },
        textStyle: { color: '#ADB5BD', fontSize: 10 },
        zoomLock: false
      },
      // 鼠标滚轮 / 拖拽缩放（图内操作）
      {
        type: 'inside',
        xAxisIndex: 0,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        moveOnMouseWheel: false
      },
      // Y 轴纵向缩放（图内 Shift+滚轮）
      {
        type: 'inside',
        yAxisIndex: 0,
        zoomOnMouseWheel: true,
        moveOnMouseMove: false,
        moveOnMouseWheel: false
      }
    ],
    series: echartsSeries
  }, true)  // notMerge=true：完全替换配置，避免残留
}

/** merge 模式：仅更新系列数据 + 轴范围，保留 dataZoom 缩放状态 */
function mergeSeriesData() {
  if (!chart || !props.series.length) return

  const echartsSeries = props.series.map((s, i) => {
    const data = s.points.map(p => {
      const t = new Date(p.time).getTime()
      const v = typeof p.value === 'string' ? parseFloat(p.value) : p.value
      return [t, isNaN(v) ? 0 : v]
    })
    const color = s.color || PALETTE[i % PALETTE.length]
    return {
      name: s.name,
      type: 'line' as const,
      smooth: props.smooth,
      symbol: 'circle',
      symbolSize: 4,
      data,
      lineStyle: { color, width: 2.5 },
      itemStyle: { color },
      emphasis: { focus: 'series' as const }
    }
  })

  // 计算 Y 轴范围
  let yMin = Infinity, yMax = -Infinity
  for (const s of props.series) {
    for (const p of s.points) {
      const v = typeof p.value === 'string' ? parseFloat(p.value) : p.value
      if (!isNaN(v)) {
        if (v < yMin) yMin = v
        if (v > yMax) yMax = v
      }
    }
  }
  if (!isFinite(yMin)) { yMin = 0; yMax = 100 }
  const pad = Math.max((yMax - yMin) * 0.08, 1)

  // 只更新数据部分，不触碰 dataZoom/grid/tooltip
  chart.setOption({
    series: echartsSeries,
    yAxis: { min: yMin - pad, max: yMax + pad },
    legend: props.series.length > 1 ? {
      top: 0,
      left: 'center',
      textStyle: { fontSize: 12, color: '#6C757D' },
      itemWidth: 16,
      itemHeight: 8
    } : { show: false }
  }, false)  // notMerge=false: 保留 dataZoom 状态
}

function handleResize() {
  chart?.resize()
}

watch(() => props.series, () => {
  if (!chart) return
  if (props.merge) {
    mergeSeriesData()
  } else {
    initChart()
  }
}, { deep: true })

onMounted(async () => {
  await nextTick()
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.chart-container {
  width: 100%;
}
</style>
