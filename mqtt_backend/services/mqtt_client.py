"""
MQTT 客户端服务 —— 全局单例，负责：
- 订阅设备遥测/告警/状态/录音主题
- 消息路由分发（gps/telemetry/alert/status/recording/config）
- 慢遥测缓存 + 快遥测合并
- 头盔电量强制 80%
- 指令/配置下发复用全局连接
"""
import json
import logging
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from fastapi import HTTPException

from config import settings
from database import get_conn, get_cursor

logger = logging.getLogger("mqtt_backend")


class MQTTClient:
    """全局 MQTT 客户端：订阅设备数据 + 下发指令复用同一连接。"""

    # 缓存每台设备最新慢刷新字段，供快遥测合并
    # value: (data_dict, timestamp) —— timestamp 用于 TTL 过期清理
    _slow_cache: dict = {}
    _CACHE_TTL = 300  # 缓存过期时间（秒），5 分钟内无遥测上报视为过期

    @staticmethod
    def _clean_stale_cache():
        """清理过期的慢遥测缓存条目"""
        now = time.time()
        stale = [
            did for did, (_, ts) in MQTTClient._slow_cache.items()
            if now - ts > MQTTClient._CACHE_TTL
        ]
        for did in stale:
            del MQTTClient._slow_cache[did]
            logger.info(f"  [cache] 清理过期缓存: {did}")

    def __init__(self):
        self.client = mqtt.Client(
            client_id=f"backend_{id(self):x}",
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(settings.EMQX_USER, settings.EMQX_PASS)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        # 自动重连：初始1秒，最大30秒，指数退避
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    # ── 回调 ──
    @staticmethod
    def _on_connect(client, userdata, flags, rc):
        if rc == 0:
            topics = settings.SUBSCRIBE_TOPICS
            logger.info(f"EMQX 连接成功，订阅 {len(topics)} 个主题")
            for topic, qos in topics:
                client.subscribe(topic, qos=qos)
                logger.info(f"  订阅: {topic} (QoS {qos})")
        else:
            logger.warning(f"EMQX 连接失败，rc={rc}")

    @staticmethod
    def _on_disconnect(client, userdata, rc):
        if rc != 0:
            logger.warning(f"EMQX 断开 (rc={rc})，将自动重连...")

    @staticmethod
    def _on_message(client, userdata, msg):
        """按 Topic 后缀分类路由消息。"""
        try:
            parts = msg.topic.split("/")
            if len(parts) < 3:
                return
            device_id = parts[1]
            subtopic = parts[2]
            if not device_id:
                return

            # 忽略下行 Topic（cmd 由服务器下发，不期望收到回显）
            if subtopic == "cmd":
                return

            # 录音为原始二进制 AMR 数据，不解析 JSON
            if subtopic == "recording":
                MQTTClient._handle_recording(device_id, msg.payload)
                return

            raw_json = msg.payload.decode("utf-8")
            logger.info(f"MQTT ← {device_id}/{subtopic} [{len(msg.payload)}B]: {raw_json[:500]}")

            # ── 注册校验 ──
            if not MQTTClient._device_registered(device_id):
                logger.info(f"设备 {device_id} 未注册，跳过")
                return

            # ── 头盔电量强制 80 ──
            if subtopic in ("gps", "telemetry") and device_id in settings.HELMET_DEVICE_IDS:
                try:
                    data = json.loads(raw_json)
                    if "battery" in data:
                        data["battery"] = 80.0
                    raw_json = json.dumps(data, ensure_ascii=False)
                except json.JSONDecodeError:
                    pass

            # ── 按类型分发 ──
            if subtopic == "status":
                MQTTClient._handle_status(device_id, raw_json)
            elif subtopic == "alert":
                MQTTClient._insert_device_data(device_id, raw_json, "alert")
                MQTTClient._handle_alert(device_id, raw_json)
            elif subtopic == "gps":
                MQTTClient._insert_device_data(device_id, raw_json, "gps")
            elif subtopic == "telemetry":
                MQTTClient._merge_slow_telemetry(device_id, raw_json)
            elif subtopic == "config":
                MQTTClient._handle_config_report(device_id, raw_json)

        except Exception as e:
            raw = msg.payload if isinstance(msg.payload, bytes) else msg.payload.encode()
            tail_hex = raw[-40:].hex(" ") if len(raw) > 40 else raw.hex(" ")
            logger.error(f"MQTT 消息处理失败: {e}  |  payload={len(raw)}B  tail_hex=[{tail_hex}]")

    # ── 内部方法 ──
    @staticmethod
    def _device_registered(device_id: str) -> bool:
        """检查设备是否已注册。"""
        with get_conn() as conn:
            with get_cursor(conn, dict_cursor=False) as cursor:
                cursor.execute(
                    "SELECT 1 FROM device_info WHERE device_id=%s LIMIT 1",
                    (device_id,),
                )
                return cursor.fetchone() is not None

    @staticmethod
    def _insert_device_data(device_id: str, raw_json: str, message_type: str):
        """将遥测/告警数据写入 device_data 表。快遥测自动合并慢字段。"""
        if message_type == "gps" and device_id in MQTTClient._slow_cache:
            slow_data, ts = MQTTClient._slow_cache[device_id]
            if time.time() - ts > MQTTClient._CACHE_TTL:
                del MQTTClient._slow_cache[device_id]
                logger.info(f"  [cache] {device_id} 缓存已过期，跳过合并")
            else:
                try:
                    data = json.loads(raw_json)
                    data.update(slow_data)
                    raw_json = json.dumps(data, ensure_ascii=False)
                except json.JSONDecodeError:
                    pass
        with get_conn() as conn:
            try:
                with get_cursor(conn, dict_cursor=False) as cursor:
                    cursor.execute(
                        "INSERT IGNORE INTO device_data "
                        "(device_id, message_type, raw_json, upload_time) "
                        "VALUES (%s, %s, %s, %s)",
                        (device_id, message_type, raw_json, datetime.now()),
                    )
                    if cursor.rowcount == 0:
                        logger.warning(
                            f"  [{message_type}] {device_id} INSERT IGNORE 跳过！"
                            f" 可能是非法 JSON (长度={len(raw_json)}): {raw_json[:200]}"
                        )
                    else:
                        logger.info(f"  [{message_type}] {device_id} 已入库")
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def _merge_slow_telemetry(device_id: str, raw_json: str):
        """将慢刷新字段合并到最近一条遥测记录中，并更新缓存。"""
        try:
            slow_data = json.loads(raw_json)
        except json.JSONDecodeError:
            logger.warning(f"  telemetry JSON 解析失败: {raw_json[:80]}")
            return
        MQTTClient._slow_cache[device_id] = (slow_data, time.time())
        MQTTClient._clean_stale_cache()
        with get_conn() as conn:
            try:
                with get_cursor(conn, dict_cursor=False) as cursor:
                    cursor.execute(
                        "SELECT id, raw_json FROM device_data "
                        "WHERE device_id=%s AND message_type='gps' "
                        "ORDER BY upload_time DESC LIMIT 1",
                        (device_id,),
                    )
                    row = cursor.fetchone()
                    if row:
                        existing = row[1]
                        if isinstance(existing, str):
                            existing = json.loads(existing)
                        existing.update(slow_data)
                        cursor.execute(
                            "UPDATE device_data SET raw_json=%s WHERE id=%s",
                            (json.dumps(existing, ensure_ascii=False), row[0]),
                        )
                        conn.commit()
                        logger.info(f"  [telemetry] 已合并到遥测 #{row[0]}")
                    else:
                        cursor.execute(
                            "INSERT IGNORE INTO device_data "
                            "(device_id, message_type, raw_json, upload_time) "
                            "VALUES (%s, 'telemetry', %s, %s)",
                            (device_id, raw_json, datetime.now()),
                        )
                        conn.commit()
                        logger.info(f"  [telemetry] {device_id} 暂无遥测，单独入库")
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def _handle_status(device_id: str, raw_json: str):
        """处理设备在线状态消息，更新 device_info 表。"""
        try:
            data = json.loads(raw_json)
            status_type = data.get("type", "unknown")
        except json.JSONDecodeError:
            logger.warning(f"  status 消息 JSON 解析失败: {raw_json[:80]}")
            return

        now = datetime.now()
        with get_conn() as conn:
            try:
                with get_cursor(conn, dict_cursor=False) as cursor:
                    if status_type == "online":
                        cursor.execute(
                            "UPDATE device_info SET is_online=1, last_online_time=%s "
                            "WHERE device_id=%s",
                            (now, device_id),
                        )
                        logger.info(f"  [status] {device_id} 上线")
                    elif status_type == "offline":
                        cursor.execute(
                            "UPDATE device_info SET is_online=0, last_offline_time=%s "
                            "WHERE device_id=%s",
                            (now, device_id),
                        )
                        logger.info(f"  [status] {device_id} 离线")
                    else:
                        logger.info(f"  [status] {device_id} 未知状态: {status_type}")
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def _handle_alert(device_id: str, raw_json: str):
        """告警额外处理——日志报警 + 预留推送/短信扩展点。"""
        try:
            data = json.loads(raw_json)
            alert_type = data.get("type", "unknown")
            severity = data.get("severity", "unknown")
            logger.warning(
                f"  ⚠ ALERT [{severity}] {device_id} → {alert_type}"
            )
        except json.JSONDecodeError:
            logger.warning(f"  alert 消息 JSON 解析失败: {raw_json[:80]}")

    @staticmethod
    def _handle_config_report(device_id: str, raw_json: str):
        """处理设备上报的当前配置值，存入 current_config 供前端表单初始化。"""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            logger.warning(f"  [config] JSON 解析失败: {raw_json[:80]}")
            return
        if not isinstance(data, dict):
            return
        has_nested = any(isinstance(v, dict) for v in data.values())
        if has_nested:
            return
        with get_conn() as conn:
            try:
                with get_cursor(conn, dict_cursor=False) as cursor:
                    cursor.execute(
                        "UPDATE device_info SET current_config=%s WHERE device_id=%s",
                        (json.dumps(data, ensure_ascii=False), device_id),
                    )
                conn.commit()
                logger.info(f"  [config] {device_id} 上报当前配置: {raw_json[:200]}")
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def _handle_recording(device_id: str, payload: bytes):
        """处理设备录音（原始 AMR 二进制）。"""
        if not payload:
            logger.warning(f"  [recording] {device_id} 空录音，跳过")
            return
        with get_conn() as conn:
            try:
                with get_cursor(conn, dict_cursor=False) as cursor:
                    cursor.execute(
                        "INSERT INTO device_recording "
                        "(device_id, format, data, upload_time) "
                        "VALUES (%s, 'amr', %s, %s)",
                        (device_id, payload, datetime.now()),
                    )
                    rec_id = cursor.lastrowid
                    conn.commit()
                    logger.info(f"  [recording] {device_id} 录音已入库, id={rec_id}, size={len(payload)}B")

                    # 将 recording_db_id 注入最近一条告警的 raw_json（30 秒时间窗口）
                    cursor.execute(
                        "SELECT id, raw_json FROM device_data "
                        "WHERE device_id=%s AND message_type='alert' "
                        "AND upload_time >= DATE_SUB(NOW(), INTERVAL 30 SECOND) "
                        "ORDER BY upload_time DESC LIMIT 1",
                        (device_id,),
                    )
                    row = cursor.fetchone()
                    if row:
                        try:
                            raw = row[1]
                            if isinstance(raw, str):
                                raw = json.loads(raw)
                            raw["recording_db_id"] = rec_id
                            cursor.execute(
                                "UPDATE device_data SET raw_json=%s WHERE id=%s",
                                (json.dumps(raw, ensure_ascii=False), row[0]),
                            )
                            conn.commit()
                            logger.info(f"  [recording] 已将 recording_db_id={rec_id} 注入告警 #{row[0]}")
                        except Exception:
                            pass
                    else:
                        logger.info(f"  [recording] 30 秒内无告警，跳过关联")
            except Exception:
                conn.rollback()
                raise

    # ── 生命周期 ──
    def start(self):
        def _run():
            self.client.connect(settings.EMQX_HOST, settings.EMQX_PORT, 60)
            self.client.loop_forever()

        t = threading.Thread(target=_run, daemon=True, name="mqtt-listener")
        t.start()
        logger.info("MQTT 客户端已启动（后台线程）")

    def _publish(self, device_id: str, subtopic: str, payload: str):
        """下发消息到设备（复用全局连接），payload 须为合法 JSON。"""
        try:
            json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail=f"格式错误：必须是合法 JSON")
        topic = f"device/{device_id}/{subtopic}"
        result = self.client.publish(topic, payload, qos=1)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"MQTT → {topic}: {payload}")
        else:
            logger.error(f"MQTT 下发失败: rc={result.rc}")
            raise HTTPException(status_code=500, detail=f"{subtopic} 下发失败")
        return result

    def publish_cmd(self, device_id: str, command: str):
        """下发指令到设备。"""
        return self._publish(device_id, "cmd", command)

    def publish_config(self, device_id: str, config: str):
        """下发配置到设备。"""
        return self._publish(device_id, "config", config)
