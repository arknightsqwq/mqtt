# -*- coding: utf-8 -*-
"""
前后端联合测试脚本
- 自动启动后端 -> 执行全部 API 测试 -> 关闭后端 -> 输出报告
用法: python tests/test_api.py
"""

import io
import os
import subprocess
import time
import sys
import json
import traceback
from datetime import datetime

# 强制 UTF-8 输出，解决 Windows GBK 乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests

# ══════════════════════════════ 配置 ══════════════════════════════
BASE_URL = "http://localhost:8000/api"
ADMIN_TOKEN = "admin123"
BACKEND_CMD = [sys.executable, "main.py"]
STARTUP_TIMEOUT = 10

# ══════════════════════════════ 工具 ══════════════════════════════
pass_count = 0
fail_count = 0
failures: list[str] = []


def ok(label: str):
    global pass_count
    pass_count += 1
    print(f"  [PASS] {label}")


def fail(label: str, detail: str = ""):
    global fail_count
    fail_count += 1
    msg = f"  [FAIL] {label}"
    if detail:
        msg += f"  --  {detail}"
    print(msg)
    failures.append(msg)


def assert_eq(actual, expected, label: str):
    if actual == expected:
        ok(label)
    else:
        fail(label, f"expected {expected!r}, got {actual!r}")


def assert_code(resp, expected_code: int, label: str):
    status = resp.status_code
    if status == expected_code:
        ok(f"{label} [HTTP {status}]")
    else:
        body = ""
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:200]
        fail(f"{label} [HTTP {status}]", f"expected {expected_code}, body={body}")


def assert_in(resp, key: str, label: str):
    body = resp.json()
    if key in body:
        ok(label)
    else:
        fail(label, f"response missing field {key!r}")


def get(endpoint: str, headers: dict | None = None):
    return requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=5)


def post(endpoint: str, data: dict, headers: dict | None = None):
    return requests.post(f"{BASE_URL}{endpoint}", json=data, headers=headers, timeout=5)


def put(endpoint: str, data: dict, headers: dict | None = None):
    return requests.put(f"{BASE_URL}{endpoint}", json=data, headers=headers, timeout=5)


def delete(endpoint: str, headers: dict | None = None):
    return requests.delete(f"{BASE_URL}{endpoint}", headers=headers, timeout=5)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def admin_header() -> dict:
    return {"X-Admin-Token": ADMIN_TOKEN}


# ══════════════════════════════ 测试用例 ══════════════════════════════

def test_health():
    print("\n-- [1] Health Check")
    r = get("/health")
    assert_code(r, 200, "GET /health")
    body = r.json()
    assert_eq(body.get("code"), 200, "code=200")
    assert_eq(body.get("status"), "running", "status=running")


def test_user_register():
    print("\n-- [2] User Register")
    r = post("/user/register", {"user_id": "testuser", "password": "123456"})
    assert_code(r, 200, "register new user")
    assert_eq(r.json().get("msg"), "注册成功", "msg=注册成功")

    r = post("/user/register", {"user_id": "testuser", "password": "654321"})
    assert_code(r, 400, "duplicate user rejected")

    r = post("/user/register", {"user_id": "testuser2", "password": "123456"})
    assert_code(r, 200, "register second user")


def test_user_login():
    print("\n-- [3] User Login")
    r = post("/user/login", {"user_id": "testuser", "password": "123456"})
    assert_code(r, 200, "login with correct password")
    assert_in(r, "access_token", "has access_token")
    body = r.json()
    assert_eq(body.get("user_id"), "testuser", "user_id=testuser")
    token = body.get("access_token", "")

    r = post("/user/login", {"user_id": "testuser", "password": "wrong"})
    assert_code(r, 401, "wrong password rejected")

    r = post("/user/login", {"user_id": "nobody", "password": "123456"})
    assert_code(r, 401, "non-existent user rejected")

    return token


def test_unauthorized(token: str):
    print("\n-- [4] Auth Interception")
    r = post("/user/logout", {})
    assert_code(r, 401, "no token -> 401")

    r = post("/user/logout", {}, headers=auth_header("fake.jwt.token"))
    assert_code(r, 401, "fake token -> 401")

    r = post("/user/logout", {}, headers=auth_header(token))
    assert_code(r, 200, "valid token -> 200")


def test_admin_auth():
    print("\n-- [5] Admin Auth")
    r = get("/admin/users")
    assert_code(r, 403, "no admin token -> 403")

    r = get("/admin/users", headers={"X-Admin-Token": "wrong"})
    assert_code(r, 403, "wrong admin token -> 403")

    r = get("/admin/users", headers=admin_header())
    assert_code(r, 200, "correct admin token -> 200")


def test_admin_device_register():
    print("\n-- [6] Admin Register Device")
    h = admin_header()
    r = post("/device/register", {
        "device_id": "dev001", "device_name": "Sensor-A", "device_desc": "Floor 1"
    }, headers=h)
    assert_code(r, 200, "register dev001")
    assert_eq(r.json().get("msg"), "设备注册入库成功", "success message")

    r = post("/device/register", {"device_id": "dev001", "device_name": "dup"}, headers=h)
    assert_code(r, 400, "duplicate dev001 rejected")

    post("/device/register", {"device_id": "dev002", "device_name": "Sensor-B"}, headers=h)
    post("/device/register", {"device_id": "dev003", "device_name": "Sensor-C"}, headers=h)
    ok("register dev002, dev003")


def test_admin_list_devices():
    print("\n-- [7] Admin List Devices")
    r = get("/admin/devices", headers=admin_header())
    assert_code(r, 200, "list devices")
    body = r.json()
    devices = body.get("data", {}).get("devices", [])
    assert_eq(len(devices), 3, "total=3 devices")
    assert_in(r, "data", "has data field")


def test_bind_device(token: str):
    print("\n-- [8] Bind Device")
    h = auth_header(token)
    r = post("/user/bind_device", {"device_id": "dev001"}, headers=h)
    assert_code(r, 200, "bind dev001 ok")

    r = post("/user/bind_device", {"device_id": "dev002"}, headers=h)
    assert_code(r, 200, "bind dev002 ok")

    r = post("/user/bind_device", {"device_id": "dev001"}, headers=h)
    assert_code(r, 400, "duplicate bind rejected")

    r = post("/user/bind_device", {"device_id": "dev999"}, headers=h)
    assert_code(r, 400, "non-existent device rejected")


def test_unbind_device(token: str):
    print("\n-- [9] Unbind Device")
    h = auth_header(token)
    r = post("/user/unbind_device", {"device_id": "dev002"}, headers=h)
    assert_code(r, 200, "unbind dev002 ok")

    r = post("/user/unbind_device", {"device_id": "dev002"}, headers=h)
    assert_code(r, 400, "duplicate unbind rejected")

    post("/user/bind_device", {"device_id": "dev002"}, headers=h)
    ok("re-bind dev002")


def test_login_returns_bound_devices():
    print("\n-- [10] Login Returns Bound Devices")
    r = post("/user/login", {"user_id": "testuser", "password": "123456"})
    assert_code(r, 200, "login ok")
    body = r.json()
    devices = body.get("bind_devices", [])
    ids = [d["device_id"] for d in devices]
    assert_eq("dev001" in ids, True, "includes dev001")
    assert_eq("dev002" in ids, True, "includes dev002")
    assert_eq(len(devices), 2, "total=2 bound devices")
    return body.get("access_token", "")


def test_device_query(token: str):
    print("\n-- [11] Device Data Query")
    h = auth_header(token)
    # user with no bound devices
    r2 = post("/user/login", {"user_id": "testuser2", "password": "123456"})
    tk2 = r2.json().get("access_token", "")
    r = post("/device/query", {"page": 1, "page_size": 10}, headers=auth_header(tk2))
    assert_code(r, 200, "no-bound-devices returns empty")
    assert_eq(r.json().get("data", {}).get("total", 0), 0, "total=0")

    # user with bound devices
    r = post("/device/query", {"page": 1, "page_size": 10}, headers=h)
    assert_code(r, 200, "bound user query ok")
    assert_in(r, "data", "has data field")

    # with filters
    r = post("/device/query", {
        "device_id": "dev001",
        "start_time": "2025-01-01 00:00:00",
        "end_time": "2030-12-31 23:59:59",
        "page": 1, "page_size": 10,
    }, headers=h)
    assert_code(r, 200, "filtered query ok")


def test_send_cmd(token: str):
    print("\n-- [12] Send Device Command")
    h = auth_header(token)
    r = post("/device/send_cmd", {
        "device_id": "dev001",
        "command": '{"action":"reboot"}',
    }, headers=h)
    assert_code(r, 200, "send cmd ok")
    assert_in(r, "msg", "has msg field")

    r = post("/device/send_cmd", {"device_id": "dev003", "command": "ping"}, headers=h)
    assert_code(r, 403, "unbound device rejected")


def test_admin_create_user():
    print("\n-- [13] Admin Create User")
    h = admin_header()
    r = post("/admin/user/create", {"user_id": "admuser", "new_password": "pass123"}, headers=h)
    assert_code(r, 200, "create user with password")

    r = post("/admin/user/create", {"user_id": "admuser2"}, headers=h)
    assert_code(r, 200, "create user with default password")

    r = post("/admin/user/create", {"user_id": "admuser"}, headers=h)
    assert_code(r, 400, "duplicate user rejected")


def test_admin_list_users():
    print("\n-- [14] Admin List Users")
    r = get("/admin/users", headers=admin_header())
    assert_code(r, 200, "list users")
    body = r.json()
    users = body.get("data", {}).get("users", [])
    assert_eq(len(users), 4, "total=4 users (testuser, testuser2, admuser, admuser2)")


def test_admin_toggle_status():
    print("\n-- [15] Admin Enable/Disable User")
    h = admin_header()
    r = put("/admin/user/status", {"user_id": "testuser2", "is_disabled": True}, headers=h)
    assert_code(r, 200, "disable testuser2")

    r = post("/user/login", {"user_id": "testuser2", "password": "123456"})
    assert_code(r, 403, "disabled user login rejected")

    r = put("/admin/user/status", {"user_id": "testuser2", "is_disabled": False}, headers=h)
    assert_code(r, 200, "enable testuser2")

    r = post("/user/login", {"user_id": "testuser2", "password": "123456"})
    assert_code(r, 200, "re-enabled user login ok")


def test_admin_reset_password():
    print("\n-- [16] Admin Reset Password")
    h = admin_header()
    r = put("/admin/user/password", {"user_id": "testuser2", "new_password": "newpass666"}, headers=h)
    assert_code(r, 200, "reset password ok")

    r = post("/user/login", {"user_id": "testuser2", "password": "123456"})
    assert_code(r, 401, "old password invalid")

    r = post("/user/login", {"user_id": "testuser2", "password": "newpass666"})
    assert_code(r, 200, "new password ok")

    put("/admin/user/password", {"user_id": "testuser2", "new_password": "123456"}, headers=h)
    ok("restored original password")


def test_admin_delete_device():
    print("\n-- [17] Admin Delete Device")
    h = admin_header()
    r = delete("/device/dev003", headers=h)
    assert_code(r, 200, "delete dev003")

    r = delete("/device/dev003", headers=h)
    assert_code(r, 404, "re-delete returns 404")

    r = get("/admin/devices", headers=h)
    devices = r.json().get("data", {}).get("devices", [])
    assert_eq(len(devices), 2, "remaining=2 devices")


def test_validation():
    print("\n-- [18] Input Validation")
    r = post("/user/register", {"user_id": "nopwd"})
    assert_code(r, 422, "missing field -> 422")

    r = post("/user/login", {})
    assert_code(r, 422, "empty body -> 422")

    token = post("/user/login", {"user_id": "testuser", "password": "123456"}).json().get("access_token", "")
    r = post("/device/query", {"page": 1, "page_size": 9999}, headers=auth_header(token))
    assert_code(r, 200, "huge page_size does not crash")


# ══════════════════════════════ 主流程 ══════════════════════════════

def main():
    global pass_count, fail_count, failures

    print("=" * 60)
    print("  Backend API Integration Test")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ── 启动后端 ──
    print("\n[INFO] Starting backend server...")
    proc = subprocess.Popen(
        BACKEND_CMD,
        cwd=".",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 等待就绪
    ready = False
    for i in range(STARTUP_TIMEOUT * 2):
        time.sleep(0.5)
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                ready = True
                print(f"[INFO] Backend ready ({r.json().get('status')})")
                break
        except Exception:
            pass
    if not ready:
        print("[ERROR] Backend failed to start within timeout!")
        proc.kill()
        return 1

    try:
        # 先清残留数据
        import pymysql
        conn = pymysql.connect(host="localhost", port=3306, user="root", passwd="mysql", db="mqtt_device_db")
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")
            for t in ("device_data", "user_device_bind", "device_info", "user_info"):
                cur.execute(f"TRUNCATE TABLE {t}")
            cur.execute("SET FOREIGN_KEY_CHECKS=1")
        conn.close()
        print("\n[INFO] Database cleaned\n")

        test_health()
        test_user_register()
        token = test_user_login()
        test_unauthorized(token)
        test_admin_auth()
        test_admin_device_register()
        test_admin_list_devices()
        # bind before checking login response
        test_bind_device(token)
        token = test_login_returns_bound_devices()
        test_unbind_device(token)
        test_device_query(token)
        test_send_cmd(token)
        test_admin_create_user()
        test_admin_list_users()
        test_admin_toggle_status()
        test_admin_reset_password()
        test_admin_delete_device()
        test_validation()

    except Exception:
        print(f"\n[ERROR] Test crashed:\n{traceback.format_exc()}")
        failures.append("FATAL: test raised exception")

    finally:
        print("\n[INFO] Stopping backend...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("[INFO] Backend stopped")

    # ── 统计 ──
    total = pass_count + fail_count
    print("\n" + "=" * 60)
    print("  TEST REPORT")
    print("=" * 60)
    print(f"  Total:   {total}")
    print(f"  Passed:  {pass_count}")
    print(f"  Failed:  {fail_count}")
    if total:
        print(f"  Rate:    {pass_count / total * 100:.1f}%")
    print("=" * 60)

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  {f}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
