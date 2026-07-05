# 下位机与服务器 MQTT 通信协议

## 1. 连接配置

| 项目 | 说明 |
|------|------|
| 协议 | MQTT v3.1.1 |
| Broker 地址 | 由 `.env` 中 `EMQX_HOST` / `EMQX_PORT` 配置 |
| 认证方式 | 用户名 + 密码（每设备独立凭证） |
| 用户名 | `device_id`（设备唯一标识） |
| 密码 | 在 EMQX 认证后端中为每台设备配置 |
| Client ID | 建议使用 `device_id`，避免重复 |

---

## 2. 主题总览

```
device/{device_id}/gps          ← 设备上报 GPS 定位 (QoS 1)
device/{device_id}/telemetry   ← 设备上报遥测 (QoS 1)
device/{device_id}/alert       ← 设备上报告警 (QoS 2)
device/{device_id}/status      ← 设备上报在线状态 (QoS 1)
device/{device_id}/cmd         → 服务器下发控制指令 (QoS 1)
device/{device_id}/config      → 服务器下发配置 (QoS 1)
device/{device_id}/recording    ← 设备上报录音 (QoS 1) [原始 AMR 二进制]
```

---

## 3. 设备 → 服务器（上行）

### 3.1 GPS 定位 — `device/{device_id}/gps`

**QoS 1**，快刷新（秒级），上报 GNSS 模块原始定位数据。由移远 Quectel GNSS 库 `get_location()` 解析后直接发送。

```json
{
  "temperature": 28.5,
  "humidity": 65.0,
  "battery": 85,
  "lux": 450,
  "mag": 1.02,
  "gps_latitude": 38.88489,
  "gps_longitude": 121.52349,
  "gps_altitude": 13.6,
  "gps_speed": 3.1,
  "gps_cog": 1.7,
  "gps_hdop": 3.2,
  "gps_fix_type": 3,
  "gps_utc_time": "073943.000",
  "gps_date": "050726",
  "gps_satellites": 6
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `temperature` | number | 温度 (°C) |
| `humidity` | number | 湿度 (%) |
| `battery` | number | 电量 (%) |
| `lux` | number | 光照强度 (lux) |
| `mag` | number | 磁力计 |
| `gps_latitude` | number | 纬度 |
| `gps_longitude` | number | 经度 |
| `gps_altitude` | number | 海拔（米） |
| `gps_speed` | number | 地面速度（m/s） |
| `gps_cog` | number | 航向角（度） |
| `gps_hdop` | number | 水平精度因子 |
| `gps_fix_type` | int | 定位类型（3=3D） |
| `gps_utc_time` | string | UTC 时间 `HHMMSS.sss` |
| `gps_date` | string | UTC 日期 `DDMMYY` |
| `gps_satellites` | int | 可见卫星数 |

### 3.2 遥测数据 — `device/{device_id}/telemetry`

**QoS 1**，慢刷新（分钟/小时级），上报低频变化字段。

```json
{
  "battery": 84.99,
  "rssi": -53.17,
  "temperature": 36.5
}
```

无固定 schema，按设备实际传感器灵活发送。收到后自动合并到最近的 GPS 记录中。

### 3.3 告警消息 — `device/{device_id}/alert`

**QoS 2**，异常事件触发时上报。

```json
{
  "type": "high_temperature",
  "severity": "warning",
  "message": "温度偏高: 32.5°C，超过 30°C 阈值",
  "current_value": 32.5,
  "threshold": 30
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 建议 | 告警类型标识 |
| `severity` | string | 建议 | `warning` / `high`；`high` 会触发服务端告警日志 |
| `message` | string | 建议 | 人类可读的告警描述 |
| `current_value` | number | 可选 | 当前触发值 |
| `threshold` | number | 可选 | 触发阈值 |

### 3.4 在线状态 — `device/{device_id}/status`

**QoS 1**，设备启动/关闭时各发送一次。

```json
{"type": "online"}
```

```json
{"type": "offline"}
```

| type 值 | 服务器行为 |
|---------|-----------|
| `online` | 更新 `is_online=1`，记录 `last_online_time` |
| `offline` | 更新 `is_online=0`，记录 `last_offline_time` |

---

## 4. 服务器 → 设备（下行）

### 4.1 控制指令 — `device/{device_id}/cmd`

**QoS 1**，由用户在前端「控制」tab 输入，服务器原样转发。**必须是合法 JSON**。

```json
{"cmd": "reboot", "params": {"delay": 5}}
```

### 4.2 配置下发 — `device/{device_id}/config`

**QoS 1**，由用户在前端「配置」tab 输入，服务器原样转发。**必须是合法 JSON**。

```json
{"report_interval": 30, "alarm_threshold": 80, "led_mode": "blink"}
```

> 前后端均会校验是否为合法 JSON，非法格式会被拒绝。

### 4.3 录音上传 — `device/{device_id}/recording`

**QoS 1**，告警触发后上报录音。**payload 为原始 AMR 二进制字节流**，不封装 JSON、不转 base64。

设备端示例（伪代码）：
```cpp
// 1. 先发告警，带上 recording_id 标记
publish("device/device_001/alert", json({
  "type": "high_temperature",
  "severity": "warning",
  "recording_id": "rec_20250705_001",
  "message": "温度偏高"
}));

// 2. 紧接着发录音原始字节
uint8_t amr_buf[8192];
int len = read_amr_from_mic(amr_buf);
publish_binary("device/device_001/recording", amr_buf, len);
```

- 无录音时不发此消息
- 后端收到后存入 `device_recording` 表并自动关联到最近一条告警
- 前端告警列表中带录音的告警会显示「播放录音」按钮

---

## 5. 设备注册

设备首次接入前需由管理员在后台注册，否则所有上行消息会被**静默丢弃**。

| 方式 | 地址 |
|------|------|
| 管理员前端 | `http://<host>:5175` → 设备注册 |
| API | `POST /api/device/register` (Header: `X-Admin-Token`) |

注册字段：`device_id`（必填）、`device_name`（必填）、`device_desc`（可选）。

---

## 6. 数据存储

上行消息写入 `device_data` 表：

| 列 | 说明 |
|----|------|
| `device_id` | 设备 ID |
| `message_type` | `telemetry` 或 `alert` |
| `raw_json` | 设备上报的原始 JSON（MySQL JSON 列，自动校验格式） |
| `upload_time` | 服务器入库时间（毫秒精度） |

> `(device_id, upload_time)` 有唯一约束，同一毫秒内的重复消息会被跳过。

录音写入 `device_recording` 表：

| 列 | 说明 |
|----|------|
| `id` | 自增主键（即告警 raw_json 中的 `recording_db_id`） |
| `device_id` | 设备 ID |
| `format` | 音频格式，默认 `amr` |
| `data` | 原始音频二进制（MEDIUMBLOB，最大 16MB） |
| `upload_time` | 上传时间 |

---

## 7. 模拟器参考

项目内置 `simulate_devices.py`，核心通信逻辑：

```python
import paho.mqtt.client as mqtt
import json

# ── 连接 ──
client = mqtt.Client(client_id=device_id, protocol=mqtt.MQTTv311)
client.username_pw_set(device_id, password)
client.connect(host, port, 60)
client.loop_start()

# ── 上行：遥测 ──
client.publish(
    f"device/{device_id}/telemetry",
    json.dumps({"temperature": 25.4, "battery": 85.0, "latitude": 31.23, "longitude": 121.47}),
    qos=1
)

# ── 上行：告警 ──
client.publish(
    f"device/{device_id}/alert",
    json.dumps({"type": "low_battery", "severity": "high", "message": "电量低"}),
    qos=2
)

# ── 上行：状态 ──
client.publish(
    f"device/{device_id}/status",
    json.dumps({"type": "online"}),
    qos=1
)

# ── 下行：接收指令/配置（需先订阅） ──
def on_message(client, userdata, msg):
    payload = json.loads(msg.payload)
    print(f"收到 {msg.topic}: {payload}")

client.subscribe(f"device/{device_id}/cmd", qos=1)
client.subscribe(f"device/{device_id}/config", qos=1)
client.on_message = on_message
```
