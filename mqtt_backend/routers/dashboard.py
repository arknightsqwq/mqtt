"""
数据可视化路由
─────────────
- 设备最新数据 / 时序数据 / GPS 轨迹
- 告警列表 / 录音获取
"""
import json
import os
import subprocess
import tempfile

from fastapi import APIRouter, HTTPException, Depends, Response

from database import get_conn, get_cursor, json_to_str, json_to_dict
from auth import get_current_user, verify_device_bind

router = APIRouter(tags=["数据可视化"])


@router.get("/api/device/{device_id}/latest", summary="设备最新数据")
def device_latest(device_id: str, user_id: str = Depends(verify_device_bind)):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                "SELECT di.device_id, di.device_name, di.is_online, "
                "di.last_online_time, di.last_offline_time, di.config_json, di.current_config, "
                "di.field_labels "
                "FROM device_info di WHERE di.device_id=%s",
                (device_id,),
            )
            info = cursor.fetchone()
            if not info:
                raise HTTPException(status_code=404, detail="设备不存在")

            cursor.execute(
                "SELECT raw_json, upload_time FROM device_data "
                "WHERE device_id=%s AND message_type='telemetry' "
                "ORDER BY upload_time DESC LIMIT 1",
                (device_id,),
            )
            telem_row = cursor.fetchone()
            cursor.execute(
                "SELECT raw_json, upload_time FROM device_data "
                "WHERE device_id=%s AND message_type='gps' "
                "ORDER BY upload_time DESC LIMIT 1",
                (device_id,),
            )
            gps_row = cursor.fetchone()

    raw = None
    upload_time = None
    if telem_row or gps_row:
        merged = {}
        if gps_row:
            merged.update(json_to_dict(gps_row["raw_json"]) or {})
        if telem_row:
            merged.update(json_to_dict(telem_row["raw_json"]) or {})
            upload_time = telem_row["upload_time"]
        else:
            upload_time = gps_row["upload_time"]
        raw = json.dumps(merged, ensure_ascii=False)
        upload_time = upload_time.strftime("%Y-%m-%d %H:%M:%S")

    config_raw = json_to_dict(info.get("config_json"))
    current_raw = json_to_dict(info.get("current_config"))
    field_labels = json_to_dict(info.get("field_labels"))

    return {
        "code": 200,
        "data": {
            "device_id": info["device_id"],
            "device_name": info["device_name"],
            "is_online": bool(info["is_online"]),
            "last_online_time": info["last_online_time"],
            "last_offline_time": info["last_offline_time"],
            "latest_raw": raw,
            "latest_time": upload_time,
            "config_json": config_raw,
            "current_config": current_raw,
            "field_labels": field_labels,
        },
    }


@router.get("/api/device/{device_id}/timeseries", summary="设备时序数据")
def device_timeseries(
    device_id: str,
    field: str = "value",
    hours: int = 24,
    limit: int = 200,
    user_id: str = Depends(verify_device_bind),
):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                "SELECT "
                "  JSON_UNQUOTE(JSON_EXTRACT(raw_json, CONCAT('$.', %s))) AS val, "
                "  upload_time "
                "FROM device_data "
                "WHERE device_id=%s AND message_type IN ('gps','telemetry') "
                "  AND upload_time >= DATE_SUB(NOW(), INTERVAL %s HOUR) "
                "  AND JSON_EXTRACT(raw_json, CONCAT('$.', %s)) IS NOT NULL "
                "ORDER BY upload_time ASC "
                "LIMIT %s",
                (field, device_id, hours, field, limit),
            )
            rows = cursor.fetchall()

    points = []
    for r in rows:
        try:
            v = float(r["val"])
        except (ValueError, TypeError):
            v = r["val"]
        points.append({
            "time": r["upload_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "value": v,
        })

    return {"code": 200, "data": {"device_id": device_id, "field": field, "points": points}}


@router.get("/api/device/{device_id}/trajectory", summary="设备GPS轨迹数据")
def device_trajectory(
    device_id: str,
    hours: float = 24,
    limit: int = 2000,
    user_id: str = Depends(verify_device_bind),
):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                "SELECT raw_json, upload_time "
                "FROM device_data "
                "WHERE device_id=%s AND message_type='gps' "
                "  AND upload_time >= DATE_SUB(NOW(), INTERVAL %s HOUR) "
                "ORDER BY upload_time ASC "
                "LIMIT %s",
                (device_id, hours, limit),
            )
            rows = cursor.fetchall()

    points = []
    for r in rows:
        data = json_to_dict(r["raw_json"])
        if not isinstance(data, dict):
            continue

        lat = data.get("gps_latitude") or data.get("latitude") or data.get("lat")
        lng = data.get("gps_longitude") or data.get("longitude") or data.get("lng") or data.get("lon")
        if lat is None or lng is None:
            continue

        speed = data.get("gps_speed_kmh") or data.get("gps_speed_knot") or data.get("gps_speed") or data.get("speed")
        alt = data.get("gps_altitude") or data.get("altitude") or data.get("alt")
        cog = data.get("gps_cog") or data.get("cog")

        points.append({
            "time": r["upload_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "lat": float(lat),
            "lng": float(lng),
            "speed": round(float(speed), 1) if speed is not None else None,
            "alt": round(float(alt), 1) if alt is not None else None,
            "cog": round(float(cog), 1) if cog is not None else None,
        })

    return {"code": 200, "data": {"device_id": device_id, "points": points}}


@router.get("/api/alerts", summary="用户告警列表")
def user_alerts(
    hours: int = 48,
    limit: int = 50,
    user_id: str = Depends(get_current_user),
):
    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                "SELECT device_id FROM user_device_bind WHERE user_id=%s",
                (user_id,),
            )
            binds = [r["device_id"] for r in cursor.fetchall()]
            if not binds:
                return {"code": 200, "data": {"alerts": []}}

            placeholders = ",".join(["%s"] * len(binds))
            cursor.execute(
                f"SELECT d.id, d.device_id, di.device_name, d.raw_json, d.upload_time "
                f"FROM device_data d "
                f"LEFT JOIN device_info di ON d.device_id=di.device_id "
                f"WHERE d.device_id IN ({placeholders}) AND d.message_type='alert' "
                f"  AND d.upload_time >= DATE_SUB(NOW(), INTERVAL %s HOUR) "
                f"ORDER BY d.upload_time DESC LIMIT %s",
                binds + [hours, limit],
            )
            rows = cursor.fetchall()

    alerts = []
    for r in rows:
        alerts.append({
            "id": r["id"],
            "device_id": r["device_id"],
            "device_name": r["device_name"],
            "raw_json": json_to_str(r["raw_json"]),
            "upload_time": r["upload_time"].strftime("%Y-%m-%d %H:%M:%S"),
        })

    return {"code": 200, "data": {"alerts": alerts}}


@router.get("/api/device/{device_id}/recording/{recording_id}", summary="获取设备录音")
def device_recording(
    device_id: str,
    recording_id: int,
    fmt: str = "wav",
    user_id: str = Depends(verify_device_bind),
):
    import logging
    logger = logging.getLogger("mqtt_backend")

    with get_conn() as conn:
        with get_cursor(conn) as cursor:
            cursor.execute(
                "SELECT data, format FROM device_recording WHERE id=%s AND device_id=%s",
                (recording_id, device_id),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="录音不存在")

    amr_data = row["data"]

    if fmt == "amr":
        return Response(
            content=amr_data,
            media_type=f"audio/{row['format']}",
            headers={"Content-Disposition": f"inline; filename={device_id}_{recording_id}.{row['format']}"},
        )

    with tempfile.NamedTemporaryFile(suffix=".amr", delete=False) as amr_file:
        amr_file.write(amr_data)
        amr_path = amr_file.name
    wav_path = amr_path + ".wav"
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", amr_path, "-acodec", "pcm_s16le", "-ar", "8000", "-ac", "1",
             "-f", "wav", wav_path],
            capture_output=True, timeout=10,
        )
        if result.returncode != 0:
            logger.error(f"AMR→WAV 转码失败: {result.stderr.decode()}")
            raise HTTPException(status_code=500, detail="音频转码失败")
        with open(wav_path, "rb") as f:
            wav_data = f.read()
        return Response(
            content=wav_data,
            media_type="audio/wav",
            headers={"Content-Disposition": f"inline; filename={device_id}_{recording_id}.wav"},
        )
    finally:
        for p in (amr_path, wav_path):
            if os.path.exists(p):
                os.unlink(p)
