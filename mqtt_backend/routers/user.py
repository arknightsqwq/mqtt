"""
用户端路由
─────────
- 用户注册 / 登录 / 登出 / 绑定查询
- 设备绑定 / 解绑
- 设备数据查询 / 指令下发 / 配置下发
"""
from fastapi import APIRouter, HTTPException, Depends, Request

from config import settings
from database import get_conn, get_cursor, hash_password, verify_password, log_operation, json_to_str
from auth import create_access_token, get_current_user, check_device_bind
from models import (
    UserLogin, UserRegister,
    DeviceBind, DeviceUnbind, DeviceDataQuery, DeviceCommand,
)

router = APIRouter(tags=["用户端"])


# ── 用户账户 ──

@router.post("/api/user/register", summary="用户注册")
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
    return {"code": 200, "msg": "注册成功"}


@router.post("/api/user/login", summary="用户登录")
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
    log_operation(data.user_id, "login", ip=request.client.host if request.client else None)
    return {
        "code": 200,
        "msg": "登录成功",
        "access_token": token,
        "token_type": "bearer",
        "user_id": data.user_id,
        "bind_devices": bind_devices,
    }


@router.get("/api/user/bindings", summary="获取用户当前绑定设备")
def user_bindings(user_id: str = Depends(get_current_user)):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                """SELECT ub.device_id, di.device_name, di.device_desc
                   FROM user_device_bind ub
                   LEFT JOIN device_info di ON ub.device_id = di.device_id
                   WHERE ub.user_id=%s""",
                (user_id,),
            )
            bind_devices = cursor.fetchall()
    return {"code": 200, "data": {"bind_devices": bind_devices}}


@router.post("/api/user/logout", summary="用户退出登录")
def user_logout(user_id: str = Depends(get_current_user)):
    return {"code": 200, "msg": "退出登录成功"}


# ── 设备绑定 ──

@router.post("/api/user/bind_device", summary="绑定设备")
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
    return {"code": 200, "msg": "设备绑定成功"}


@router.post("/api/user/unbind_device", summary="解绑设备")
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
    return {"code": 200, "msg": "设备解绑成功"}


# ── 设备数据 ──

@router.post("/api/device/query", summary="查询设备数据")
def query_device_data(data: DeviceDataQuery, user_id: str = Depends(get_current_user)):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
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

            cursor.execute(
                f"SELECT COUNT(*) AS total FROM device_data d WHERE {where}", params
            )
            total = cursor.fetchone()["total"]

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
        data_list.append({
            "id": r["id"],
            "device_id": r["device_id"],
            "device_name": r["device_name"],
            "message_type": r["message_type"],
            "raw_json": json_to_str(r["raw_json"]),
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


@router.post("/api/device/send_cmd", summary="下发设备指令")
def send_device_cmd(data: DeviceCommand, user_id: str = Depends(get_current_user)):
    check_device_bind(data.device_id, user_id)
    from main import mqtt_client
    mqtt_client.publish_cmd(data.device_id, data.command)
    return {"code": 200, "msg": f"指令已下发到设备 {data.device_id}"}


@router.post("/api/device/send_config", summary="下发设备配置")
def send_device_config(data: DeviceCommand, user_id: str = Depends(get_current_user)):
    check_device_bind(data.device_id, user_id)
    from main import mqtt_client
    mqtt_client.publish_config(data.device_id, data.command)
    return {"code": 200, "msg": f"配置已下发到设备 {data.device_id}"}
