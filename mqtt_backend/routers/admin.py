"""
运维端路由
─────────
- 设备注册 / 删除 / 配置更新
- 用户创建 / 密码重置 / 状态切换 / 列表
- 批量导入 / 操作日志 / MQTT 消息查询
- 管理首页概览 / EMQX 状态
"""
import base64
import json
import logging
import urllib.request

from fastapi import APIRouter, HTTPException, Depends, Request

from config import settings
from database import get_conn, get_cursor, hash_password, log_operation, json_to_str
from auth import verify_admin
from models import DeviceRegister, AdminUserOperate

logger = logging.getLogger("mqtt_backend")
router = APIRouter(tags=["运维端"])


# ── 设备管理 ──

@router.post("/api/device/register", summary="【运维】设备注册入库")
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
                "INSERT INTO device_info (device_id, device_name, device_desc, config_json, field_labels) "
                "VALUES (%s, %s, %s, %s, %s)",
                (data.device_id, data.device_name, data.device_desc,
                 json.dumps(data.config_json, ensure_ascii=False) if data.config_json else None,
                 json.dumps(data.field_labels, ensure_ascii=False) if data.field_labels else None),
            )
            conn.commit()
    log_operation("admin", "register_device", data.device_id,
                  f"name={data.device_name}",
                  request.client.host if request and request.client else None)
    return {"code": 200, "msg": "设备注册入库成功"}


@router.delete("/api/device/{device_id}", summary="【运维】删除设备")
def device_delete(device_id: str, _: None = Depends(verify_admin)):
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM device_info WHERE device_id=%s LIMIT 1", (device_id,)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="设备不存在")
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
    log_operation("admin", "delete_device", device_id)
    return {"code": 200, "msg": f"设备 {device_id} 已删除"}


@router.put("/api/admin/device/{device_id}/config", summary="【运维】更新设备配置模板")
async def admin_update_device_config(
    device_id: str, request: Request, _: None = Depends(verify_admin),
):
    data = await request.json()
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM device_info WHERE device_id=%s LIMIT 1", (device_id,)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="设备不存在")
            cursor.execute(
                "UPDATE device_info SET config_json=%s WHERE device_id=%s",
                (json.dumps(data, ensure_ascii=False), device_id),
            )
            conn.commit()
    log_operation("admin", "update_device_config", device_id)
    return {"code": 200, "msg": f"设备 {device_id} 配置已更新"}


@router.put("/api/admin/device/{device_id}/field-labels", summary="【运维】更新设备字段标签")
async def admin_update_device_field_labels(
    device_id: str, request: Request, _: None = Depends(verify_admin),
):
    data = await request.json()
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM device_info WHERE device_id=%s LIMIT 1", (device_id,)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="设备不存在")
            cursor.execute(
                "UPDATE device_info SET field_labels=%s WHERE device_id=%s",
                (json.dumps(data, ensure_ascii=False), device_id),
            )
            conn.commit()
    log_operation("admin", "update_device_field_labels", device_id)
    return {"code": 200, "msg": f"设备 {device_id} 字段标签已更新"}


# ── 用户管理 ──

@router.post("/api/admin/user/create", summary="【运维】创建用户")
def admin_create_user(data: AdminUserOperate, _: None = Depends(verify_admin)):
    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM user_info WHERE user_id=%s", (data.user_id,)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="用户已存在")
            pwd = data.new_password or settings.DEFAULT_USER_PASSWORD
            cursor.execute(
                "INSERT INTO user_info (user_id, user_password, status) VALUES (%s, %s, 1)",
                (data.user_id, hash_password(pwd)),
            )
            conn.commit()
    log_operation("admin", "create_user", data.user_id)
    return {"code": 200, "msg": f"用户 {data.user_id} 创建成功"}


@router.put("/api/admin/user/password", summary="【运维】重置用户密码")
def admin_update_user(data: AdminUserOperate, _: None = Depends(verify_admin)):
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
    log_operation("admin", "reset_pwd", data.user_id)
    return {"code": 200, "msg": f"用户 {data.user_id} 密码已重置"}


@router.put("/api/admin/user/status", summary="【运维】禁用/启用用户")
def admin_disable_user(data: AdminUserOperate, _: None = Depends(verify_admin)):
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
    log_operation("admin", "disable_user" if data.is_disabled else "enable_user", data.user_id)
    return {"code": 200, "msg": f"用户 {data.user_id} 已{action}"}


@router.get("/api/admin/users", summary="【运维】用户列表")
def admin_list_users(_: None = Depends(verify_admin)):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute("SELECT user_id, status FROM user_info ORDER BY user_id")
            users = cursor.fetchall()
    return {"code": 200, "data": {"users": users}}


@router.get("/api/admin/devices", summary="【运维】设备列表")
def admin_list_devices(_: None = Depends(verify_admin)):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                """SELECT di.device_id, di.device_name, di.device_desc, di.config_json,
                          di.field_labels,
                          di.is_online, di.last_online_time, di.last_offline_time,
                          COUNT(ub.user_id) AS bind_count
                   FROM device_info di
                   LEFT JOIN user_device_bind ub ON di.device_id = ub.device_id
                   GROUP BY di.device_id
                   ORDER BY di.device_id"""
            )
            devices = cursor.fetchall()
    return {"code": 200, "data": {"devices": devices}}


# ── 批量导入 ──

@router.post("/api/admin/device/batch_register", summary="【运维】批量注册设备")
def device_batch_register(items: list[DeviceRegister], _: None = Depends(verify_admin)):
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
                    "INSERT INTO device_info (device_id, device_name, device_desc, field_labels) "
                    "VALUES (%s, %s, %s, %s)",
                    (d.device_id, d.device_name, d.device_desc,
                     json.dumps(d.field_labels, ensure_ascii=False) if d.field_labels else None),
                )
                success += 1
            conn.commit()
    log_operation("admin", "batch_register_device", None, f"success={success} skipped={skipped}")
    return {"code": 200, "msg": f"成功 {success} 台, 跳过 {skipped} 台（已存在）", "data": {"success": success, "skipped": skipped}}


@router.post("/api/admin/user/batch_create", summary="【运维】批量创建用户")
def user_batch_create(items: list[AdminUserOperate], _: None = Depends(verify_admin)):
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
                pwd = u.new_password or settings.DEFAULT_USER_PASSWORD
                cursor.execute(
                    "INSERT INTO user_info (user_id, user_password, status) VALUES (%s, %s, 1)",
                    (u.user_id, hash_password(pwd)),
                )
                success += 1
            conn.commit()
    log_operation("admin", "batch_create_user", None, f"success={success} skipped={skipped}")
    return {"code": 200, "msg": f"成功 {success} 个, 跳过 {skipped} 个（已存在）", "data": {"success": success, "skipped": skipped}}


# ── 操作日志 ──

@router.get("/api/admin/logs", summary="【运维】操作日志查询")
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
            "id": r["id"], "user_id": r["user_id"],
            "action": r["action"], "target": r["target"],
            "detail": r["detail"], "ip": r["ip"],
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
        })
    return {"code": 200, "data": {"list": logs, "total": total}}


# ── MQTT 消息查询 ──

@router.get("/api/admin/messages", summary="【运维】MQTT 消息查询")
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
        msgs.append({
            "id": r["id"],
            "device_id": r["device_id"],
            "device_name": r["device_name"],
            "message_type": r["message_type"],
            "raw_json": json_to_str(r["raw_json"]),
            "upload_time": r["upload_time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        })
    return {"code": 200, "data": {"list": msgs, "total": total}}


# ── 管理概览 ──

@router.get("/api/admin/overview", summary="【运维】管理首页概览")
def admin_overview(_: None = Depends(verify_admin)):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute("SELECT COUNT(*) AS t FROM device_info")
            dev_total = cursor.fetchone()["t"]
            cursor.execute("SELECT COUNT(*) AS t FROM device_info WHERE is_online=1")
            dev_online = cursor.fetchone()["t"]

            cursor.execute("SELECT COUNT(*) AS t FROM user_info")
            usr_total = cursor.fetchone()["t"]
            cursor.execute("SELECT COUNT(*) AS t FROM user_info WHERE status=1")
            usr_active = cursor.fetchone()["t"]
            cursor.execute("SELECT COUNT(*) AS t FROM user_info WHERE status=0")
            usr_disabled = cursor.fetchone()["t"]

            cursor.execute("SELECT COUNT(*) AS t FROM device_data WHERE upload_time >= CURDATE()")
            today_msg = cursor.fetchone()["t"]
            cursor.execute(
                "SELECT COUNT(*) AS t FROM device_data "
                "WHERE upload_time >= CURDATE() AND message_type='alert'"
            )
            today_alert = cursor.fetchone()["t"]
            cursor.execute(
                "SELECT COUNT(*) AS t FROM device_data "
                "WHERE upload_time >= CURDATE() AND message_type='gps'"
            )
            today_telemetry = cursor.fetchone()["t"]

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
            "device_total": dev_total, "device_online": dev_online,
            "device_offline": dev_total - dev_online,
            "user_total": usr_total, "user_active": usr_active,
            "user_disabled": usr_disabled,
            "today_messages": today_msg, "today_alerts": today_alert,
            "today_telemetry": today_telemetry,
            "recent_logs": logs,
        },
    }


@router.get("/api/admin/emqx-info", summary="【运维】EMQX Broker 状态")
def admin_emqx_info(_: None = Depends(verify_admin)):
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

    nodes_data = _get("/api/v5/nodes")
    stats_data = _get("/api/v5/stats")

    result = {
        "reachable": False, "version": "", "uptime_seconds": 0,
        "uptime_display": "", "node_status": "", "edition": "",
        "memory_used": "", "memory_total": "", "load1": 0.0,
        "load5": 0.0, "load15": 0.0, "connections": 0,
        "live_connections": 0, "sessions": 0, "topics": 0,
        "subscriptions": 0, "retained": 0, "channels": 0,
        "max_fds": 0, "process_used": 0, "process_available": 0,
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

        secs = result["uptime_seconds"]
        days, rem = divmod(secs, 86400)
        hours, rem = divmod(rem, 3600)
        mins, _ = divmod(rem, 60)
        parts = []
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if mins: parts.append(f"{mins}m")
        result["uptime_display"] = " ".join(parts) if parts else f"{secs}s"

    if stats_data:
        result["reachable"] = True
        s = _unwrap(stats_data)
        result["sessions"] = s.get("sessions.count", 0)
        result["topics"] = s.get("topics.count", 0)
        result["subscriptions"] = s.get("subscriptions.count", 0)
        result["retained"] = s.get("retained.count", 0)
        result["channels"] = s.get("channels.count", 0)

    return {"code": 200, "data": result}
