"""
集中配置管理 —— 从 .env 加载所有配置项，提供类型化访问。
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── 应用 ──
    APP_TITLE: str = os.getenv("APP_TITLE", "设备数据管理后端")
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # ── 数据库 ──
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASS: str = os.getenv("DB_PASS", "")
    DB_NAME: str = os.getenv("DB_NAME", "mqtt_device_db")
    DB_CHARSET: str = os.getenv("DB_CHARSET", "utf8mb4")
    # 连接池参数
    DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN", "2"))
    DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX", "5"))
    DB_POOL_MAX_CONNS: int = int(os.getenv("DB_POOL_MAX_CONNS", "10"))

    # ── EMQX ──
    EMQX_HOST: str = os.getenv("EMQX_HOST", "localhost")
    EMQX_PORT: int = int(os.getenv("EMQX_PORT", "1883"))
    EMQX_USER: str = os.getenv("EMQX_USER", "")
    EMQX_PASS: str = os.getenv("EMQX_PASS", "")
    # EMQX REST API (管理接口，默认端口 18083)
    EMQX_API_HOST: str = os.getenv("EMQX_API_HOST", "localhost")
    EMQX_API_PORT: int = int(os.getenv("EMQX_API_PORT", "18083"))
    EMQX_API_KEY: str = os.getenv("EMQX_API_KEY", "")
    EMQX_API_SECRET: str = os.getenv("EMQX_API_SECRET", "")
    # MQTT 订阅主题列表，格式: "topic:qos,topic:qos,..."
    _raw_topics: str = os.getenv(
        "SUBSCRIBE_TOPICS",
        "device/+/telemetry:1,device/+/alert:2,device/+/status:1,device/+/data:1",
    )

    @property
    def SUBSCRIBE_TOPICS(self) -> list[tuple[str, int]]:
        """解析订阅主题列表，返回 [(topic, qos), ...]"""
        result = []
        for item in self._raw_topics.split(","):
            item = item.strip()
            if not item:
                continue
            if ":" in item:
                topic, qos = item.rsplit(":", 1)
                result.append((topic.strip(), int(qos)))
            else:
                result.append((item, 1))
        return result

    # ── JWT ──
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

    # ── 管理员 ──
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "admin123")

    # ── 分页 ──
    PAGE_SIZE_MAX: int = int(os.getenv("PAGE_SIZE_MAX", "100"))


settings = Settings()
