# -*- coding: utf-8 -*-
"""
模拟 IoT 设备向 MQTT Broker 上传数据（独立连接模式）
────────────────────────────────────────────────────
每台设备使用自己的 MQTT 客户端 + 独立账号密码连接 EMQX，
真实模拟"每设备独立认证"场景。

用法:
  python simulate_devices.py                        # 默认模拟 device_001 和 device_002
  python simulate_devices.py device_001              # 只模拟一台
  python simulate_devices.py device_001 device_003   # 模拟多台
  python simulate_devices.py --interval 5            # 上报间隔改为 5 秒（默认 10 秒）

依赖: pip install paho-mqtt
"""

import io
import json
import math
import random
import sys
import time
from datetime import datetime
from threading import Event

# 强制 UTF-8 输出，解决 Windows GBK 乱码
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import paho.mqtt.client as mqtt

# ═══════════════════════════════════════
# 配置
# ═══════════════════════════════════════
EMQX_HOST = "192.168.5.4"
EMQX_PORT = 1883

# 设备独立凭证：{device_id: password}
# 需与 EMQX 内置数据库中的用户密码一致
DEVICE_CREDENTIALS = {
    "device_001": "device_001_pass123",
    "device_002": "device_002_pass123",
    "device_003": "device_003_pass123",
}

# 默认模拟设备列表（设备ID → 设备类型 + 模拟参数）
DEFAULT_DEVICES = {
    "device_001": {
        "name": "温度传感器",
        "type": "temperature",
        "fields": {
            "temperature": {"base": 25.0, "noise": 3.0, "drift_period": 60},
            "humidity":    {"base": 55.0, "noise": 8.0, "drift_period": 120},
            "battery":     {"base": 85.0, "noise": 0.5, "drift_period": 3600},
            "rssi":        {"base": -55.0, "noise": 5.0, "drift_period": 0},
        },
    },
    "device_002": {
        "name": "湿度传感器",
        "type": "humidity",
        "fields": {
            "temperature": {"base": 22.0, "noise": 2.0, "drift_period": 45},
            "humidity":    {"base": 70.0, "noise": 5.0, "drift_period": 90},
            "pressure":    {"base": 1013.0, "noise": 2.0, "drift_period": 30},
            "battery":     {"base": 72.0, "noise": 0.3, "drift_period": 3600},
        },
    },
    "device_003": {
        "name": "空气质量监测器",
        "type": "air_quality",
        "fields": {
            "pm25":        {"base": 35.0, "noise": 15.0, "drift_period": 0},
            "pm10":        {"base": 50.0, "noise": 20.0, "drift_period": 0},
            "co2":         {"base": 450.0, "noise": 50.0, "drift_period": 120},
            "temperature": {"base": 24.0, "noise": 1.5, "drift_period": 60},
            "humidity":    {"base": 50.0, "noise": 6.0, "drift_period": 100},
        },
    },
}


def parse_args():
    devices = []
    interval = 10
    alert_every = 8

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--interval" and i + 1 < len(args):
            interval = float(args[i + 1])
            i += 2
        elif args[i] == "--alert-every" and i + 1 < len(args):
            alert_every = int(args[i + 1])
            i += 2
        elif not args[i].startswith("--"):
            devices.append(args[i])
            i += 1
        else:
            i += 1

    if not devices:
        devices = list(DEFAULT_DEVICES.keys())

    return devices, interval, alert_every


# ═══════════════════════════════════════
# 模拟数据生成
# ═══════════════════════════════════════
class DeviceSimulator:
    """单个设备的模拟器，用正弦波 + 噪声生成逼真传感器数据。"""

    def __init__(self, device_id: str, config: dict):
        self.device_id = device_id
        self.name = config["name"]
        self.type = config["type"]
        self.fields = config["fields"]
        self.tick = 0

    def generate_telemetry(self) -> dict:
        self.tick += 1
        data = {}
        for field_name, params in self.fields.items():
            base = params["base"]
            noise = params["noise"]
            drift_period = params.get("drift_period", 0)

            value = base + random.gauss(0, noise)

            if drift_period > 0:
                drift = math.sin(2 * math.pi * self.tick / drift_period) * noise * 1.5
                value += drift

            if field_name == "battery":
                value = min(100.0, max(0.0, value - self.tick * 0.001))

            data[field_name] = round(value, 2)

        return data

    def generate_alert(self) -> dict | None:
        telemetry = self.generate_telemetry()
        alert_types = []

        if self.type == "temperature" and telemetry.get("temperature", 25) > 30:
            alert_types.append({
                "type": "high_temperature",
                "severity": "warning",
                "message": f"温度偏高: {telemetry['temperature']}°C，超过 30°C 阈值",
                "current_value": telemetry["temperature"],
                "threshold": 30,
            })
        if telemetry.get("battery", 100) < 20:
            alert_types.append({
                "type": "low_battery",
                "severity": "high",
                "message": f"电池电量低: {telemetry['battery']}%，请及时更换",
                "current_value": telemetry["battery"],
                "threshold": 20,
            })
        if self.type == "air_quality" and telemetry.get("pm25", 0) > 75:
            alert_types.append({
                "type": "high_pm25",
                "severity": "high",
                "message": f"PM2.5 超标: {telemetry['pm25']} µg/m³ > 75 µg/m³",
                "current_value": telemetry["pm25"],
                "threshold": 75,
            })

        if alert_types:
            return random.choice(alert_types)
        return None


# ═══════════════════════════════════════
# 独立设备 MQTT 客户端（每设备一条连接）
# ═══════════════════════════════════════
class DeviceMQTTClient:
    """单台设备的 MQTT 客户端，使用设备自己的账号密码独立连接。"""

    def __init__(self, device_id: str, password: str):
        self.device_id = device_id
        self.stats = {"telemetry": 0, "alert": 0, "status": 0}
        self._connected = Event()

        self.client = mqtt.Client(
            client_id=device_id,
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(device_id, password)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        # 自动重连
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected.set()
            print(f"  [{datetime.now():%H:%M:%S}] ✓ {self.device_id} 已连接 EMQX")
        else:
            print(f"  [{datetime.now():%H:%M:%S}] ✗ {self.device_id} 连接失败, rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"  [{datetime.now():%H:%M:%S}] ⚠ {self.device_id} 断开 (rc={rc})，自动重连...")

    def connect(self, timeout: float = 5.0):
        """连接 EMQX 并等待确认。"""
        self.client.connect(EMQX_HOST, EMQX_PORT, 60)
        self.client.loop_start()
        if not self._connected.wait(timeout):
            print(f"  [{datetime.now():%H:%M:%S}] ✗ {self.device_id} 连接超时！")
            return False
        return True

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, subtopic: str, payload: dict | str):
        topic = f"device/{self.device_id}/{subtopic}"
        if isinstance(payload, dict):
            payload = json.dumps(payload, ensure_ascii=False)
        result = self.client.publish(topic, payload, qos=1)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            self.stats[subtopic] = self.stats.get(subtopic, 0) + 1
        return result

    def send_status(self, online: bool = True):
        payload = {"type": "online" if online else "offline"}
        self.publish("status", payload)

    def send_telemetry(self, data: dict):
        self.publish("telemetry", data)

    def send_alert(self, alert: dict):
        self.publish("alert", alert)


# ═══════════════════════════════════════
# 主循环
# ═══════════════════════════════════════
def main():
    device_ids, interval, alert_every = parse_args()

    # 校验凭证
    for did in device_ids:
        if did not in DEVICE_CREDENTIALS:
            print(f"⚠ 设备 '{did}' 没有配置凭证！请在 DEVICE_CREDENTIALS 中添加。")
            print(f"   已知设备: {list(DEVICE_CREDENTIALS.keys())}")
            sys.exit(1)

    # 创建模拟器
    simulators: dict[str, DeviceSimulator] = {}
    for did in device_ids:
        if did in DEFAULT_DEVICES:
            simulators[did] = DeviceSimulator(did, DEFAULT_DEVICES[did])
        else:
            simulators[did] = DeviceSimulator(did, {
                "name": did,
                "type": "generic",
                "fields": {
                    "value":        {"base": 50.0, "noise": 10.0, "drift_period": 30},
                    "temperature":  {"base": 25.0, "noise": 3.0, "drift_period": 60},
                    "battery":      {"base": 80.0, "noise": 0.5, "drift_period": 3600},
                },
            })

    print("=" * 60)
    print("  IoT 设备模拟器（独立连接模式）")
    print(f"  目标 Broker: {EMQX_HOST}:{EMQX_PORT}")
    print(f"  上报间隔: {interval}s")
    print(f"  模拟设备: {len(simulators)} 台")
    for did, sim in simulators.items():
        fields_str = ", ".join(sim.fields.keys())
        print(f"    • {did} ({sim.name}) — 字段: {fields_str}")
        print(f"      凭证: {did} / {DEVICE_CREDENTIALS[did]}")
    print("=" * 60)

    # ── 每台设备建立独立 MQTT 连接 ──
    print(f"\n[{datetime.now():%H:%M:%S}] 建立独立 MQTT 连接...")
    clients: dict[str, DeviceMQTTClient] = {}
    for did in device_ids:
        client = DeviceMQTTClient(did, DEVICE_CREDENTIALS[did])
        if client.connect():
            clients[did] = client
        else:
            print(f"  ✗ {did} 连接失败，跳过")
    print()

    if not clients:
        print("没有设备成功连接 EMQX，退出。")
        sys.exit(1)

    # ── 发送上线状态 ──
    print(f"[{datetime.now():%H:%M:%S}] 发送设备上线状态...")
    for did, client in clients.items():
        client.send_status(online=True)
        print(f"  device/{did}/status → online")

    # ── 主循环 ──
    print(f"\n[{datetime.now():%H:%M:%S}] 开始模拟数据上报 (Ctrl+C 停止)\n")

    try:
        while True:
            for did, sim in simulators.items():
                if did not in clients:
                    continue

                client = clients[did]

                # 遥测数据
                data = sim.generate_telemetry()
                client.send_telemetry(data)

                payload_str = json.dumps(data, ensure_ascii=False)
                if len(payload_str) > 80:
                    payload_str = payload_str[:77] + "..."
                print(f"  [{datetime.now():%H:%M:%S}] {did} → telemetry: {payload_str}")

                # 偶尔发告警
                if alert_every > 0 and sim.tick % alert_every == 0:
                    alert = sim.generate_alert()
                    if alert:
                        client.send_alert(alert)
                        print(f"  [{datetime.now():%H:%M:%S}] {did} → alert ⚠ {alert['type']} [{alert['severity']}]")

            # 统计
            total = sum(sum(c.stats.values()) for c in clients.values())
            parts = []
            for did, c in clients.items():
                parts.append(f"{did}: t{c.stats.get('telemetry',0)} a{c.stats.get('alert',0)}")
            print(f"  ── 已发送 {total} 条消息 ({', '.join(parts)}) ──\n")

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n[{datetime.now():%H:%M:%S}] 收到中断信号，发送离线状态...")
        for did, client in clients.items():
            client.send_status(online=False)
            print(f"  device/{did}/status → offline")
            client.disconnect()

        total = sum(sum(c.stats.values()) for c in clients.values())
        print(f"\n总共发送: {total} 条消息")
        print("模拟器已退出。")


if __name__ == "__main__":
    main()
