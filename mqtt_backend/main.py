"""
设备数据管理后端 —— FastAPI + MQTT + MySQL
───────────────────────────────────────────
- JWT 认证：用户端接口需 Bearer Token
- 管理员认证：运维接口需 X-Admin-Token 头
- 连接池：MySQL 连接复用，避免高并发下耗尽连接
- MQTT：全局共享客户端，自动重连，指令下发复用
- 日志：请求日志中间件，异常全局兜底

路由拆分：
- routers/user.py      用户端（注册/登录/绑定/设备数据查询）
- routers/admin.py     运维端（设备管理/用户管理/日志/EMQX）
- routers/dashboard.py 数据可视化（最新数据/时序/GPS轨迹/告警/录音）
"""
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import check_db_connection
from services.mqtt_client import MQTTClient

# 全局单例
mqtt_client = MQTTClient()

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
# 路由注册
# ═══════════════════════════════════════════════
from routers.user import router as user_router
from routers.admin import router as admin_router
from routers.dashboard import router as dashboard_router

app.include_router(user_router)
app.include_router(admin_router)
app.include_router(dashboard_router)


# ═══════════════════════════════════════════════
# 健康检查
# ═══════════════════════════════════════════════
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
