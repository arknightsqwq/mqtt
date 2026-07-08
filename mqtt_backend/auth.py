"""
认证模块 —— JWT 签发/校验 + 管理员权限校验 + 设备绑定校验。
- get_current_user:      从 Authorization: Bearer <token> 中解析 user_id
- verify_admin:           从 X-Admin-Token 头中校验管理员令牌
- verify_device_bind:     校验当前用户是否绑定了指定设备（消除 6 处重复代码）
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Header, HTTPException, Depends, Path
from jose import JWTError, jwt

from config import settings


# ── JWT ──
def create_access_token(user_id: str) -> str:
    """签发 JWT 访问令牌，默认24小时过期。"""
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """解析 JWT 令牌，成功返回 user_id，失败返回 None。"""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        return None


# ── FastAPI 依赖注入 ──
def get_current_user(authorization: str = Header(None)) -> str:
    """
    FastAPI 依赖：从 Authorization 头中提取并验证 JWT。
    用法: def my_route(user_id: str = Depends(get_current_user)): ...
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少认证令牌")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="认证格式错误，应为 Bearer <token>")
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    return user_id


def verify_admin(x_admin_token: str = Header(None)) -> None:
    """
    FastAPI 依赖：校验管理员令牌。
    用法: def admin_route(..., _=Depends(verify_admin)): ...
    """
    if not x_admin_token or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="无管理员权限")


def verify_device_bind(
    device_id: str = Path(...),
    user_id: str = Depends(get_current_user),
) -> str:
    """
    FastAPI 依赖：校验当前用户是否绑定了指定设备（路径参数）。
    绑定关系不存在时自动抛出 403。

    用法（替代原来的手写 4 行校验）:
        def my_route(device_id: str, user_id: str = Depends(verify_device_bind)):
            ...
    """
    check_device_bind(device_id, user_id)
    return user_id


def check_device_bind(device_id: str, user_id: str) -> None:
    """
    校验用户是否绑定了指定设备（适用于 device_id 在请求体中而非路径参数的场景）。
    未绑定时抛出 403。

    用法:
        check_device_bind(data.device_id, user_id)
    """
    from database import get_conn, get_cursor

    with get_conn() as conn:
        with get_cursor(conn, dict_cursor=False) as cursor:
            cursor.execute(
                "SELECT 1 FROM user_device_bind WHERE user_id=%s AND device_id=%s LIMIT 1",
                (user_id, device_id),
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=403, detail="无权限操作该设备")
