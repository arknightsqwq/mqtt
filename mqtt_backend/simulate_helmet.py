# -*- coding: utf-8 -*-
"""
持续向 device/helmet/telemetry 发送遥测数据
───────────────────────────────────────────
每 20 秒上报一条，各字段带随机微小波动。
电量只能降不能升。

用法:
  python simulate_helmet.py
  python simulate_helmet.py --interval 10    # 自定义间隔（秒）

依赖: pip install paho-mqtt
"""

import json
import random
import sys
import time
from datetime import datetime

# 强制 UTF-8 输出，解决 Windows GBK 乱码
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import paho.mqtt.client as mqtt

# ═══════════════════════════════════════
# 配置
# ═══════════════════════════════════════
EMQX_HOST = "cn-xy.starryfrp.com"
EMQX_PORT = 1883
DEVICE_ID = "helmet"
DEVICE_PASS = "helmet"
TOPIC = f"device/{DEVICE_ID}/telemetry"

# 初始基准值 + 每次波动范围
# 字段              基准      波动±      单位      说明
FIELDS = {
    "bpm":          (86.0,    4.0,     "bpm",     "心率"),
    "lux":          (15.8,    3.0,     "lux",     "光照度"),
    "mag":          (0.68,    0.03,    "Gauss",   "磁场"),
    "spo2":         (98.0,    0.5,     "%",       "血氧饱和度"),
    "temperature":  (22.4,    0.3,     "°C",      "温度"),
    "humidity":     (67.0,    1.0,     "%RH",     "湿度"),
    "pressure":     (1008.4,  0.6,     "hPa",     "气压"),
}

# 电量：只能降不能升，每小时大约降 0.02%（极慢）
BATTERY_BASE = 80.0
BATTERY_DECAY_PER_TICK = 0.0001  # 每次衰减（20s/次 → 每小时 180 次 → ~0.018%/h）


def parse_args():
    interval = 20
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--interval" and i + 1 < len(args):
            interval = float(args[i + 1])
            i += 2
        else:
            i += 1
    return interval


def main():
    interval = parse_args()

    battery = BATTERY_BASE

    # ── 创建 MQTT 客户端 ──
    client = mqtt.Client(client_id=DEVICE_ID, protocol=mqtt.MQTTv311)
    client.username_pw_set(DEVICE_ID, DEVICE_PASS)
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    connected = False

    def on_connect(client, userdata, flags, rc):
        nonlocal connected
        if rc == 0:
            connected = True
            print(f"[{datetime.now():%H:%M:%S}] ✓ 已连接 EMQX (helmet)")
        else:
            print(f"[{datetime.now():%H:%M:%S}] ✗ 连接失败 rc={rc}")

    client.on_connect = on_connect

    print("=" * 55)
    print("  Helmet 遥测模拟器")
    print(f"  Broker: {EMQX_HOST}:{EMQX_PORT}")
    print(f"  Topic:  {TOPIC}")
    print(f"  间隔:   {interval}s")
    print(f"  电量初始: {BATTERY_BASE}%  (只降不升, ~{BATTERY_DECAY_PER_TICK * 3600 / interval * 100:.2f}%/h)")
    print("=" * 55)

    client.connect(EMQX_HOST, EMQX_PORT, 60)
    client.loop_start()

    # 等待连接
    for _ in range(50):
        if connected:
            break
        time.sleep(0.1)

    if not connected:
        print("连接超时，退出。")
        sys.exit(1)

    tick = 0
    print(f"\n[{datetime.now():%H:%M:%S}] 开始上报 (Ctrl+C 停止)\n")

    try:
        while True:
            tick += 1

            # ── 生成遥测数据 ──
            data = {}
            for field_name, (base, noise, unit, desc) in FIELDS.items():
                value = base + random.gauss(0, noise)
                # 夹紧到合理范围
                if field_name == "spo2":
                    value = min(100.0, max(85.0, value))
                elif field_name == "humidity":
                    value = min(100.0, max(0.0, value))
                elif field_name == "lux":
                    value = max(0.0, value)
                elif field_name == "bpm":
                    value = min(200.0, max(40.0, value))
                elif field_name == "temperature":
                    value = min(50.0, max(-10.0, value))
                elif field_name == "pressure":
                    value = min(1100.0, max(900.0, value))
                data[field_name] = round(value, 2 if field_name != "bpm" and field_name != "spo2" else 1)

            # 电量：只降不升（极小衰减 + 微小抖动）
            battery -= BATTERY_DECAY_PER_TICK
            # 加一点点不可预测性，但只有往下
            battery -= abs(random.gauss(0, 0.002))
            battery = max(0.0, battery)  # 不低于 0
            data["battery"] = round(battery, 2)

            # ── 发布 ──
            payload = json.dumps(data, ensure_ascii=False)
            result = client.publish(TOPIC, payload, qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                parts = ", ".join(f"{k}={v}" for k, v in data.items())
                print(f"[{datetime.now():%H:%M:%S}] ✓ {payload}")
            else:
                print(f"[{datetime.now():%H:%M:%S}] ✗ 发送失败 rc={result.rc}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n[{datetime.now():%H:%M:%S}] 收到中断信号，退出。")
        client.loop_stop()
        client.disconnect()
        print(f"共上报 {tick} 条，电量从 {BATTERY_BASE}% → {battery:.2f}%")


if __name__ == "__main__":
    main()
