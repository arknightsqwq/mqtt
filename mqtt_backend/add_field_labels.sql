-- ===================================================
-- 给已有数据库添加 field_labels 列
-- 在 MySQL 中执行：
--   mysql -u root -p mqtt_device_db < add_field_labels.sql
-- ===================================================

ALTER TABLE device_info
  ADD COLUMN field_labels json DEFAULT NULL
  COMMENT '遥测字段中文映射: {"temperature":"温度","humidity":"湿度",...}'
  AFTER config_json;

-- 为已有三台模拟设备写入 field_labels
UPDATE device_info SET field_labels = '{
  "temperature": "温度",
  "humidity": "湿度",
  "battery": "电量",
  "lux": "光照度",
  "mag": "磁场",
  "gps_latitude": "纬度",
  "gps_longitude": "经度",
  "gps_altitude": "海拔",
  "gps_speed": "速度",
  "gps_cog": "航向",
  "gps_hdop": "精度",
  "gps_fix_type": "定位类型",
  "gps_date": "日期",
  "gps_utc_time": "UTC时间",
  "gps_satellites": "卫星数"
}' WHERE device_id IN ('device_001', 'device_002', 'device_003');
