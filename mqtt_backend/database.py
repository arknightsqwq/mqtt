"""
数据库工具 —— 连接池 + 上下文管理器 + 常用查询封装。
使用 DBUtils 实现 pymysql 连接池，避免每次请求都新建连接。
"""
import json as _json
from contextlib import contextmanager
from typing import Optional, Any

import pymysql
from dbutils.pooled_db import PooledDB
from passlib.context import CryptContext
from fastapi import HTTPException

from config import settings

# ── 密码加密上下文 ──
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── 连接池（全局单例） ──
_pool: Optional[PooledDB] = None


def _create_pool() -> PooledDB:
    return PooledDB(
        creator=pymysql,
        mincached=settings.DB_POOL_MIN,
        maxcached=settings.DB_POOL_MAX,
        maxconnections=settings.DB_POOL_MAX_CONNS,
        blocking=True,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASS,
        database=settings.DB_NAME,
        charset=settings.DB_CHARSET,
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_pool() -> PooledDB:
    global _pool
    if _pool is None:
        _pool = _create_pool()
    return _pool


@contextmanager
def get_conn():
    """获取数据库连接的上下文管理器，自动归还到连接池。"""
    pool = get_pool()
    conn = pool.connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(conn=None, dict_cursor: bool = True):
    """获取游标的上下文管理器，自动关闭。"""
    if conn is None:
        with get_conn() as conn:
            cursor = conn.cursor(
                pymysql.cursors.DictCursor if dict_cursor else pymysql.cursors.Cursor
            )
            try:
                yield cursor, conn
            finally:
                cursor.close()
    else:
        cursor = conn.cursor(
            pymysql.cursors.DictCursor if dict_cursor else pymysql.cursors.Cursor
        )
        try:
            yield cursor
        finally:
            cursor.close()


def check_db_connection() -> bool:
    """启动时检测数据库连通性。"""
    print("\n[数据库] 正在检测连接...")
    try:
        with get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            print(
                f"[数据库] 连接成功 → "
                f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            )
            return True
    except Exception as e:
        print(f"[数据库] 连接失败 → {e}")
        return False


# ── 密码工具 ──
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JSON 列工具：统一处理 MySQL JSON 列返回类型不一致 ──

def json_to_str(value: Any) -> str | None:
    """dict → JSON 字符串；已是字符串则原样返回；None → None。"""
    if value is None:
        return None
    if isinstance(value, dict):
        return _json.dumps(value, ensure_ascii=False)
    return value


def json_to_dict(value: Any) -> dict | list | None:
    """JSON 字符串 → dict/list；已是 dict/list 则原样返回；None → None。"""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return _json.loads(value)
        except _json.JSONDecodeError:
            return None
    if isinstance(value, (dict, list)):
        return value
    return None


# ── 操作日志 ──
def log_operation(user_id: str | None, action: str, target: str | None = None,
                  detail: str | None = None, ip: str | None = None):
    """写入操作日志（不抛异常，日志失败不影响主流程）。"""
    try:
        with get_conn() as conn:
            with get_cursor(conn, dict_cursor=False) as cursor:
                cursor.execute(
                    "INSERT INTO operation_logs (user_id, action, target, detail, ip) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (user_id, action, target, detail, ip),
                )
                conn.commit()
    except Exception:
        pass  # 日志写入失败不影响业务
