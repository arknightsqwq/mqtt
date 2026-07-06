"""
Pydantic 数据模型 —— 请求体 / 响应体校验。
用户端接口不再要求传 user_id，统一从 JWT 令牌中提取。
"""
from pydantic import BaseModel, field_validator

from config import settings


# ── 用户 ──
class UserLogin(BaseModel):
    user_id: str
    password: str


class UserRegister(BaseModel):
    user_id: str
    password: str


class LoginResponse(BaseModel):
    code: int = 200
    msg: str = "登录成功"
    access_token: str
    token_type: str = "bearer"
    user_id: str
    bind_devices: list[dict] = []


# ── 设备 ──
class DeviceRegister(BaseModel):
    device_id: str
    device_name: str
    device_desc: str = ""
    config_json: dict | None = None
    field_labels: dict | None = None


class DeviceBind(BaseModel):
    device_id: str


class DeviceUnbind(BaseModel):
    device_id: str


# ── 数据查询 ──
class DeviceDataQuery(BaseModel):
    device_id: str = ""
    start_time: str = ""
    end_time: str = ""
    page: int = 1
    page_size: int = 10

    @field_validator("page_size")
    @classmethod
    def clamp_page_size(cls, v: int) -> int:
        if v < 1:
            return 10
        if v > settings.PAGE_SIZE_MAX:
            return settings.PAGE_SIZE_MAX
        return v


# ── 指令下发 ──
class DeviceCommand(BaseModel):
    device_id: str
    command: str


# ── 管理员操作 ──
class AdminUserOperate(BaseModel):
    user_id: str
    new_password: str | None = None
    is_disabled: bool | None = None


class AdminDeviceDelete(BaseModel):
    device_id: str
