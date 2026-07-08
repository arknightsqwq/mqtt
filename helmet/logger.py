import time
from config import *

class Logger:
    def __init__(self):
        self._ready = False
        self._ride_path = ""
        self._alert_path = ""
        self._ride_fh = None
        self._alert_fh = None
        self._last_log_time = 0

    def init(self):
        try:
            from quectel import File
            File.mkdir(LOG_DIR)
            date_str = str(int(time.time()))
            self._ride_path = LOG_DIR + "ride_" + date_str + ".csv"
            self._alert_path = LOG_DIR + "alert_" + date_str + ".csv"
            # 写表头, 保持文件打开
            self._ride_fh = File.open(self._ride_path, "w")
            self._ride_fh.write("time,temp,humi,ax,ay,az,mag,lux,bat,speed,dist_km,alt\n")
            self._alert_fh = File.open(self._alert_path, "w")
            self._alert_fh.write("time,type,level,lat,lng,impact_g\n")
            self._ready = True
            print("[LOG] TF card logging ready")
            return True
        except Exception as e:
            print(f"[LOG] TF card not available: {e}")
            return False

    def _append_line(self, fh, line):
        """直接写入 (句柄保持打开, 位置始终在末尾, 无需 seek)"""
        try:
            fh.write(line)
        except:
            pass

    def log_ride(self, data, stats, ts):
        if not self._ready or not self._ride_fh:
            return
        if ts - self._last_log_time < LOG_INTERVAL_S:
            return
        self._last_log_time = ts
        try:
            t = data.get("temp", "")
            h = data.get("humi", "")
            ax = data.get("ax", 0)
            ay = data.get("ay", 0)
            az = data.get("az", 0)
            mag = data.get("mag", 0)
            lux = int(data.get("lux", 0))
            bat = data.get("bat", 0)
            line = f"{ts},{t},{h},{ax:.2f},{ay:.2f},{az:.2f},{mag:.2f},{lux},{bat},{stats.speed:.1f},{stats.distance_km:.2f},{stats.altitude}\n"
            self._append_line(self._ride_fh, line)
        except:
            pass

    def log_alert(self, alert_type, level, gps, impact_g, ts):
        if not self._ready or not self._alert_fh:
            return
        try:
            lat = gps.get("latitude", 0) if gps else 0
            lng = gps.get("longitude", 0) if gps else 0
            line = f"{ts},{alert_type},{level},{lat},{lng},{impact_g:.2f}\n"
            self._append_line(self._alert_fh, line)
        except:
            pass

    def deinit(self):
        try:
            if self._ride_fh:
                self._ride_fh.close()
            if self._alert_fh:
                self._alert_fh.close()
        except:
            pass
        self._ride_fh = None
        self._alert_fh = None
        self._ready = False
