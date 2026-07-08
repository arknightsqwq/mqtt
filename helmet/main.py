import time
import config
from config import *
from sensors import Sensors
from collision import CollisionDetector
from network import NetworkManager
from sms import send_sos_sms
from display import DisplayManager
from alarm import AlarmManager
from stats import RideStats
from logger import Logger
from ble import BLEManager
import remote_config

# Buzzer hardware test on boot
def _buzzer_test():
    try:
        import machine
        buzzer = machine.Pin(PIN_BUZZER, machine.Pin.OUT)
        buzzer.value(1)
        time.sleep_ms(500)
        buzzer.value(0)
        print("[OK] Buzzer test passed")
    except Exception as e:
        print("[WARN] Buzzer test failed: {}".format(e))


def _ensure_sd_dirs():
    """预创建 SD 卡目录 (仅当不存在时创建)"""
    try:
        from quectel import File
        File.listdir("SD:helmet/*")
    except:
        try:
            File.mkdir("SD:helmet/")
        except:
            pass


# Global state
_sos_handled = False
_last_dist_warn_s = 0  # ticks_ms, for distance warning cooldown
_last_spd_warn_s = 0  # ticks_ms, for speed warning cooldown
_last_status_time = 0
_last_log_time = 0
_last_bat_warn_ms = 0
_last_hr_time = 0

# Power saving
_power_save = False
_idle_start_time = 0

def main():
    global _sos_handled, _last_status_time, _last_log_time, _last_bat_warn_ms, _last_hr_time
    global _power_save, _idle_start_time

    print("=" * 50)
    print("  Smart Cycling Helmet System V2")
    print("=" * 50)

    print("\n[INIT] Sensors...")
    sensors = Sensors()

    print("[INIT] Heart Rate...")
    sensors.start_hr()

    print("[INIT] Collision detector...")
    detector = CollisionDetector()

    print("[INIT] Display...")
    display = DisplayManager()
    display.init_lcd()
    display.init_leds()

    print("[INIT] Alarm...")
    alarm = AlarmManager()
    alarm.init()

    print("[INIT] GNSS...")
    sensors.start_gnss()

    print("[INIT] Network...")
    net = NetworkManager()
    net_ok = net.connect()

    print("[INIT] BLE...")
    # BLE disabled — EC200U hardware bug + memory pressure
    ble = None

    print("[INIT] TF Card...")
    _ensure_sd_dirs()
    logger = Logger()
    logger.init()

    print("[INIT] Ride Stats...")
    stats = RideStats()

    if net_ok:
        remote_config.load()
        remote_config.publish_status()
        net.publish_telemetry({"bat": 100, "temp": 0})

    print("\n" + "=" * 50)
    print("  System Ready! Entering main loop.")
    print("=" * 50 + "\n")
    _buzzer_test()

    _idle_start_time = time.ticks_ms()
    _loop_count = 0
    _heavy_count = 0
    _cached_now_s = 0
    _cached_now_s_time = 0
    _slow_sensor_ms = 0  # last time slow sensors were read
    SLOW_INTERVAL = 25

    # ── Startup self-test: exercise all modules once ──
    print("\n[SELFTEST] Running full sensor read...")
    ax, ay, az, mag = sensors.read_accel()
    data = sensors.read_all()  # full read (AHT20 may be slow, but only on startup)
    data["ax"], data["ay"], data["az"], data["mag"] = ax, ay, az, mag
    _slow_sensor_ms = time.ticks_ms()
    display.auto_light(data.get("lux", 999))
    gps = sensors.read_gps()
    stats.update(gps, int(time.time()))
    display.update_display(data, 0, stats)
    print("[SELFTEST] accel={:.1f}g temp={:.0f}C humi={:.0f}% lux={:.0f} gps={}".format(
        mag, data.get("temp", 0) or 0, data.get("humi", 0) or 0,
        data.get("lux", 0) or 0, "OK" if gps else "N/A"))
    print("[SELFTEST] Done. Entering main loop.\n")

    # Main loop
    while True:
        t0 = time.ticks_ms()

        # ── Fast: accel + collision (every iteration, ~50Hz) ──
        ax, ay, az, mag = sensors.read_accel()
        result = detector.detect(mag, ax, ay, az, t0)

        if result.level > 0:
            try:
                now_s = int(time.time())
                print("[ALERT] Collision level {} ({:.1f}g)".format(
                    result.level, result.impact_g))
                alarm.collision_alarm(result.level)
                gps = sensors.read_gps()
                sev = "high" if result.level >= 3 else "warning"
                thr = config.DIRECT_IMPACT_L1 if result.level <= 1 else (config.DIRECT_IMPACT_L2 if result.level <= 2 else config.DIRECT_IMPACT_L3)
                net.publish_alert("collision", sev,
                    "collision L{}: {:.1f}g".format(result.level, result.impact_g),
                    current_value=result.impact_g, threshold=thr)
                logger.log_alert("collision", result.level, gps, result.impact_g, now_s)
                if result.level >= 3:
                    _handle_severe_crash(alarm, net, sensors, logger, stats, display, data)
            except Exception as e:
                print("[ALERT] Error: {}".format(e))
            continue

        # ── Fast: SOS button (pin read only) ──
        sos_triggered, _ = alarm.check_sos()
        if sos_triggered and not _sos_handled:
            now_s = int(time.time())
            print("[SOS] Manual SOS triggered!")
            display.set_light_mode("emergency")

            # Buzzer + TTS → wait → report → beep → record → call → SMS
            alarm.sos_alarm()

            # Wait 1.5s before proceeding
            time.sleep(1.5)

            # Hang up any incoming call that would block audio/dial
            if alarm.is_call_active():
                print("[SOS] Active call detected, hanging up first...")
                alarm.hangup_all()

            gps = sensors.read_gps()
            lat = gps.get("latitude", 0) if gps else 0
            lng = gps.get("longitude", 0) if gps else 0
            if net_ok:
                net.publish_alert("sos", "high", "manual SOS alarm", current_value=0, threshold=0)
                if gps:
                    net.publish_gps(gps)
            logger.log_alert("sos", 3, gps, 0, now_s)
            # Beep once as recording cue, then record
            alarm.buzzer_alert(1)
            try:
                rec_path = "SD:sos_" + str(time.ticks_ms()) + ".amr"
                if alarm.record_scene(rec_path):
                    net.publish_recording(rec_path)
            except Exception as e:
                print("[SOS] Recording failed: {}".format(e))
            if config.EMERGENCY_NUM and config.EMERGENCY_NUM != "":
                alarm.emergency_call(config.EMERGENCY_NUM)
                send_sos_sms(config.EMERGENCY_NUM, lat, lng, 3)
            display.set_light_mode("auto")
            _sos_handled = True
            alarm.clear_sos()
        if not sos_triggered:
            _sos_handled = False

        # ── Slow tasks (every ~500ms) ──
        _loop_count += 1
        if _loop_count >= SLOW_INTERVAL:
            _loop_count = 0
            _heavy_count += 1
            now_ms = t0

            # Auto light + distance (ADC is fast, read every cycle)
            lux = sensors.read_light()
            dist_m = sensors.read_distance()
            data["dist"] = dist_m

            # Refresh slow sensors every 30s (AHT20 is slow, don't block loop)
            if time.ticks_diff(now_ms, _slow_sensor_ms) >= 30000:
                fresh = sensors.read_all()
                fresh["ax"], fresh["ay"], fresh["az"], fresh["mag"] = ax, ay, az, mag
                data = fresh
                _slow_sensor_ms = now_ms
            else:
                data["ax"], data["ay"], data["az"], data["mag"] = ax, ay, az, mag
            data["lux"] = lux  # always up-to-date for LCD/upload

            if time.ticks_diff(now_ms, _cached_now_s_time) >= 30000:
                _cached_now_s = int(time.time())
                _cached_now_s_time = now_ms
            now_s = _cached_now_s

            # Distance warning + light mode
            if dist_m < config.DIST_WARN_THRESHOLD:
                display.set_light_mode("warning")
                alarm.vibrate_on()
                global _last_dist_warn_s
                if time.ticks_diff(now_ms, _last_dist_warn_s) >= config.DIST_WARN_COOLDOWN_S * 1000:
                    alarm.play_tts("后方车辆距离过近，请注意安全")
                    _last_dist_warn_s = now_ms
            else:
                display.set_light_mode("auto")
                alarm.vibrate_off()
            display.auto_light(lux)

            gps = sensors.read_gps()
            stats.update(gps, now_s)

            # Speed warning
            if stats.speed > config.SPEED_WARN_THRESHOLD:
                global _last_spd_warn_s
                if time.ticks_diff(now_ms, _last_spd_warn_s) >= config.SPEED_WARN_COOLDOWN_S * 1000:
                    alarm.play_tts("速度过快，请减速慢行")
                    _last_spd_warn_s = now_ms

            try:
                _handle_periodic_tasks(net, sensors, data, stats, now_ms, _power_save)
            except Exception:
                pass

            # Heavy tasks every 4th slow cycle (~2s)
            if _heavy_count >= 4:
                _heavy_count = 0
                data["bpm"], data["spo2"] = sensors.read_hr()  # for LCD display
                try:
                    net.check_msg()
                    remote_config.flush_ack()
                except: pass
                if ble: _ble_notify(ble, data, stats)
                logger.log_ride(data, stats, now_s)
                display.update_display(data, 0, stats)

            bat = data.get("bat", 100)
            if bat < BAT_LOW_2:
                _power_save = True
                if time.ticks_diff(now_ms, _last_bat_warn_ms) > 60000:
                    alarm.low_battery_alarm(2)
                    _last_bat_warn_ms = now_ms
            elif bat < BAT_LOW_1:
                if time.ticks_diff(now_ms, _last_bat_warn_ms) > 60000:
                    alarm.low_battery_alarm(1)
                    _last_bat_warn_ms = now_ms

        # Maintain 50Hz
        elapsed = time.ticks_diff(time.ticks_ms(), t0)
        time.sleep_ms(max(1, 20 - elapsed))


def _check_power_save(sensors, display, now_ms):
    global _idle_start_time

    mag = sensors.read_accel()[3]
    if abs(mag - 1.0) < IDLE_ACCEL_THRESHOLD:
        idle_duration = time.ticks_diff(now_ms, _idle_start_time)
        if idle_duration > DEEP_IDLE_TIMEOUT_MS:
            display.lcd_off()
            return True, _idle_start_time
        elif idle_duration > IDLE_TIMEOUT_MS:
            return True, _idle_start_time
    else:
        _idle_start_time = now_ms
        display.lcd_on()

    return False, _idle_start_time


def _handle_periodic_tasks(net, sensors, data, stats, now_ms, power_save):
    global _last_status_time, _last_hr_time

    mqtt_ok = net.is_connected()
    gps_interval = config.GPS_INTERVAL_MS * 2 if power_save else config.GPS_INTERVAL_MS
    tele_interval = IDLE_INTERVAL_MS if power_save else config.UPLOAD_INTERVAL_MS

    # GPS 快发：秒级，传感器+GNSS 全字段
    if mqtt_ok and time.ticks_diff(now_ms, _last_status_time) >= gps_interval:
        gps = sensors.read_gps()
        net.publish_gps(gps)
        _last_status_time = now_ms

    # Telemetry 慢发：分钟级，仅低频字段
    if mqtt_ok and time.ticks_diff(now_ms, _last_hr_time) >= tele_interval:
        net.publish_telemetry(data)
        _last_hr_time = now_ms


def _handle_severe_crash(alarm, net, sensors, logger, stats, display, data):
    now_s = int(time.time())
    print("[CRASH] Buzzer on, {}s cancel wait...".format(SOS_AUTO_TIMEOUT_S))
    display.set_light_mode("emergency")
    alarm.buzzer_on()

    # Hang up any incoming call that would block emergency dial
    if alarm.is_call_active():
        print("[CRASH] Active call detected, hanging up...")
        alarm.hangup_all()

    wait_start = time.time()
    for i in range(SOS_AUTO_TIMEOUT_S):
        if alarm._sos_pin and alarm._sos_pin.value() == 0:
            alarm.buzzer_off()
            alarm.play_tts("已取消自动求助")
            print("[CRASH] Cancelled by user")
            return
        print("  cancel wait {}/{}s".format(i + 1, SOS_AUTO_TIMEOUT_S))
        time.sleep(1)

    alarm.buzzer_off()
    print("[CRASH] No cancel — starting emergency sequence")

    gps = sensors.read_gps()
    lat = gps.get("latitude", 0) if gps else 0
    lng = gps.get("longitude", 0) if gps else 0
    logger.log_alert("auto_sos", 3, gps, data.get("mag", 0), now_s)

    # Publish GPS to MQTT immediately after alarm
    if gps and net.is_connected():
        net.publish_gps(gps)

    # Record BEFORE voice call (voice call seizes audio codec)
    print("[CRASH] Recording scene audio...")
    try:
        rec_path = "SD:crash_" + str(time.ticks_ms()) + ".amr"
        if alarm.record_scene(rec_path):
            net.publish_recording(rec_path)
    except Exception as e:
        print("[CRASH] Recording failed: {}".format(e))

    print("[CRASH] Calling {}...".format(config.EMERGENCY_NUM))
    alarm.play_tts("正在拨打紧急电话")
    if config.EMERGENCY_NUM and config.EMERGENCY_NUM != "":
        alarm.emergency_call(config.EMERGENCY_NUM)
        print("[CRASH] Sending SMS...")
        send_sos_sms(config.EMERGENCY_NUM, lat, lng, 3)

    display.set_light_mode("auto")
    print("[CRASH] Emergency sequence complete, resuming detection")


def _ble_notify(ble, data, stats):
    try:
        import json
        from collections import OrderedDict
        payload = OrderedDict()
        payload["t"] = round(data.get("temp", 0), 1) if data.get("temp") else 0
        payload["h"] = round(data.get("humi", 0), 1) if data.get("humi") else 0
        payload["s"] = round(stats.speed, 1)
        payload["d"] = round(stats.distance_km, 2)
        payload["b"] = data.get("bat", 0)
        ble.notify(json.dumps(payload))
    except:
        pass


if __name__ == "__main__":
    main()
