import machine
import time
from ahtx0 import AHT20
from lis2dh12 import LIS2DH12
from max30102 import MAX30102, HeartRateMonitor
from quectel import GNSS, LBS
from config import *


class Sensors:
    def __init__(self):
        self.i2c = machine.I2C(1, freq=400000)
        self.aht20 = AHT20(self.i2c)
        self.lis2dh = LIS2DH12(self.i2c)
        self.ldr = machine.ADC(machine.Pin(PIN_LIGHT_ADC))
        self.bat_adc = machine.ADC(machine.Pin(PIN_BAT_ADC))
        self.dist_adc = machine.ADC(machine.Pin(PIN_DIST_ADC))
        self._gnss = None
        self._gnss_started = False
        self._lbs = None
        self._hr_sensor = None
        self._hr_monitor = None
        self._hr_result = {"bpm": 0, "spo2": 0, "red": 0, "ir": 0}
        self._hr_thread_running = False
        self._gps_cache = None
        self._gps_cache_time = 0
        self._last_known_gps = None      # 最后有效位置，碰撞时兜底使用
        self._lbs_cache_time = 0
        self._sensor_cache = {}
        self._sensor_cache_time = 0

    # ── AHT20 ──
    def read_temp_humi(self):
        try:
            return self.aht20.temperature, self.aht20.relative_humidity
        except Exception:
            return None, None

    # ── LIS2DH12 ──
    def read_accel(self):
        try:
            x, y, z = self.lis2dh.acceleration
            mag = (x**2 + y**2 + z**2) ** 0.5 / 9.8
            return x / 9.8, y / 9.8, z / 9.8, mag
        except Exception:
            return 0, 0, 0, 1.0

    # ── Light sensor ──
    def read_light(self):
        raw = self.ldr.read_u16() >> 4
        lux = (4095 - raw) / 4095.0 * 1000
        return lux

    # ── Distance sensor (ADC, 0-3.3V → 0-3m) ──
    def read_distance(self):
        raw = self.dist_adc.read_u16() >> 4
        volt = raw / 4095.0 * 3.3
        dist_m = volt / 3.3 * 3.0  # linear: 0-3.3V → 0-3m
        return dist_m

    # ── Battery ──
    def read_battery(self):
        raw = self.bat_adc.read_u16() >> 4
        volt = (raw * 3.3) / 4095.0
        if volt < BAT_VOLT_MIN * 0.85:
            return 100
        pct = self._volt_to_pct(volt)
        return max(0, min(100, int(pct)))

    def _volt_to_pct(self, volt):
        curve = BAT_CURVE
        if volt >= curve[0][0]:
            return curve[0][1]
        if volt <= curve[-1][0]:
            return curve[-1][1]
        for i in range(len(curve) - 1):
            v_high, p_high = curve[i]
            v_low, p_low = curve[i + 1]
            if v_low <= volt <= v_high:
                frac = (volt - v_low) / (v_high - v_low) if v_high != v_low else 0
                return p_low + frac * (p_high - p_low)
        return 0

    # ── MAX30102 心率/血氧 (独立线程) ──

    def start_hr(self, power_level=0x1F, sample_rate=100):
        """初始化传感器并启动独立采集线程"""
        self._hr_power_level = power_level
        self._hr_sample_rate = sample_rate
        self._hr_result = {"bpm": 0, "spo2": 0, "red": 0, "ir": 0}
        self._hr_thread_running = False
        self._hr_i2c_lock = None  # 备用

        # 先尝试初始化
        if not self._hr_init_sensor():
            return False

        # 启动独立线程
        import _thread
        _thread.stack_size(8192)  # 加大线程栈 (默认可能只有 4K)
        self._hr_thread_running = True
        self._hr_ts = 0
        try:
            _thread.start_new_thread(self._hr_loop, ())
            print("[SENSORS] HR thread started")
            return True
        except Exception as e:
            print(f"[SENSORS] HR thread failed: {e}")
            self._hr_thread_running = False
            return False

    def _hr_init_sensor(self):
        """初始化/重新初始化 MAX30102"""
        try:
            # 独立 I2C 对象，避免与主线程的 AHT20/LIS2DH12 冲突
            hr_i2c = machine.I2C(1, freq=400000)
            self._hr_sensor = MAX30102(hr_i2c)
            self._hr_sensor.begin()
            self._hr_sensor.setup(
                power_level=self._hr_power_level,
                sample_rate=self._hr_sample_rate,
                led_mode=2,
            )
            self._hr_monitor = HeartRateMonitor()
            self._hr_ts = 0
            return True
        except Exception as e:
            print(f"[SENSORS] HR init failed: {e}")
            self._hr_sensor = None
            self._hr_monitor = None
            return False

    def _hr_loop(self):
        """独立线程：连续采集心率数据，不受主循环 LBS 延迟影响"""
        ts = time.ticks_ms()
        while self._hr_thread_running:
            if self._hr_sensor is None:
                self._hr_init_sensor()
                time.sleep_ms(500)
                continue

            try:
                samples = self._hr_sensor.read_fifo()
            except OSError:
                # I2C 暂时出错，跳过本次，保留算法状态
                time.sleep_ms(50)
                continue

            if samples:
                if self._hr_ts == 0:
                    self._hr_ts = time.ticks_ms()
                last_red, last_ir = 0, 0
                for red, ir in samples:
                    if ir > 10000:
                        self._hr_monitor.process(red, ir, self._hr_ts)
                    self._hr_ts += 40
                    last_red, last_ir = red, ir
                # 存结果（原子赋值，不需要锁）
                self._hr_result["bpm"] = self._hr_monitor.bpm
                self._hr_result["spo2"] = self._hr_monitor.spo2
                self._hr_result["red"] = last_red
                self._hr_result["ir"] = last_ir

            # 50ms 采集间隔，与主循环无关
            time.sleep_ms(50)

    def stop_hr(self):
        self._hr_thread_running = False
        time.sleep_ms(100)
        if self._hr_sensor is not None:
            try:
                self._hr_sensor.shutdown()
            except Exception:
                pass
        self._hr_sensor = None
        self._hr_monitor = None

    def read_hr(self):
        """返回缓存的最新心率结果，不阻塞"""
        r = self._hr_result
        return r["bpm"], r["spo2"]

    def read_hr_temp(self):
        if self._hr_sensor is None:
            return None
        try:
            return self._hr_sensor.read_temp()
        except Exception:
            return None

    # ── GNSS + LBS fallback ──
    def start_gnss(self):
        if not self._gnss_started:
            self._gnss = GNSS()
            if self._gnss.start():
                self._gnss_started = True
                return True
            return False
        return True

    def read_gps(self):
        now_ms = time.ticks_ms()
        if self._gps_cache_time > 0 and time.ticks_diff(now_ms, self._gps_cache_time) < 30000:
            return self._gps_cache

        print("[GPS] cache miss, querying...")
        if self._gnss_started:
            try:
                loc = self._gnss.get_location()
                if loc:
                    self._gps_cache = loc
                    self._gps_cache_time = now_ms
                    self._last_known_gps = loc
                    self._lbs_cache_time = now_ms  # reset cooldown when GNSS works
                    print("[GPS] cached (success)")
                    return loc
            except Exception:
                print("[GPS] get_location failed, restarting GNSS...")
                try:
                    self._gnss.stop()
                except:
                    pass
                time.sleep_ms(500)
                try:
                    self._gnss.start()
                except:
                    self._gnss_started = False
                time.sleep_ms(200)

        # LBS fallback: cell tower positioning, ~8s, every 5min
        if time.ticks_diff(now_ms, self._lbs_cache_time) >= 300000:
            try:
                if not self._lbs:
                    self._lbs = LBS()
                print("[LBS] querying...")
                loc = self._lbs.get_location(8000)
                if loc:
                    loc["_from"] = "lbs"
                    self._gps_cache = loc
                    self._gps_cache_time = now_ms
                    self._last_known_gps = loc
                    print("[LBS] cached (success)")
                    self._lbs_cache_time = now_ms
                    return loc
            except Exception as e:
                print("[LBS] failed: {}".format(e))
            self._lbs_cache_time = now_ms

        self._gps_cache = None
        self._gps_cache_time = now_ms

        # Fallback: last known position if available
        if self._last_known_gps:
            print("[GPS] using last known position")
            return self._last_known_gps

        return None

    def read_all(self):
        now_ms = time.ticks_ms()
        # Slow sensors: cache 30s. AHT20 takes 500ms per read, don't call every time!
        cache_age = time.ticks_diff(now_ms, self._sensor_cache_time) if self._sensor_cache_time else 99999
        if cache_age >= 30000:
            t, h = self.read_temp_humi()
            self._sensor_cache = {
                "temp": t, "humi": h,
                "lux": self.read_light(),
                "bat": self.read_battery(),
            }
            self._sensor_cache_time = now_ms
            print("[SENSOR] cache refreshed")

        ax, ay, az, mag = self.read_accel()
        bpm, spo2 = self.read_hr()
        r = self._hr_result
        return {
            "temp": self._sensor_cache["temp"],
            "humi": self._sensor_cache["humi"],
            "ax": ax, "ay": ay, "az": az, "mag": mag,
            "lux": self._sensor_cache["lux"],
            "bat": self._sensor_cache["bat"],
            "bpm": bpm, "spo2": spo2,
            "hr_red": r["red"], "hr_ir": r["ir"],
        }
