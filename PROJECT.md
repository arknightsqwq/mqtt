# IoT 设备监测系统 — 项目文档

## 一、项目概述

本项目是一个完整的 IoT 智能头盔远程监测平台，采用 **MQTT + FastAPI + Vue 3 + MySQL** 技术栈。系统支持设备通过 MQTT 协议上报遥测数据（生命体征、环境、GPS 等），用户可通过 Web 前端实时查看数据、图表、GPS 轨迹，并可下发控制指令；管理员可通过独立后台管理设备和用户。

### 技术栈

| 层级 | 技术 |
|------|------|
| 消息中间件 | EMQX (MQTT Broker v3.1.1) |
| 后端框架 | Python FastAPI + Uvicorn |
| 数据库 | MySQL 8.0 |
| 连接池 | pymysql + DBUtils PooledDB |
| 认证 | JWT (HS256, 24h过期) + bcrypt 密码哈希 |
| 用户前端 | Vue 3 + TypeScript + Vite + Pinia + Element Plus + ECharts 5 + Leaflet |
| 管理前端 | Vue 3 + TypeScript + Vite + Element Plus + Pinia |
| MQTT 客户端 | paho-mqtt |

### 目录结构

```
d:\mqtt\
├── 下位机与服务器MQTT通信协议.md       # MQTT 通信协议文档
├── mqtt_backend/                      # Python FastAPI 后端
│   ├── main.py                        # 主入口：所有路由 + MQTT 客户端 + 业务逻辑
│   ├── models.py                      # Pydantic 请求/响应模型
│   ├── config.py                      # 配置文件（环境变量读取）
│   ├── database.py                    # 数据库连接池 + 密码加密 + 操作日志
│   ├── auth.py                        # JWT 令牌 + Admin Token 认证
│   ├── schema.sql                     # 数据库建表脚本（5张表）
│   ├── add_field_labels.sql           # 迁移脚本：增加 field_labels 字段
│   ├── simulate_devices.py            # 设备模拟器（可独立运行）
│   └── tests/test_api.py              # 集成测试（18个测试用例）
├── mqtt_frontend_user/                # 用户前端 (端口 5176)
│   └── src/
│       ├── api/                       # Axios 封装 + API 函数
│       ├── router/                    # 路由配置 + 鉴权守卫
│       ├── stores/                    # Pinia 状态管理 (auth/devices/alerts)
│       ├── types/                     # TypeScript 类型定义
│       ├── composables/               # 组合式函数 (轮询/字段翻译)
│       ├── constants/                 # 常量 (字段分组)
│       ├── components/                # 可复用组件
│       └── views/                     # 页面组件
└── mqtt_frontend_admin/               # 管理前端 (端口 5175)
    └── src/
        ├── api/admin.ts               # 管理端 API 函数
        ├── router/                    # 路由配置
        ├── stores/                    # Admin 认证状态
        ├── types/                     # TypeScript 类型定义
        └── views/                     # 管理页面
```

---

## 二、系统架构

### 2.1 整体数据流

```
┌─────────────────┐     MQTT (发布)      ┌──────────────┐
│  IoT 设备        │ ──────────────────→  │              │
│  (智能头盔等)     │                      │   EMQX       │
│  topics:         │ ←────────────────── │   Broker     │
│  device/{id}/gps │     MQTT (订阅)      │              │
│  device/{id}/    │                      └──────┬───────┘
│    telemetry     │                             │
│  device/{id}/    │                    MQTT 消息推送
│    alert         │                             │
│  device/{id}/    │                      ┌──────▼───────┐
│    status        │                      │  FastAPI      │
│  device/{id}/    │                      │  后端          │
│    recording     │                      │  (Port 8000)  │
│  device/{id}/    │                      │               │
│    cmd ←         │ ←── 下发指令 ←────────│  MQTT Client  │
│  device/{id}/    │                      │  HTTP Routes  │
│    config ←      │ ←── 下发配置 ←────────│               │
└─────────────────┘                      └──────┬───────┘
                                                │
                                          MySQL 读写
                                                │
                                     ┌──────────▼───────┐
                                     │    MySQL 8.0      │
                                     │    mqtt_device_db  │
                                     └──────────────────┘
                                                │
                                     HTTP REST API (JWT)
                                                │
                          ┌─────────────────────┼─────────────────────┐
                          │                                             │
                   ┌──────▼───────┐                           ┌───────▼──────┐
                   │  用户前端      │                           │  管理前端     │
                   │  (Port 5176)  │                           │  (Port 5175) │
                   │  Vue 3 +      │                           │  Vue 3 +     │
                   │  ECharts +    │                           │  Element     │
                   │  Leaflet      │                           │  Plus        │
                   └──────────────┘                           └──────────────┘
```

### 2.2 认证体系

```
用户端:  POST /api/user/login  →  JWT Token (24h)
         → 存 localStorage
         → 后续请求: Authorization: Bearer <token>
         → FastAPI get_current_user 依赖注入验证

管理端:  Admin Token (配置项 ADMIN_TOKEN, 默认 "admin123")
         → 存 sessionStorage
         → 后续请求: X-Admin-Token: <token>
         → FastAPI verify_admin 依赖注入验证
```

---

## 三、MQTT 通信协议

### 3.1 主题结构

所有设备数据主题遵循格式：`device/{device_id}/{subtopic}`

| 方向 | Subtopic | 用途 | QoS | 数据格式 |
|------|----------|------|-----|----------|
| 设备 → 服务器 | `gps` | GPS 定位（高频，~1-5s） | 1 | JSON |
| 设备 → 服务器 | `telemetry` | 传感器遥测（低频，~10-30s） | 1 | JSON |
| 设备 → 服务器 | `alert` | 告警消息 | 1 | JSON |
| 设备 → 服务器 | `status` | 在线状态变更 | 1 | JSON (含 is_online) |
| 设备 → 服务器 | `recording` | 录音数据（AMR 二进制） | 1 | Binary |
| 服务器 → 设备 | `cmd` | 控制指令下发 | 1 | JSON |
| 服务器 → 设备 | `config` | 配置模板下发 | 1 | JSON |

### 3.2 GPS 与遥测合并策略（双向合并 + 缓存）

由于 GPS（高频）和 Telemetry（低频）上报频率不同，后端使用三级冗余合并确保数据完整性：

**防线一：GPS 入库时预合并**
```
GPS 消息到达 → 读取内存缓存 _slow_cache[device_id]
             → 将缓存的慢字段合并到 GPS JSON 中
             → INSERT INTO device_data (raw_json 包含完整数据)
```

**防线二：遥测到达时回补**
```
Telemetry 消息到达 → 更新内存缓存
                  → 查找该设备最新一条 GPS 行
                  → UPDATE device_data SET raw_json = 合并后的 JSON
                  → （若无 GPS 行则单独 INSERT）
```

**防线三：API 读取时兜底**
```
GET /api/device/{id}/latest
  → 查最新 GPS 行 + 最新 Telemetry 行
  → Python 端 merge: GPS 打底 → Telemetry 覆盖
  → 返回 latest_raw (JSON 字符串)
```

**慢遥测缓存 ( _slow_cache )**
- 进程级内存字典，key = device_id，value = `(data_dict, timestamp)`
- TTL = 300 秒（5分钟无遥测则自动清除）
- 每次遥测消息到达时顺便全量清理过期条目
- 每次 GPS 合并时检查该设备缓存是否过期

---

## 四、数据库设计

### 4.1 表结构

#### user_info — 用户表
| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | varchar(50) PK | 用户名 |
| user_password | varchar(255) | bcrypt 哈希密码 |
| status | tinyint | 1=启用 0=禁用 |
| create_time | datetime | 创建时间 |

#### device_info — 设备信息表
| 字段 | 类型 | 说明 |
|------|------|------|
| device_id | varchar(50) PK | 设备唯一标识 |
| device_name | varchar(100) | 设备名称 |
| device_desc | text | 设备描述 |
| config_json | json | 配置模板（用户端配置页表单定义） |
| field_labels | json | 遥测字段中文映射 `{"temperature":"温度",...}` |
| current_config | json | 设备上报的当前实际配置 |
| is_online | tinyint | 在线状态 1/0 |
| last_online_time | datetime(3) | 最后上线时间（毫秒精度） |
| last_offline_time | datetime(3) | 最后离线时间 |
| create_time | datetime | 注册时间 |

#### user_device_bind — 用户设备绑定表
| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | varchar(50) PK FK | 用户 ID |
| device_id | varchar(50) PK FK | 设备 ID |
| bind_time | datetime | 绑定时间 |

外键级联删除：删除设备/用户时自动清除关联绑定。

#### device_data — 遥测数据表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint PK AUTO_INCREMENT | 自增主键 |
| device_id | varchar(50) FK | 设备 ID |
| message_type | varchar(20) | gps / telemetry / alert |
| raw_json | json | 完整 JSON 数据 |
| upload_time | datetime(3) | 入库时间（毫秒精度） |

唯一约束：`(device_id, upload_time)` — 同一毫秒内同设备只保留一条。

#### device_recording — 录音存储表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint PK AUTO_INCREMENT | 自增主键 |
| device_id | varchar(50) FK | 设备 ID |
| format | varchar(10) | 格式（默认 amr） |
| data | mediumblob | 二进制音频数据 |
| upload_time | datetime | 上传时间 |

### 4.2 关键索引设计

- `device_data`: 联合唯一索引 `(device_id, upload_time)` — 防止重复写入
- `device_data`: 索引 `(device_id, message_type, upload_time)` — GPS/Telemetry 查询加速
- `user_device_bind`: 联合主键 `(user_id, device_id)`

---

## 五、后端 API 详解

### 5.1 用户认证路由

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/user/register` | 无 | 用户注册，密码 bcrypt 哈希 |
| POST | `/api/user/login` | 无 | 登录，返回 JWT token + 已绑定设备列表 |
| POST | `/api/user/logout` | JWT | 登出 |
| POST | `/api/user/bind_device` | JWT | 绑定设备到当前用户 |
| POST | `/api/user/unbind_device` | JWT | 解绑设备 |

### 5.2 设备数据路由（用户端）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/device/{id}/latest` | 获取设备最新合并数据（GPS + Telemetry） |
| GET | `/api/device/{id}/timeseries?field=&hours=&limit=` | 提取单个字段时序数据（JSON_EXTRACT） |
| GET | `/api/device/{id}/trajectory?hours=&limit=` | GPS 轨迹数据（lat/lng/speed/alt/cog，最多2000点） |
| POST | `/api/device/query` | 设备数据分页查询 |
| POST | `/api/device/send_cmd` | 通过 MQTT 下发控制指令 |
| POST | `/api/device/send_config` | 通过 MQTT 下发配置 |

### 5.3 告警与录音路由（用户端）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/alerts?hours=&limit=` | 获取用户绑定设备的所有告警 |
| GET | `/api/device/{id}/recording/{rec_id}?fmt=` | 获取录音文件（默认 WAV，可选 AMR） |

### 5.4 管理端路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/overview` | 仪表盘统计（设备/用户/消息/日志总数） |
| GET | `/api/admin/emqx-info` | EMQX 代理状态（版本/连接数/主题/负载） |
| GET | `/api/admin/devices` | 设备列表（含绑定数、字段标签） |
| POST | `/api/device/register` | 注册单个设备 |
| POST | `/api/admin/device/batch_register` | 批量注册（CSV/JSON，跳过已有） |
| DELETE | `/api/device/{id}` | 删除设备（级联清除所有数据） |
| PUT | `/api/admin/device/{id}/config` | 更新设备配置模板 |
| PUT | `/api/admin/device/{id}/field-labels` | 更新设备字段中文标签 |
| GET | `/api/admin/users` | 用户列表 |
| POST | `/api/admin/user/create` | 创建用户 |
| POST | `/api/admin/user/batch_create` | 批量创建用户 |
| PUT | `/api/admin/user/password` | 重置用户密码 |
| PUT | `/api/admin/user/status` | 启用/禁用用户 |
| GET | `/api/admin/logs?user_id=&action=&page=&page_size=` | 操作日志分页查询 |
| GET | `/api/admin/messages?device_id=&message_type=&keyword=&start=&end=` | MQTT 消息查询 |

### 5.5 系统路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |

---

## 六、后端核心函数详解

### 6.1 MQTTClient 类（main.py）

全局单例，封装 paho-mqtt 客户端，负责消息订阅/处理和指令下发。

| 方法 | 功能 |
|------|------|
| `__init__()` | 初始化 MQTT 客户端，设置回调，连接 EMQX，订阅 5 个通配符主题 |
| `_on_message(client, userdata, msg)` | 消息路由器：解析 topic 获取 device_id 和 subtopic，分发到对应 handler |
| `_device_registered(device_id)` | 检查设备是否在 device_info 表中注册 |
| `_insert_device_data(device_id, raw_json, message_type)` | 写入 device_data 表。GPS 类型自动合并慢遥测缓存 |
| `_merge_slow_telemetry(device_id, raw_json)` | 缓存慢遥测数据 → 找到最新 GPS 行 → UPDATE 合并 |
| `_handle_status(device_id, raw_json)` | 更新 device_info 的 is_online 和时间戳 |
| `_handle_alert(device_id, raw_json)` | 告警入库，日志告警 |
| `_handle_config_report(device_id, raw_json)` | 设备上报当前配置，更新 current_config |
| `_handle_recording(device_id, payload)` | AMR 二进制入库 → 回溯 30 秒内最近告警注入 recording_db_id |
| `_clean_stale_cache()` | 清理超过 300 秒未更新的慢遥测缓存条目 |
| `publish_cmd(device_id, command)` | 向 `device/{id}/cmd` 主题发布指令 |
| `publish_config(device_id, config)` | 向 `device/{id}/config` 主题发布配置 |

### 6.2 database.py

| 函数 | 功能 |
|------|------|
| `get_pool()` | 延迟初始化 DBUtils PooledDB 连接池（最小2连接，可配置） |
| `get_conn()` | 上下文管理器，自动获取/归还数据库连接 |
| `get_cursor(conn, dict_cursor)` | 上下文管理器，自动获取/关闭游标。dict_cursor=True 返回字典行 |
| `check_db_connection()` | 启动时数据库连通性测试 |
| `hash_password(plain)` | bcrypt 密码哈希 |
| `verify_password(plain, hashed)` | bcrypt 密码验证 |
| `log_operation(user_id, action, target, detail, ip)` | 写入操作日志，失败静默忽略 |

### 6.3 auth.py

| 函数 | 功能 |
|------|------|
| `create_access_token(user_id)` | 生成 JWT，sub=user_id，24h 有效期，HS256 签名 |
| `decode_access_token(token)` | 解码 JWT，返回 user_id（失败返回 None） |
| `get_current_user(authorization)` | FastAPI 依赖：从 Bearer token 提取 user_id |
| `verify_admin(x_admin_token)` | FastAPI 依赖：校验管理端 Token |

### 6.4 device_timeseries（main.py:994）

提取 raw_json 中指定字段的时序数据，使用 MySQL `JSON_EXTRACT` + `JSON_UNQUOTE`：
```sql
SELECT JSON_UNQUOTE(JSON_EXTRACT(raw_json, CONCAT('$.', field))) AS val, upload_time
FROM device_data
WHERE device_id=%s AND message_type='gps'
  AND upload_time >= DATE_SUB(NOW(), INTERVAL hours HOUR)
  AND JSON_EXTRACT(...) IS NOT NULL
ORDER BY upload_time ASC LIMIT limit
```
返回 `[{time, value}, ...]` 供 ECharts 折线图使用。

### 6.5 device_trajectory（main.py:1039）

查询 GPS 数据用于地图轨迹回放：
```sql
SELECT raw_json, upload_time
FROM device_data
WHERE device_id=%s AND message_type='gps'
  AND upload_time >= DATE_SUB(NOW(), INTERVAL hours HOUR)
ORDER BY upload_time ASC LIMIT limit
```
Python 端从 raw_json 提取 lat/lng/speed/alt/cog，返回 `[{time, lat, lng, speed, alt, cog}, ...]`。

---

## 七、用户前端详解

### 7.1 路由与页面结构

```
/login                          → 登录页
/register                       → 注册页
/                               → 主布局（需登录）
  /devices                      → 设备列表（首页）
  /alerts                       → 告警中心
  /profile                      → 个人中心
  /device/:id                   → 设备详情（含6个Tab）
    Tab 1: 概览 (DeviceOverview)
    Tab 2: 数据 (DeviceData)
    Tab 3: 告警 (DeviceAlerts)
    Tab 4: 控制 (DeviceControl)
    Tab 5: 配置 (DeviceConfig)
    Tab 6: 轨迹 (DeviceTrajectory)
```

### 7.2 状态管理（Pinia Stores）

**useAuthStore** (`auth.ts`)
| 属性/方法 | 说明 |
|-----------|------|
| `token` | JWT 令牌（持久化到 localStorage） |
| `userId` | 当前用户名 |
| `bindDevices` | 已绑定设备列表 `{device_id, device_name, device_desc}[]` |
| `login(user_id, password)` | 登录并存储 token |
| `register(user_id, password)` | 注册 |
| `logout()` | 登出并清除 token |

**useDevicesStore** (`devices.ts`)
| 属性/方法 | 说明 |
|-----------|------|
| `list: DeviceSummary[]` | 设备摘要列表 |
| `fetchDevices(deviceIds)` | 批量获取设备最新数据 |
| `fetchOneDevice(deviceId)` | 获取单设备最新数据 |
| `bindDevice(deviceId)` | 绑定设备 |
| `unbindDevice(deviceId)` | 解绑设备 |

**useAlertsStore** (`alerts.ts`)
| 属性/方法 | 说明 |
|-----------|------|
| `items: AlertItemData[]` | 告警列表 |
| `fetchAlerts(hours, limit)` | 获取告警 |

### 7.3 核心组合式函数

**usePolling** (`src/composables/usePolling.ts`)
- 自动轮询指定回调函数
- 页面隐藏时自动暂停（`visibilitychange` 事件）
- 页面恢复时立即刷新一次
- 组件卸载时自动停止
- 使用场景：设备列表轮询（10s）、设备详情轮询（10s）、时序图轮询（10s）

**useFieldLabel** (`src/composables/useFieldLabel.ts`)
- `translate(fieldLabels, key) → string`
- 从设备的 `field_labels` JSON 映射中查找中文名
- 未找到则降级显示原始英文字段名

### 7.4 页面组件功能

#### DeviceOverview（设备概览）
- 在线/离线状态横幅（渐变背景 + 脉冲动画）
- 遥测卡片按 4 组分类显示：生命体征（红）→ 环境（蓝）→ 位置（绿）→ 设备（橙）
- 同组字段放同一张卡片，左侧色条 + 淡色背景
- Leaflet 地图显示当前位置
- 设备信息面板（ID、名称、状态、最后上线时间）
- 解绑按钮

#### DeviceData（数据图表）
- 多选字段下拉（自动发现 latest_raw 中的数值字段）
- 时间范围选择：1h / 6h / 24h / 7d
- 每个字段渲染独立 ECharts 时间序列折线图
- dataZoom 滑块支持缩放和拖拽
- 轮询刷新保留缩放状态（merge 模式）
- 字段名通过 field_labels 翻译为中文

#### DeviceTrajectory（GPS 轨迹）
- 时间范围选择：5min / 1h / 6h / 24h / 7d
- Leaflet 地图显示 GPS 折线轨迹
- 绿色圆点标记起点，红色圆点标记终点
- 自动 fitBounds 适配视野
- 下方速度时间序列图带 dataZoom 滑块
- **联动机制**：拖动数据滑块 → 按时间范围过滤 GPS 点 → 地图轨迹实时更新
- 统计栏：总里程（Haversine 公式）、GPS 点数、平均速度、最高速度
- 自定义缩放时间时显示"自定义"标签 + "重置范围"按钮

#### DeviceControl（设备控制）
- JSON 指令输入框（含格式提示）
- JSON 格式校验
- 下发按钮 → 后端转发到 `device/{id}/cmd` 主题
- 本地指令历史记录

#### DeviceConfig（设备配置）
- **无配置模板时**：自由 JSON 编辑 + 下发
- **有配置模板时**：动态表单生成
  - `type: "number"` → 数字输入框（支持 min/max）
  - `type: "select"` → 下拉选择（options 数组）
  - `type: "text"` → 文本输入
  - 初始值来自设备上报的 current_config 或模板默认值
- 配置下发历史记录

#### DeviceAlerts（设备告警）
- 时间范围过滤：1h / 6h / 24h / 48h
- 告警项含所属设备名、消息内容、时间
- 支持告警关联录音回放（WAV 格式）

#### AlertsList（全局告警）
- 时间范围过滤（同上）
- 点击告警名称跳转到对应设备详情

---

## 八、管理前端详解

### 8.1 路由结构

```
/login              → 登录（输入 Admin Token）
/admin              → 管理布局
  /admin/dashboard  → 仪表盘
  /admin/devices    → 设备管理
  /admin/register-device → 设备注册（单个/批量）
  /admin/users      → 用户管理
  /admin/create-user → 用户创建（单个/批量）
  /admin/messages   → MQTT 消息查看
  /admin/logs       → 操作日志
```

### 8.2 页面功能

**Dashboard**：6 个统计卡片（设备总数/在线数、用户总数、今日消息数、EMQX 连接数、MQTT 主题数）+ EMQX 代理详情（版本、运行时间、连接、会话、内存、负载）+ 最近操作日志。

**DeviceList**：设备表格（ID、名称、描述、在线状态、绑定数）。操作列：配置 JSON 编辑器弹窗、字段标签 JSON 编辑器弹窗、删除（带确认）。

**DeviceRegister**：单个注册表单 + 批量导入（支持拖拽 CSV/JSON 文件）。

**UserList**：用户表格（ID、状态）。操作：启用/禁用切换、重置密码弹窗。

**UserCreate**：单个创建表单 + 批量导入。

**MessageViewer**：MQTT 消息查询（按设备ID、消息类型、关键字、时间范围过滤）。详情弹窗含 JSON 查看和复制。

**LogViewer**：操作日志查询（按用户ID、操作类型过滤）。彩色标签区分操作类型。

---

## 九、设计规范

### 9.1 设计令牌（CSS 变量）

| 类别 | 变量 | 值 |
|------|------|------|
| 主色 | `--color-primary` | `#FF6B35` (活力橙) |
| 成功 | `--color-success` | `#00C48C` |
| 警告 | `--color-warning` | `#FFD93D` |
| 危险 | `--color-danger` | `#FF4757` |
| 背景-页面 | `--bg-page` | `#F0F2F5` |
| 背景-卡片 | `--bg-card` | `#FFFFFF` |
| 文字-主 | `--text-primary` | `#1A1A2E` |
| 文字-次 | `--text-secondary` | `#6C757D` |
| 文字-弱 | `--text-muted` | `#ADB5BD` |
| 字体-展示 | `--font-display` | Noto Sans SC |
| 字体-等宽 | `--font-mono` | JetBrains Mono |

### 9.2 统计分组颜色

| 分组 | 色值 | 使用场景 |
|------|------|----------|
| 生命体征 | `#FF6B6B` | 心率(bpm)、血氧(spo2) |
| 环境 | `#4A90D9` | 温度、湿度、光照、气压、磁场 |
| 位置 | `#20BF6B` | GPS 坐标、速度、航向、海拔 |
| 设备 | `#E6A23C` | 电量、卫星数、HDOP 等 |
| 其他 | `#B0B4C8` | 未分类字段 |

---

## 十、设备模拟器

`simulate_devices.py` 可独立运行，无需真实硬件即可测试系统：

```bash
# 启动 3 台默认设备
python simulate_devices.py

# 指定设备和参数
python simulate_devices.py device_001 device_002 --interval 5 --alert-every 30
```

**工作原理**：
- 每台设备独立 MQTT 客户端，连接到 EMQX
- GPS 数据：在基准坐标附近做正弦漂移 + 高斯噪声，约 2 秒一条
- 遥测数据：温度、湿度、电量、光照、磁场，高斯噪声模拟，约 10 秒一条
- 告警：随机触发（可配置频率）
- 启动时发送 `status: {is_online: true}`，退出时（Ctrl+C）发送 `status: {is_online: false}`

---

## 十一、配置说明

### 后端 .env 关键配置

```env
# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASS=your_password
DB_NAME=mqtt_device_db

# EMQX
EMQX_HOST=localhost
EMQX_PORT=1883
EMQX_USER=backend
EMQX_PASS=your_emqx_password
EMQX_API_HOST=localhost
EMQX_API_PORT=18083
EMQX_API_KEY=your_api_key
EMQX_API_SECRET=your_api_secret

# JWT
JWT_SECRET=your_secret_key
JWT_EXPIRE_HOURS=24

# Admin
ADMIN_TOKEN=admin123

# Subscribe Topics (comma-separated)
SUBSCRIBE_TOPICS=device/+/gps:1,device/+/telemetry:1,device/+/alert:1,device/+/status:1,device/+/recording:1
```

---

## 十二、启动方式

### 1. 启动 EMQX Broker
```bash
# 确保 EMQX 已安装并运行在 localhost:1883 (MQTT) 和 localhost:18083 (管理API)
```

### 2. 初始化数据库
```bash
mysql -u root -p < mqtt_backend/schema.sql
mysql -u root -p < mqtt_backend/add_field_labels.sql
```

### 3. 启动后端
```bash
cd mqtt_backend
pip install -r requirements.txt
python main.py
# 监听 http://0.0.0.0:8000
```

### 4. 启动前端
```bash
# 用户端 (端口 5176)
cd mqtt_frontend_user
npm install
npm run dev

# 管理端 (端口 5175)
cd mqtt_frontend_admin
npm install
npm run dev
```

### 5. （可选）启动设备模拟器
```bash
cd mqtt_backend
python simulate_devices.py
```

### 6. 运行测试
```bash
cd mqtt_backend
python -m pytest tests/test_api.py -v
```
