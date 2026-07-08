/**
 * 图表颜色调色板。
 * 全局统一，避免各处重复定义。
 */
export const CHART_PALETTE = [
  '#FF6B35', '#00C48C', '#4A90D9', '#FFD93D',
  '#FF4757', '#A55EEA', '#2ED573', '#FF6348',
] as const

/**
 * 分组卡片左侧色条颜色映射。
 */
export const GROUP_COLORS: Record<string, string> = {
  '生命体征': '#FF6B6B',
  '环境':     '#4A90D9',
  '位置':     '#20BF6B',
  '设备':     '#E6A23C',
  '其他':     '#B0B4C8',
}
