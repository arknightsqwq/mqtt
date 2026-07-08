# -*- coding: utf-8 -*-
"""沿路段生成 GPS 轨迹，带随机摇摆"""
import json, math, random, sys
from datetime import datetime, timedelta
import pymysql

DB_CONFIG = {"host": "localhost", "port": 3306, "user": "root", "password": "mysql", "database": "mqtt_device_db", "charset": "utf8mb4"}

# GCJ-02 → WGS-84
PI, A, EE = math.pi, 6378245.0, 0.00669342162296594323
def _out(lat, lng): return lng < 72.004 or lng > 137.8347 or lat < 0.8293 or lat > 55.8271
def _tlat(lng, lat):
    r = -100.0 + 2.0*lng + 3.0*lat + 0.2*lat*lat + 0.1*lng*lat + 0.2*math.sqrt(abs(lng))
    r += (20*math.sin(6*lng*PI) + 20*math.sin(2*lng*PI))*2/3
    r += (20*math.sin(lat*PI) + 40*math.sin(lat/3*PI))*2/3
    r += (160*math.sin(lat/12*PI) + 320*math.sin(lat*PI/30))*2/3
    return r
def _tlng(lng, lat):
    r = 300.0 + lng + 2.0*lat + 0.1*lng*lng + 0.1*lng*lat + 0.1*math.sqrt(abs(lng))
    r += (20*math.sin(6*lng*PI) + 20*math.sin(2*lng*PI))*2/3
    r += (20*math.sin(lng*PI) + 40*math.sin(lng/3*PI))*2/3
    r += (150*math.sin(lng/12*PI) + 300*math.sin(lng/30*PI))*2/3
    return r
def gcj2wgs(lat, lng):
    if _out(lat, lng): return lat, lng
    dlat = _tlat(lng - 105, lat - 35); dlng = _tlng(lng - 105, lat - 35)
    rlat = lat/180*PI; magic = 1 - EE*math.sin(rlat)**2; sm = math.sqrt(magic)
    dlat = dlat*180/((A*(1-EE))/(magic*sm)*PI); dlng = dlng*180/(A/sm*math.cos(rlat)*PI)
    return lat*2 - (lat+dlat), lng*2 - (lng+dlng)

# 高德拾取的 GCJ-02 航点 (lon, lat)
GCJ_POINTS = [(121.527404, 38.885324), (121.528640, 38.885369)]
# 转 WGS-84
WGS = [gcj2wgs(lat, lon) for lon, lat in GCJ_POINTS]
print("GCJ -> WGS:")
for (lon_g, lat_g), (lat_w, lon_w) in zip(GCJ_POINTS, WGS):
    print(f"  {lat_g:.6f},{lon_g:.6f} -> {lat_w:.6f},{lon_w:.6f}")

METERS_DEG_LAT = 111320.0
METERS_DEG_LON = 111320.0 * math.cos(math.radians(WGS[0][0]))

def wobble(progress):
    """多频叠加左右摇摆（米）"""
    big = 2.0 * math.sin(progress * math.pi * 2.3 + 0.7)
    med = 1.0 * math.sin(progress * math.pi * 5.1 + 1.4)
    tiny = 0.35 * math.sin(progress * math.pi * 11 + 2.8)
    noise = random.gauss(0, 0.25)
    return big + med + tiny + noise

def main():
    p1, p2 = WGS
    dlat_m = (p2[0]-p1[0]) * METERS_DEG_LAT
    dlon_m = (p2[1]-p1[1]) * METERS_DEG_LON
    total_m = math.sqrt(dlat_m**2 + dlon_m**2)
    uy, ux = dlat_m/total_m, dlon_m/total_m  # 前进方向单位向量
    py, px = -ux, uy  # 垂直方向

    speed_ms = 1.4; interval_s = 3
    step_m = speed_ms * interval_s
    n = max(10, int(total_m / step_m))

    start = datetime(2026, 7, 7, 14, 0, 0)
    step_td = timedelta(seconds=interval_s)

    records = []
    for i in range(n):
        prog = i / (n-1) if n > 1 else 0
        fwd = prog * total_m
        off = wobble(prog)
        lat = p1[0] + (fwd*uy + off*py) / METERS_DEG_LAT
        lon = p1[1] + (fwd*ux + off*px) / METERS_DEG_LON

        # 航向
        if i < n-1:
            np = (i+1)/(n-1); nf = np*total_m; no = wobble(np)
            nlat = p1[0] + (nf*uy + no*py)/METERS_DEG_LAT
            nlon = p1[1] + (nf*ux + no*px)/METERS_DEG_LON
            cog = (math.degrees(math.atan2((nlon-lon)*METERS_DEG_LON, (nlat-lat)*METERS_DEG_LAT)) + 360) % 360
        else:
            cog = (math.degrees(math.atan2(ux, uy)) + 360) % 360

        spd = speed_ms*3.6 + random.gauss(0, 0.3)
        ts = start + step_td * i

        data = {
            "gps_latitude": round(lat, 8), "gps_longitude": round(lon, 8),
            "gps_altitude": round(48+random.gauss(0,1.5), 1),
            "gps_speed_kmh": round(max(0.5, spd), 1),
            "gps_speed_knot": round(max(0.5, spd)*0.53996, 1),
            "gps_cog": round(cog, 1),
            "gps_hdop": round(random.uniform(0.8,2.0), 1),
            "gps_satellites": random.randint(14,24),
            "gps_fix_mode": "3D",
            "gps_utc_time": ts.strftime("%H%M%S.000"),
            "gps_date": ts.strftime("%m%d%y"),
            "bpm": round(max(70,min(130,random.gauss(95,8))),1),
            "spo2": round(max(93,min(100,random.gauss(97.5,0.8))),1),
            "temperature": round(random.gauss(24,1.5),1),
            "humidity": round(max(30,min(95,random.gauss(55,5))),1),
            "pressure": round(random.gauss(1008,1.5),2),
            "lux": round(abs(random.gauss(350,200)),1),
            "mag": round(random.gauss(0.55,0.08),2),
            "battery": 80.0,
        }
        records.append((ts, json.dumps(data, ensure_ascii=False)))

    print(f"Distance: {total_m:.0f}m, Records: {n}, ~{n*interval_s/60:.1f}min")

    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM device_data WHERE device_id='helmet' AND message_type='gps'")
            d = cur.rowcount
            for ts, raw in records:
                cur.execute("INSERT INTO device_data (device_id,message_type,raw_json,upload_time) VALUES (%s,%s,%s,%s)", ("helmet","gps",raw,ts))
        conn.commit()
    except Exception as e:
        conn.rollback(); print(f"ERROR: {e}"); sys.exit(1)
    finally:
        conn.close()

    print(f"[OK] Deleted {d}, inserted {len(records)}")
    for i in range(0, len(records), max(1, len(records)//4)):
        ts, raw = records[i]; o = json.loads(raw)
        print(f"  [{ts:%H:%M:%S}] lat={o['gps_latitude']:.6f} lon={o['gps_longitude']:.6f} cog={o['gps_cog']:.0f}deg bpm={o['bpm']}")

if __name__ == "__main__":
    main()
