"""MQTT remote configuration: receive config via MQTT, apply, persist to SD."""
import json
import config

CONFIG_FILE = "SD:helmet/remote.json"
CONFIG_TOPIC = b"device/" + config.DEVICE_ID.encode() + b"/config"
ACK_TOPIC = b"device/" + config.DEVICE_ID.encode() + b"/config/ack"
STATUS_TOPIC = b"device/" + config.DEVICE_ID.encode() + b"/config"

# Map JSON keys to config module attributes and types
_SCHEMA = {
    "emergency_num":           ("EMERGENCY_NUM", str),
    "speed_warn_threshold":    ("SPEED_WARN_THRESHOLD", float),
    "speed_warn_cooldown_s":   ("SPEED_WARN_COOLDOWN_S", int),
    "dist_warn_threshold":     ("DIST_WARN_THRESHOLD", float),
    "dist_warn_cooldown_s":    ("DIST_WARN_COOLDOWN_S", int),
    "light_threshold_lux":     ("LIGHT_THRESHOLD_LUX", float),
    "direct_impact_l1":        ("DIRECT_IMPACT_L1", float),
    "direct_impact_l2":        ("DIRECT_IMPACT_L2", float),
    "direct_impact_l3":        ("DIRECT_IMPACT_L3", float),
    "ff_impact_l1":            ("FF_IMPACT_L1", float),
    "ff_impact_l2":            ("FF_IMPACT_L2", float),
    "ff_impact_l3":            ("FF_IMPACT_L3", float),
    "upload_interval_ms":      ("UPLOAD_INTERVAL_MS", int),
    "gps_interval_ms":         ("GPS_INTERVAL_MS", int),
}

_client = None  # MQTT client reference for publishing ACK
_pending_ack = None  # deferred ACK data (avoid deadlock in callback)


def load():
    """Load saved config from SD card and apply. Returns True if loaded."""
    try:
        from quectel import File
        f = File.open(CONFIG_FILE, "r")
        data = json.loads(f.read().decode())
        f.close()
        changed = _apply(data)
        if changed:
            print("[CONFIG] Loaded from SD ({} keys)".format(len(data)))
        return True
    except Exception as e:
        print("[CONFIG] No saved config: {}".format(e))
        return False


def save():
    """Save current config values to SD card."""
    try:
        from quectel import File
        data = _dump()
        f = File.open(CONFIG_FILE, "w")
        f.write(json.dumps(data))
        f.close()
        print("[CONFIG] Saved to SD")
    except Exception as e:
        print("[CONFIG] Save failed: {}".format(e))


def subscribe(client):
    """Subscribe to config topic on the given MQTT client."""
    global _client
    _client = client
    client.set_callback(_on_message)
    client.subscribe(CONFIG_TOPIC, qos=1)
    print("[CONFIG] Subscribed to {}".format(CONFIG_TOPIC.decode()))


def _on_message(topic, msg):
    """MQTT callback: handle incoming config message. ACK deferred to avoid deadlock."""
    global _pending_ack
    try:
        topic_str = topic.decode() if isinstance(topic, bytes) else topic
        if topic_str != CONFIG_TOPIC.decode():
            return
        data = json.loads(msg.decode() if isinstance(msg, bytes) else msg)
        print("[CONFIG] Received: {}".format(data))
        changed = _apply(data)
        if changed:
            save()
        _pending_ack = {"ok": True, "msg": "applied", "values": _dump()}
    except Exception as e:
        print("[CONFIG] Error: {}".format(e))
        _pending_ack = {"ok": False, "msg": str(e)}


def publish_status():
    """Publish current config values to broker (e.g. on startup)."""
    global _client
    if not _client:
        return
    try:
        _client.publish(STATUS_TOPIC, json.dumps(_dump()))
        print("[CONFIG] Status published")
    except Exception as e:
        print("[CONFIG] Status failed: {}".format(e))


def flush_ack():
    """Publish pending ACK. Call from main loop outside check_msg()."""
    global _pending_ack, _client
    if _pending_ack and _client:
        try:
            _client.publish(ACK_TOPIC, json.dumps(_pending_ack))
            print("[CONFIG] ACK sent")
        except Exception as e:
            print("[CONFIG] ACK failed: {}".format(e))
        _pending_ack = None


def _apply(data):
    """Apply config dict to config module. Returns list of changed keys."""
    changed = []
    for key, (attr, typ) in _SCHEMA.items():
        if key in data:
            new_val = typ(data[key])
            old_val = getattr(config, attr)
            if new_val != old_val:
                setattr(config, attr, new_val)
                changed.append(key)
                print("[CONFIG] {} = {} (was {})".format(attr, new_val, old_val))
    return changed


def _dump():
    """Return dict of current config values."""
    return {key: getattr(config, attr) for key, (attr, _) in _SCHEMA.items()}


