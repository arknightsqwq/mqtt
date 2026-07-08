/**
 * 本地/会话存储键常量。
 * 避免散落字符串，消除拼写错误风险。
 */
export const STORAGE_KEYS = {
  /** 用户 JWT Bearer token（localStorage） */
  USER_TOKEN: 'user_token',
  /** 当前登录用户 ID（localStorage） */
  USER_ID: 'user_id',
  /** 用户绑定设备列表缓存（localStorage） */
  BIND_DEVICES: 'bind_devices',
  /** 管理员 token（sessionStorage） */
  ADMIN_TOKEN: 'admin_token',
} as const
