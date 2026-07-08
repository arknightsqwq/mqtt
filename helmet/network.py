import time
import json
from collections import OrderedDict
from umqtt.robust import MQTTClient
from config import *

class NetworkManager:
    def __init__(self):
        self.client = None
        self._connected = False
        self._last_reconnect_ms = 0
        self._reconnect_interval = 5000  # 5s between reconnect attempts
        self._callback = None
        self._config_sub_done = False

    def set_callback(self, cb):
        self._callback = cb

    def _create_client(self):
        return MQTTClient(
            client_id=MQTT_CLIENT_ID,
            server=MQTT_BROKER,
            port=MQTT_PORT,
            user=MQTT_USER,
            password=MQTT_PASS,
            keepalive=KEEPALIVE_S,
        )

    def connect(self):
        print("[NET] Initializing 4G network...")
        import quectel
        nw = quectel.Network()
        nw.init()
        if not nw.query_usim():
            print("[NET] SIM card not detected!")
            return False
        try:
            nw.attach()
        except Exception as e:
            print("[NET] attach warning: {}".format(e))
        print("[NET] 4G network ready")

        print("[NET] Connecting MQTT...")
        self.client = self._create_client()
        if self._callback:
            self.client.set_callback(self._callback)
        try:
            self.client.connect()
            self._connected = True
            print("[NET] MQTT connected")
            self._subscribe_config()
            self._publish_online()
            return True
        except Exception as e:
            print("[NET] MQTT connect failed: {}".format(e))
            return False

    def disconnect(self):
        self._publish_offline()
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
            self.client = None
        self._connected = False

    def reconnect(self):
        now_ms = time.ticks_ms()
        if time.ticks_diff(now_ms, self._last_reconnect_ms) < self._reconnect_interval:
            return False
        self._last_reconnect_ms = now_ms
        # Explicitly close old client to free socket
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
            self.client = None
        try:
            self.client = self._create_client()
            if self._callback:
                self.client.set_callback(self._callback)
            self.client.connect()
            self._connected = True
            self._config_sub_done = False
            print("[NET] MQTT reconnected")
            self._subscribe_config()
            self._publish_online()
            return True
        except Exception as e:
            print("[NET] MQTT reconnect failed: {}".format(e))
            self._connected = False
            return False

    def _subscribe_config(self):
        if self._config_sub_done:
            return
        try:
            import remote_config
            remote_config.subscribe(self.client)
            self._config_sub_done = True
        except Exception as e:
            print("[NET] Config sub failed: {}".format(e))

    def is_connected(self):
        return self._connected

    def _try_publish(self, topic, payload, qos=0):
        if self._connected:
            try:
                self.client.publish(topic, payload, qos=qos)
                return True
            except Exception:
                self._connected = False
        self.reconnect()
        if self._connected:
            try:
                self.client.publish(topic, payload, qos=qos)
                return True
            except Exception:
                self._connected = False
        return False

    def check_msg(self):
        if self._connected:
            try:
                self.client.check_msg()
            except Exception:
                self._connected = False
        if not self._connected:
            self.reconnect()

    # ── 上行：在线状态 (device/{id}/status) ──

    def _publish_online(self):
        self._try_publish(TOPIC_STATUS, json.dumps({"type": "online"}), qos=QOS_STATUS)
        print("[STATUS] online")

    def _publish_offline(self):
        self._try_publish(TOPIC_STATUS, json.dumps({"type": "offline"}), qos=QOS_STATUS)
        print("[STATUS] offline")

    # ── 上行：GPS 定位 (device/{id}/gps) 秒级刷新，仅 GNSS 原始字段 ──

    def publish_gps(self, gps):
        if not gps:
            return False
        payload = OrderedDict()
        for k, v in gps.items():
            if k != "_from":
                payload["gps_" + k] = v
        return self._try_publish(TOPIC_GPS, json.dumps(payload), qos=QOS_TELEMETRY)

    # ── 上行：遥测 (device/{id}/telemetry) 仅传感器字段 ──

    def publish_telemetry(self, data):
        payload = OrderedDict()
        if data.get("temp") is not None:
            payload["temperature"] = round(data["temp"], 1)
        if data.get("humi") is not None:
            payload["humidity"] = round(data["humi"], 1)
        if data.get("bat") is not None:
            payload["battery"] = data["bat"]
        if data.get("lux") is not None:
            payload["lux"] = int(data["lux"])
        if data.get("mag") is not None:
            payload["mag"] = round(data["mag"], 2)
        if data.get("bpm", 0) > 0:
            payload["bpm"] = data["bpm"]
            payload["spo2"] = data["spo2"]
        return self._try_publish(TOPIC_TELEMETRY, json.dumps(payload), qos=QOS_TELEMETRY)

    # ── 上行：告警 (device/{id}/alert) ──

    def publish_alert(self, alert_type, severity, message, current_value=None, threshold=None, recording_id=None):
        payload = OrderedDict()
        payload["type"] = alert_type
        payload["severity"] = severity
        payload["message"] = message
        if current_value is not None:
            payload["current_value"] = round(current_value, 1)
        if threshold is not None:
            payload["threshold"] = round(threshold, 1)
        if recording_id:
            payload["recording_id"] = recording_id
        return self._try_publish(TOPIC_ALERT, json.dumps(payload), qos=QOS_ALERT)

    # ── 上行：录音 (device/{id}/recording) ──

    def publish_recording(self, filepath):
        try:
            from quectel import File
            filename = filepath.split(":")[-1].lstrip("/")
            f = File.open(filepath, "r")
            data = f.read()
            f.close()
            print("[UPLOAD] {} ({} bytes)".format(filename, len(data)))
        except Exception as e:
            print("[UPLOAD] Read failed: {}".format(e))
            return False

        if self._connected:
            try:
                self.client.publish(TOPIC_RECORDING, data, qos=QOS_TELEMETRY)
                print("[UPLOAD] Sent")
                return True
            except Exception:
                self._connected = False
        self.reconnect()
        if self._connected:
            try:
                self.client.publish(TOPIC_RECORDING, data, qos=QOS_TELEMETRY)
                print("[UPLOAD] Sent (reconnected)")
                return True
            except Exception:
                self._connected = False
        print("[UPLOAD] Failed: MQTT not connected")
        return False
