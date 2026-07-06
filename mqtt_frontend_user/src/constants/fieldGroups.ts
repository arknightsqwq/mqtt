/**
 * 遥测字段分组配置。
 * key 为英文字段名，value 为分组中文名。
 * 未在此配置的字段自动归入"其他"。
 */
export const FIELD_GROUPS: Record<string, string> = {
  // 生命体征
  bpm: '生命体征',
  spo2: '生命体征',

  // 环境
  temperature: '环境',
  humidity: '环境',
  lux: '环境',
  pressure: '环境',
  mag: '环境',

  // 位置
  gps_latitude: '位置',
  gps_longitude: '位置',
  gps_altitude: '位置',
  gps_speed_kmh: '位置',
  gps_speed_knot: '位置',
  gps_speed: '位置',
  gps_cog: '位置',

  // 设备
  battery: '设备',
  gps_satellites: '设备',
  gps_fix_type: '设备',
  gps_fix_mode: '设备',
  gps_hdop: '设备',
  gps_date: '设备',
  gps_utc_time: '设备',
}

/** 未匹配字段的默认分组名 */
export const DEFAULT_GROUP = '其他'
