"""
设备数据管理后端 —— FastAPI + MQTT + MySQL
───────────────────────────────────────────
- JWT 认证：用户端接口需 Bearer Token
- 管理员认证：运维接口需 X-Admin-Token 头
- 连接池：MySQL 连接复用，避免高并发下耗尽连接
- MQTT：全局共享客户端，自动重连，指令下发复用
- 日志：请求日志中间件，异常全局兜底
"""
import base64
import json
import logging
import threading
import time
import urllib.request
import urllib.error
from contextlib import asynccontextmanager
from datetime import datetime

import paho.mqtt.client as mqtt
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import (
    get_conn, get_cursor, check_db_connection,
    hash_password, verify_password, log_operation,
)
from auth import create_access_token, get_current_user, verify_admin
from models import (
    UserLogin, UserRegister, LoginResponse,
    DeviceRegister, DeviceBind, DeviceUnbind,
    DeviceDataQuery, DeviceCommand,
    AdminUserOperate,
)

# ═══════════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mqtt_backend")


# ═══════════════════════════════════════════════
# MQTT 客户端（全局单例，支持重连 + 复用下发）
# ═══════════════════════════════════════════════
class MQTTClient:
    """全局 MQTT 客户端：订阅设备数据 + 下发指令复用同一连接。"""

    def __init__(self):
        self.client = mqtt.Client(
            client_id=f"backend_{id(self):x}",
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(settings.EMQX_USER, settings.EMQX_PASS)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        # 自动重连：初始1秒，最大30秒，指数退避
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    # ── 回调 ──
    @staticmethod
    def _on_connect(client, userdata, flags, rc):
        if rc == 0:
            topics = settings.SUBSCRIBE_TOPICS
            logger.info(f"EMQX 连接成功，订阅 {len(topics)} 个主题")
            for topic, qos in topics:
                client.subscribe(topic, qos=qos)
                logger.info(f"  订阅: {topic} (QoS {qos})")
        else:
            logger.warning(f"EMQX 连接失败，rc={rc}")

    @staticmethod
    def _on_disconnect(client, userdata, rc):
        if rc != 0:
            logger.warning(f"EMQX 断开 (rc={rc})，将自动重连...")

    @staticmethod
    def _on_message(client, userdata, msg):
        """按 Topic 后缀分类路由消息。"""
        try:
            parts = msg.topic.split("/")
            if len(parts) < 3:
                return
            device_id = parts[1]
            subtopic = parts[2]  # "telemetry" | "alert" | "status" | "data" | "cmd" | "config"
            if not device_id:
                return

            # 忽略下行 Topic（虽然默认不会收到自己发的消息，但做防御性过滤）
            if subtopic in ("cmd", "config"):
                return

            raw_json = msg.payload.decode("utf-8")
            logger.info(f"MQTT ← {device_id}/{subtopic}: {raw_json[:100]}")

            # ── 注册校验 ──
            if not MQTTClient._device_registered(device_id):
                logger.info(f"设备 {device_id} 未注册，跳过")
                return

            # ── 按类型分发 ──
            if subtopic == "status":
                MQTTClient._handle_status(device_id, raw_json)
            elif subtopic == "alert":
                MQTTClient._insert_device_data(device_id, raw_json, "alert")
                MQTTClient._handle_alert(device_id, raw_json)
            else:  # telemetry | data（兼容旧版）
                MQTTClient._insert_device_data(device_id, raw_json, "telemetry")

        except Exception as e:
            logger.error(f"MQTT 消息处理失败: {e}")

    # ── 内部方法 ──
    @staticmethod
    def _device_registered(device_id: str) -> bool:
        """检查设备是否已注册。"""
        with get_conn() as conn:
            with get_cursor(conn, dict_cursor=False) as cursor:
                cursor.execute(
                    "SELECT 1 FROM device_info WHERE device_id=%s LIMIT 1",
                    (device_id,),
                )
                return cursor.fetchone() is not None

    @staticmethod
    def _insert_device_data(device_id: str, raw_json: str, message_type: str):
        """将遥测/告警数据写入 device_data 表。"""
        with get_conn() as conn:
            try:
                with get_cursor(conn, dict_cursor=False) as cursor:
                    cursor.execute(
                        "INSERT IGNORE INTO device_data "
                        "(device_id, message_type, raw_json, upload_time) "
                        "VALUES (%s, %s, %s, %s)",
                        (device_id, message_type, raw_json, datetime.now()),
                    )
                conn.commit()
                logger.info(f"  [{message_type}] {device_id} 已入库")
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def _handle_status(device_id: str, raw_json: str):
        """处理设备在线状态消息，更新 device_info 表。"""
        try:
            data = json.loads(raw_json)
            status_type = data.get("type", "unknown")
        except json.JSONDecodeError:
            logger.warning(f"  status 消息 JSON 解析失败: {raw_json[:80]}")
            return

        now = datetime.now()
        with get_conn() as conn:
            try:
                with get_cursor(conn, dict_cursor=False) as cursor:
                    if status_type == "online":
                        cursor.execute(
                            "UPDATE device_info SET is_online=1, last_online_time=%s "
                            "WHERE device_id=%s",
                            (now, device_id),
                        )
                        logger.info(f"  [status] {device_id} 上线")
                    elif status_type == "offline":
                        cursor.execute(
                            "UPDATE device_info SET is_online=0, last_offline_time=%s "
                            "WHERE device_id=%s",
                            (now, device_id),
                        )
                        logger.info(f"  [status] {device_id} 离线")
                    else:
                        logger.info(f"  [status] {device_id} 未知状态: {status_type}")
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def _handle_alert(device_id: str, raw_json: str):
        """告警额外处理——日志报警 + 预留推送/短信扩展点。"""
        try:
            data = json.loads(raw_json)
            alert_type = data.get("type", "unknown")
            severity = data.get("severity", "unknown")
            logger.warning(
                f"  ⚠ ALERT [{severity}] {device_id} → {alert_type}"
            )
            # TODO: 扩展点 ——
            #   if severity == "high":
            #       send_sms(phone, f"设备{device_id}发生{type}告警")
            #       push_notification(user_ids, ...)
        except json.JSONDecodeError:
            logger.warning(f"  alert 消息 JSON 解析失败: {raw_json[:80]}")

    # ── 生命周期 ──
    def start(self):
        def _run():
            self.client.connect(settings.EMQX_HOST, settings.EMQX_PORT, 60)
            self.client.loop_forever()

        t = threading.Thread(target=_run, daemon=True, name="mqtt-listener")
        t.start()
        logger.info("MQTT 客户端已启动（后台线程）")

    def publish_cmd(self, device_id: str, command: str):
        """下发指令到设备（复用全局连接）。"""
        topic = f"device/{device_id}/cmd"
        result = self.client.publish(topic, command, qos=1)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"MQTT → {topic}: {command}")
        else:
            logger.error(f"MQTT 下发失败: rc={result.rc}")
            raise HTTPException(status_code=500, detail="指令下发失败")
        return result


# 全局单例
mqtt_client = MQTTClient()


# ═══════════════════════════════════════════════
# FastAPI 应用
# ═══════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时检测数据库 + 启动 MQTT，关闭时清理。"""
    logger.info(f"启动 {settings.APP_TITLE} ...")
    check_db_connection()
    mqtt_client.start()
    yield
    logger.info("服务关闭")


app = FastAPI(title=settings.APP_TITLE, lifespan=lifespan)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 请求日志中间件 ──
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} "
        f"({elapsed*1000:.0f}ms)"
    )
    return response


# ── 全局异常兜底 ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "msg": exc.detail},
        )
    logger.exception(f"未捕获异常: {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"code": 500, "msg": "服务器内部错误"},
    )


# ═══════════════════════════════════════════════
# 一、用户端接口
# ═══════════════════════════════════════════════

@app.post("/api/user/register", summary="用户注册")
def user_register(data: UserRegister):
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM user_info WHERE user_id=%s LIMIT 1", (data.user_id,)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="用户已存在")
            cursor.execute(
                "INSERT INTO user_info (user_id, user_password) VALUES (%s, %s)",
                (data.user_id, hash_password(data.password)),
            )
            conn.commit()
    logger.info(f"新用户注册: {data.user_id}")
    return {"code": 200, "msg": "注册成功"}


@app.post("/api/user/login", summary="用户登录")
def user_login(data: UserLogin, request: Request):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                "SELECT * FROM user_info WHERE user_id=%s LIMIT 1", (data.user_id,)
            )
            user = cursor.fetchone()
            if not user or not verify_password(data.password, user["user_password"]):
                raise HTTPException(status_code=401, detail="账号或密码错误")
            if user.get("status") == 0:
                raise HTTPException(status_code=403, detail="账号已被禁用")

            cursor.execute(
                """SELECT ub.device_id, di.device_name, di.device_desc
                   FROM user_device_bind ub
                   LEFT JOIN device_info di ON ub.device_id = di.device_id
                   WHERE ub.user_id=%s""",
                (data.user_id,),
            )
            bind_devices = cursor.fetchall()

    token = create_access_token(data.user_id)
    logger.info(f"用户登录: {data.user_id}")
    log_operation(data.user_id, "login", ip=request.client.host if request else None)
    return {
        "code": 200,
        "msg": "登录成功",
        "access_token": token,
        "token_type": "bearer",
        "user_id": data.user_id,
        "bind_devices": bind_devices,
    }


@app.post("/api/user/logout", summary="用户退出登录")
def user_logout(user_id: str = Depends(get_current_user)):
    logger.info(f"用户登出: {user_id}")
    return {"code": 200, "msg": "退出登录成功"}


@app.post("/api/user/bind_device", summary="绑定设备")
def bind_device(data: DeviceBind, user_id: str = Depends(get_current_user)):
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM device_info WHERE device_id=%s LIMIT 1",
                (data.device_id,),
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=400, detail="设备不存在")

            cursor.execute(
                "SELECT 1 FROM user_device_bind WHERE user_id=%s AND device_id=%s LIMIT 1",
                (user_id, data.device_id),
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="已绑定该设备")

            cursor.execute(
                "INSERT INTO user_device_bind (user_id, device_id) VALUES (%s, %s)",
                (user_id, data.device_id),
            )
            conn.commit()
    logger.info(f"用户 {user_id} 绑定设备 {data.device_id}")
    return {"code": 200, "msg": "设备绑定成功"}


@app.post("/api/user/unbind_device", summary="解绑设备")
def unbind_device(data: DeviceUnbind, user_id: str = Depends(get_current_user)):
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM user_device_bind WHERE user_id=%s AND device_id=%s LIMIT 1",
                (user_id, data.device_id),
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=400, detail="未绑定该设备")
            cursor.execute(
                "DELETE FROM user_device_bind WHERE user_id=%s AND device_id=%s",
                (user_id, data.device_id),
            )
            conn.commit()
    logger.info(f"用户 {user_id} 解绑设备 {data.device_id}")
    return {"code": 200, "msg": "设备解绑成功"}


@app.post("/api/device/query", summary="查询设备数据")
def query_device_data(
    data: DeviceDataQuery, user_id: str = Depends(get_current_user)
):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            # 获取用户绑定的设备
            cursor.execute(
                "SELECT device_id FROM user_device_bind WHERE user_id=%s", (user_id,)
            )
            bind_devices = [row["device_id"] for row in cursor.fetchall()]
            if not bind_devices:
                return {
                    "code": 200,
                    "msg": "暂无绑定设备",
                    "data": {"list": [], "total": 0, "page": data.page, "page_size": data.page_size},
                }

            # 构建 WHERE 条件
            placeholders = ",".join(["%s"] * len(bind_devices))
            conditions = [f"d.device_id IN ({placeholders})"]
            params = bind_devices.copy()

            if data.device_id and data.device_id in bind_devices:
                conditions.append("d.device_id = %s")
                params.append(data.device_id)
            if data.start_time:
                conditions.append("d.upload_time >= %s")
                params.append(data.start_time)
            if data.end_time:
                conditions.append("d.upload_time <= %s")
                params.append(data.end_time)

            where = " AND ".join(conditions)

            # count
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM device_data d WHERE {where}", params
            )
            total = cursor.fetchone()["total"]

            # 分页查询
            offset = (data.page - 1) * data.page_size
            cursor.execute(
                f"""SELECT d.id, d.device_id, d.message_type, d.raw_json,
                           d.upload_time, di.device_name
                    FROM device_data d
                    LEFT JOIN device_info di ON d.device_id = di.device_id
                    WHERE {where}
                    ORDER BY d.upload_time DESC
                    LIMIT %s OFFSET %s""",
                params + [data.page_size, offset],
            )
            rows = cursor.fetchall()

    data_list = []
    for r in rows:
        raw = r["raw_json"]
        # JSON 类型列 pymysql 可能返回 dict，统一转字符串给前端
        if isinstance(raw, dict):
            raw = json.dumps(raw, ensure_ascii=False)
        data_list.append({
            "id": r["id"],
            "device_id": r["device_id"],
            "device_name": r["device_name"],
            "message_type": r["message_type"],
            "raw_json": raw,
            "upload_time": r["upload_time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        })
    return {
        "code": 200,
        "msg": "查询成功",
        "data": {
            "list": data_list,
            "total": total,
            "page": data.page,
            "page_size": data.page_size,
        },
    }


@app.post("/api/device/send_cmd", summary="下发设备指令")
def send_device_cmd(
    data: DeviceCommand, user_id: str = Depends(get_current_user)
):
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM user_device_bind WHERE user_id=%s AND device_id=%s LIMIT 1",
                (user_id, data.device_id),
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=403, detail="无权限操作该设备")

    # 复用全局 MQTT 连接下发指令
    mqtt_client.publish_cmd(data.device_id, data.command)
    logger.info(f"用户 {user_id} → 设备 {data.device_id} 指令: {data.command}")
    return {"code": 200, "msg": f"指令已下发到设备 {data.device_id}"}


# ═══════════════════════════════════════════════
# 二、运维端接口（需 X-Admin-Token 头）
# ═══════════════════════════════════════════════

@app.post("/api/device/register", summary="【运维】设备注册入库")
def device_register(
    data: DeviceRegister, _: None = Depends(verify_admin), request: Request = None
):
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM device_info WHERE device_id=%s LIMIT 1",
                (data.device_id,),
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="设备已存在")
            cursor.execute(
                "INSERT INTO device_info (device_id, device_name, device_desc) "
                "VALUES (%s, %s, %s)",
                (data.device_id, data.device_name, data.device_desc),
            )
            conn.commit()
    logger.info(f"管理员注册设备: {data.device_id} ({data.device_name})")
    log_operation("admin", "register_device", data.device_id,
                  f"name={data.device_name}", request.client.host if request else None)
    return {"code": 200, "msg": "设备注册入库成功"}


@app.delete("/api/device/{device_id}", summary="【运维】删除设备")
def device_delete(
    device_id: str, _: None = Depends(verify_admin)
):
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM device_info WHERE device_id=%s LIMIT 1", (device_id,)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="设备不存在")
            # 级联清理：绑定关系 + 设备数据 + 设备信息
            cursor.execute(
                "DELETE FROM user_device_bind WHERE device_id=%s", (device_id,)
            )
            cursor.execute(
                "DELETE FROM device_data WHERE device_id=%s", (device_id,)
            )
            cursor.execute(
                "DELETE FROM device_info WHERE device_id=%s", (device_id,)
            )
            conn.commit()
    logger.info(f"管理员删除设备: {device_id}")
    log_operation("admin", "delete_device", device_id)
    return {"code": 200, "msg": f"设备 {device_id} 已删除"}


@app.post("/api/admin/user/create", summary="【运维】创建用户")
def admin_create_user(
    data: AdminUserOperate, _: None = Depends(verify_admin)
):
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM user_info WHERE user_id=%s", (data.user_id,)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="用户已存在")
            pwd = data.new_password or "123456"
            cursor.execute(
                "INSERT INTO user_info (user_id, user_password, status) VALUES (%s, %s, 1)",
                (data.user_id, hash_password(pwd)),
            )
            conn.commit()
    logger.info(f"管理员创建用户: {data.user_id}")
    log_operation("admin", "create_user", data.user_id)
    return {"code": 200, "msg": f"用户 {data.user_id} 创建成功"}


@app.put("/api/admin/user/password", summary="【运维】重置用户密码")
def admin_update_user(
    data: AdminUserOperate, _: None = Depends(verify_admin)
):
    if not data.new_password:
        raise HTTPException(status_code=400, detail="new_password 不能为空")
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            affected = cursor.execute(
                "UPDATE user_info SET user_password=%s WHERE user_id=%s",
                (hash_password(data.new_password), data.user_id),
            )
            if not affected:
                raise HTTPException(status_code=404, detail="用户不存在")
            conn.commit()
    logger.info(f"管理员重置用户 {data.user_id} 密码")
    log_operation("admin", "reset_pwd", data.user_id)
    return {"code": 200, "msg": f"用户 {data.user_id} 密码已重置"}


@app.put("/api/admin/user/status", summary="【运维】禁用/启用用户")
def admin_disable_user(
    data: AdminUserOperate, _: None = Depends(verify_admin)
):
    if data.is_disabled is None:
        raise HTTPException(status_code=400, detail="is_disabled 不能为空")
    status = 0 if data.is_disabled else 1
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            affected = cursor.execute(
                "UPDATE user_info SET status=%s WHERE user_id=%s",
                (status, data.user_id),
            )
            if not affected:
                raise HTTPException(status_code=404, detail="用户不存在")
            conn.commit()
    action = "禁用" if data.is_disabled else "启用"
    logger.info(f"管理员{action}用户: {data.user_id}")
    log_operation("admin", "disable_user" if data.is_disabled else "enable_user", data.user_id)
    return {"code": 200, "msg": f"用户 {data.user_id} 已{action}"}


@app.get("/api/admin/users", summary="【运维】用户列表")
def admin_list_users(_: None = Depends(verify_admin)):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                "SELECT user_id, status FROM user_info ORDER BY user_id"
            )
            users = cursor.fetchall()
    return {"code": 200, "data": {"users": users}}


@app.get("/api/admin/devices", summary="【运维】设备列表")
def admin_list_devices(_: None = Depends(verify_admin)):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                """SELECT di.device_id, di.device_name, di.device_desc,
                          di.is_online, di.last_online_time, di.last_offline_time,
                          COUNT(ub.user_id) AS bind_count
                   FROM device_info di
                   LEFT JOIN user_device_bind ub ON di.device_id = ub.device_id
                   GROUP BY di.device_id
                   ORDER BY di.device_id"""
            )
            devices = cursor.fetchall()
    return {"code": 200, "data": {"devices": devices}}


# ═══════════════════════════════════════════════
# 三、数据可视化接口（用户端仪表盘）
# ═══════════════════════════════════════════════

@app.get("/api/device/{device_id}/latest", summary="设备最新数据")
def device_latest(device_id: str, user_id: str = Depends(get_current_user)):
    """获取设备最新一条遥测数据，用于仪表盘实时展示。"""
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            # 权限校验
            cursor.execute(
                "SELECT 1 FROM user_device_bind WHERE user_id=%s AND device_id=%s LIMIT 1",
                (user_id, device_id),
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=403, detail="无权限访问该设备")

            cursor.execute(
                "SELECT di.device_id, di.device_name, di.is_online, "
                "di.last_online_time, di.last_offline_time "
                "FROM device_info di WHERE di.device_id=%s",
                (device_id,),
            )
            info = cursor.fetchone()
            if not info:
                raise HTTPException(status_code=404, detail="设备不存在")

            cursor.execute(
                "SELECT raw_json, upload_time, message_type FROM device_data "
                "WHERE device_id=%s AND message_type='telemetry' "
                "ORDER BY upload_time DESC LIMIT 1",
                (device_id,),
            )
            latest = cursor.fetchone()

    raw = None
    upload_time = None
    if latest:
        raw = latest["raw_json"]
        if isinstance(raw, dict):
            raw = json.dumps(raw, ensure_ascii=False)
        upload_time = latest["upload_time"].strftime("%Y-%m-%d %H:%M:%S")

    return {
        "code": 200,
        "data": {
            "device_id": info["device_id"],
            "device_name": info["device_name"],
            "is_online": bool(info["is_online"]),
            "last_online_time": info["last_online_time"],
            "last_offline_time": info["last_offline_time"],
            "latest_raw": raw,
            "latest_time": upload_time,
        },
    }


@app.get("/api/device/{device_id}/timeseries", summary="设备时序数据")
def device_timeseries(
    device_id: str,
    field: str = "value",
    hours: int = 24,
    limit: int = 200,
    user_id: str = Depends(get_current_user),
):
    """提取 raw_json 中指定字段的时序数据，用于折线图。"""
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                "SELECT 1 FROM user_device_bind WHERE user_id=%s AND device_id=%s LIMIT 1",
                (user_id, device_id),
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=403, detail="无权限访问该设备")

            # 用 JSON_EXTRACT 提取字段值，fallback 到整个 JSON
            cursor.execute(
                "SELECT "
                "  JSON_UNQUOTE(JSON_EXTRACT(raw_json, CONCAT('$.', %s))) AS val, "
                "  upload_time "
                "FROM device_data "
                "WHERE device_id=%s AND message_type='telemetry' "
                "  AND upload_time >= DATE_SUB(NOW(), INTERVAL %s HOUR) "
                "  AND JSON_EXTRACT(raw_json, CONCAT('$.', %s)) IS NOT NULL "
                "ORDER BY upload_time ASC "
                "LIMIT %s",
                (field, device_id, hours, field, limit),
            )
            rows = cursor.fetchall()

    points = []
    for r in rows:
        try:
            v = float(r["val"])
        except (ValueError, TypeError):
            v = r["val"]
        points.append({
            "time": r["upload_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "value": v,
        })

    return {"code": 200, "data": {"device_id": device_id, "field": field, "points": points}}


@app.get("/api/alerts", summary="用户告警列表")
def user_alerts(
    hours: int = 48,
    limit: int = 50,
    user_id: str = Depends(get_current_user),
):
    """获取用户所有绑定设备的告警消息。"""
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                "SELECT device_id FROM user_device_bind WHERE user_id=%s",
                (user_id,),
            )
            binds = [r["device_id"] for r in cursor.fetchall()]
            if not binds:
                return {"code": 200, "data": {"alerts": []}}

            placeholders = ",".join(["%s"] * len(binds))
            cursor.execute(
                f"SELECT d.id, d.device_id, di.device_name, d.raw_json, d.upload_time "
                f"FROM device_data d "
                f"LEFT JOIN device_info di ON d.device_id=di.device_id "
                f"WHERE d.device_id IN ({placeholders}) AND d.message_type='alert' "
                f"  AND d.upload_time >= DATE_SUB(NOW(), INTERVAL %s HOUR) "
                f"ORDER BY d.upload_time DESC LIMIT %s",
                binds + [hours, limit],
            )
            rows = cursor.fetchall()

    alerts = []
    for r in rows:
        raw = r["raw_json"]
        if isinstance(raw, dict):
            raw = json.dumps(raw, ensure_ascii=False)
        alerts.append({
            "id": r["id"],
            "device_id": r["device_id"],
            "device_name": r["device_name"],
            "raw_json": raw,
            "upload_time": r["upload_time"].strftime("%Y-%m-%d %H:%M:%S"),
        })

    return {"code": 200, "data": {"alerts": alerts}}


# ═══════════════════════════════════════════════
# 四、操作日志查询（运维端）
# ═══════════════════════════════════════════════

@app.get("/api/admin/logs", summary="【运维】操作日志查询")
def admin_query_logs(
    page: int = 1,
    page_size: int = 20,
    user_id: str = "",
    action: str = "",
    _: None = Depends(verify_admin),
):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            conditions = []
            params = []

            if user_id:
                conditions.append("user_id=%s")
                params.append(user_id)
            if action:
                conditions.append("action=%s")
                params.append(action)

            where = " AND ".join(conditions) if conditions else "1=1"

            cursor.execute(
                f"SELECT COUNT(*) AS total FROM operation_logs WHERE {where}", params
            )
            total = cursor.fetchone()["total"]

            offset = (page - 1) * page_size
            cursor.execute(
                f"SELECT id, user_id, action, target, detail, ip, created_at "
                f"FROM operation_logs WHERE {where} "
                f"ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params + [page_size, offset],
            )
            rows = cursor.fetchall()

    logs = []
    for r in rows:
        logs.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "action": r["action"],
            "target": r["target"],
            "detail": r["detail"],
            "ip": r["ip"],
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
        })

    return {"code": 200, "data": {"list": logs, "total": total}}


# ═══════════════════════════════════════════════
# 四-B、MQTT 消息查询（运维端）
# ═══════════════════════════════════════════════

@app.get("/api/admin/messages", summary="【运维】MQTT 消息查询")
def admin_query_messages(
    page: int = 1,
    page_size: int = 20,
    device_id: str = "",
    message_type: str = "",
    keyword: str = "",
    start_time: str = "",
    end_time: str = "",
    _: None = Depends(verify_admin),
):
    """查询 device_data 表中的 MQTT 消息，支持多条件过滤 + 关键词搜索。"""
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            conditions = []
            params = []

            if device_id:
                conditions.append("d.device_id=%s")
                params.append(device_id)
            if message_type:
                conditions.append("d.message_type=%s")
                params.append(message_type)
            if keyword:
                conditions.append("d.raw_json LIKE %s")
                params.append(f"%{keyword}%")
            if start_time:
                conditions.append("d.upload_time >= %s")
                params.append(start_time)
            if end_time:
                conditions.append("d.upload_time <= %s")
                params.append(end_time)

            where = " AND ".join(conditions) if conditions else "1=1"

            cursor.execute(
                f"SELECT COUNT(*) AS total FROM device_data d WHERE {where}", params
            )
            total = cursor.fetchone()["total"]

            offset = (page - 1) * page_size
            cursor.execute(
                f"SELECT d.id, d.device_id, d.message_type, d.raw_json, d.upload_time, "
                f"di.device_name "
                f"FROM device_data d "
                f"LEFT JOIN device_info di ON d.device_id = di.device_id "
                f"WHERE {where} "
                f"ORDER BY d.upload_time DESC LIMIT %s OFFSET %s",
                params + [page_size, offset],
            )
            rows = cursor.fetchall()

    msgs = []
    for r in rows:
        raw = r["raw_json"]
        if isinstance(raw, dict):
            raw = json.dumps(raw, ensure_ascii=False)
        msgs.append({
            "id": r["id"],
            "device_id": r["device_id"],
            "device_name": r["device_name"],
            "message_type": r["message_type"],
            "raw_json": raw,
            "upload_time": r["upload_time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        })

    return {"code": 200, "data": {"list": msgs, "total": total}}


# ═══════════════════════════════════════════════
# 四-C、批量导入
# ═══════════════════════════════════════════════

@app.post("/api/admin/device/batch_register", summary="【运维】批量注册设备")
def device_batch_register(
    items: list[DeviceRegister], _: None = Depends(verify_admin)
):
    """批量注册设备，跳过已存在的，返回成功/失败计数。"""
    success = 0
    skipped = 0
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            for d in items:
                cursor.execute(
                    "SELECT 1 FROM device_info WHERE device_id=%s LIMIT 1",
                    (d.device_id,),
                )
                if cursor.fetchone():
                    skipped += 1
                    continue
                cursor.execute(
                    "INSERT INTO device_info (device_id, device_name, device_desc) "
                    "VALUES (%s, %s, %s)",
                    (d.device_id, d.device_name, d.device_desc),
                )
                success += 1
            conn.commit()
    logger.info(f"批量注册设备: 成功 {success}, 跳过 {skipped}")
    log_operation("admin", "batch_register_device", None, f"success={success} skipped={skipped}")
    return {"code": 200, "msg": f"成功 {success} 台, 跳过 {skipped} 台（已存在）", "data": {"success": success, "skipped": skipped}}


@app.post("/api/admin/user/batch_create", summary="【运维】批量创建用户")
def user_batch_create(
    items: list[AdminUserOperate], _: None = Depends(verify_admin)
):
    """批量创建用户，跳过已存在的，默认密码 123456。"""
    success = 0
    skipped = 0
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            for u in items:
                cursor.execute(
                    "SELECT 1 FROM user_info WHERE user_id=%s LIMIT 1", (u.user_id,)
                )
                if cursor.fetchone():
                    skipped += 1
                    continue
                pwd = u.new_password or "123456"
                cursor.execute(
                    "INSERT INTO user_info (user_id, user_password, status) "
                    "VALUES (%s, %s, 1)",
                    (u.user_id, hash_password(pwd)),
                )
                success += 1
            conn.commit()
    logger.info(f"批量创建用户: 成功 {success}, 跳过 {skipped}")
    log_operation("admin", "batch_create_user", None, f"success={success} skipped={skipped}")
    return {"code": 200, "msg": f"成功 {success} 个, 跳过 {skipped} 个（已存在）", "data": {"success": success, "skipped": skipped}}
# ═══════════════════════════════════════════════

@app.get("/api/admin/overview", summary="【运维】管理首页概览")
def admin_overview(_: None = Depends(verify_admin)):
    """返回设备/用户/消息汇总，用于管理首页仪表盘。"""
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            # 设备统计
            cursor.execute("SELECT COUNT(*) AS t FROM device_info")
            dev_total = cursor.fetchone()["t"]
            cursor.execute("SELECT COUNT(*) AS t FROM device_info WHERE is_online=1")
            dev_online = cursor.fetchone()["t"]

            # 用户统计
            cursor.execute("SELECT COUNT(*) AS t FROM user_info")
            usr_total = cursor.fetchone()["t"]
            cursor.execute("SELECT COUNT(*) AS t FROM user_info WHERE status=1")
            usr_active = cursor.fetchone()["t"]
            cursor.execute("SELECT COUNT(*) AS t FROM user_info WHERE status=0")
            usr_disabled = cursor.fetchone()["t"]

            # 今日消息统计
            cursor.execute(
                "SELECT COUNT(*) AS t FROM device_data WHERE upload_time >= CURDATE()"
            )
            today_msg = cursor.fetchone()["t"]
            cursor.execute(
                "SELECT COUNT(*) AS t FROM device_data "
                "WHERE upload_time >= CURDATE() AND message_type='alert'"
            )
            today_alert = cursor.fetchone()["t"]
            cursor.execute(
                "SELECT COUNT(*) AS t FROM device_data "
                "WHERE upload_time >= CURDATE() AND message_type='telemetry'"
            )
            today_telemetry = cursor.fetchone()["t"]

            # 最近操作
            cursor.execute(
                "SELECT id, user_id, action, target, created_at "
                "FROM operation_logs ORDER BY created_at DESC LIMIT 8"
            )
            recent_logs = cursor.fetchall()

    logs = []
    for r in recent_logs:
        logs.append({
            "id": r["id"], "user_id": r["user_id"],
            "action": r["action"], "target": r["target"],
            "created_at": r["created_at"].strftime("%H:%M:%S"),
        })

    return {
        "code": 200,
        "data": {
            "device_total": dev_total,
            "device_online": dev_online,
            "device_offline": dev_total - dev_online,
            "user_total": usr_total,
            "user_active": usr_active,
            "user_disabled": usr_disabled,
            "today_messages": today_msg,
            "today_alerts": today_alert,
            "today_telemetry": today_telemetry,
            "recent_logs": logs,
        },
    }


@app.get("/api/admin/emqx-info", summary="【运维】EMQX Broker 状态")
def admin_emqx_info(_: None = Depends(verify_admin)):
    """从 EMQX REST API 拉取 broker 运行状态，失败时返回降级数据。"""
    base = f"http://{settings.EMQX_API_HOST}:{settings.EMQX_API_PORT}"
    auth = base64.b64encode(
        f"{settings.EMQX_API_KEY}:{settings.EMQX_API_SECRET}".encode()
    ).decode()
    headers = {"Authorization": f"Basic {auth}"}

    def _get(path: str):
        try:
            req = urllib.request.Request(f"{base}{path}", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            logger.warning(f"EMQX API {path} 请求失败: {e}")
            return None

    def _unwrap(obj):
        """EMQX v5 API 可能返回 {data:[...]} 或 {data:{...}} 或直接返回对象/数组。统一提取为单条 dict。"""
        if isinstance(obj, list):
            return obj[0] if obj else {}
        if isinstance(obj, dict):
            inner = obj.get("data")
            if isinstance(inner, list):
                return inner[0] if inner else {}
            if isinstance(inner, dict):
                return inner
            return obj
        return {}

    # 并行拉取 nodes + stats
    nodes_data = _get("/api/v5/nodes")
    stats_data = _get("/api/v5/stats")

    result = {
        "reachable": False,
        "version": "",
        "uptime_seconds": 0,
        "uptime_display": "",
        "node_status": "",
        "edition": "",
        "memory_used": "",
        "memory_total": "",
        "load1": 0.0,
        "load5": 0.0,
        "load15": 0.0,
        "connections": 0,
        "live_connections": 0,
        "sessions": 0,
        "topics": 0,
        "subscriptions": 0,
        "retained": 0,
        "channels": 0,
        "max_fds": 0,
        "process_used": 0,
        "process_available": 0,
    }

    if nodes_data:
        result["reachable"] = True
        n = _unwrap(nodes_data)
        result["version"] = n.get("version", "")
        result["uptime_seconds"] = n.get("uptime", 0)
        result["node_status"] = n.get("node_status", "")
        result["edition"] = n.get("edition", "")
        result["memory_used"] = n.get("memory_used", "")
        result["memory_total"] = n.get("memory_total", "")
        result["load1"] = n.get("load1", 0.0)
        result["load5"] = n.get("load5", 0.0)
        result["load15"] = n.get("load15", 0.0)
        result["connections"] = n.get("connections", 0)
        result["live_connections"] = n.get("live_connections", 0)
        result["max_fds"] = n.get("max_fds", 0)
        result["process_used"] = n.get("process_used", 0)
        result["process_available"] = n.get("process_available", 0)

        # 格式化 uptime
        secs = result["uptime_seconds"]
        days, rem = divmod(secs, 86400)
        hours, rem = divmod(rem, 3600)
        mins, _ = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if mins:
            parts.append(f"{mins}m")
        result["uptime_display"] = " ".join(parts) if parts else f"{secs}s"

    if stats_data:
        result["reachable"] = True
        s = _unwrap(stats_data)
        result["sessions"] = s.get("sessions.count", 0)
        result["topics"] = s.get("topics.count", 0)
        result["subscriptions"] = s.get("subscriptions.count", 0)
        result["retained"] = s.get("retained.count", 0)
        result["channels"] = s.get("channels.count", 0)

    logger.info(
        f"EMQX info: reachable={result['reachable']}, version={result['version']}, "
        f"connections={result['connections']}, topics={result['topics']}"
    )
    return {"code": 200, "data": result}


@app.get("/api/health", summary="健康检查")
def health_check():
    return {
        "code": 200,
        "status": "running",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ═══════════════════════════════════════════════
# 启动入口
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info",
    )
