"""P6 후속 차량 실측 등록 — 6.2 매핑 확인(G10) → 6.3 진단 → 6.4 카메라 실측(유효 만료) → 6.5 차량 합산(BR-CV-27) → 6.6 결과."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .. import db
from ..gates import GateBlocked
from ..predict import map_level
from ..repo import measurement as mrepo
from ..repo import policy as prepo
from ..repo import reference as rrepo
from ..settings import Settings, get_settings
from . import diagnosis, ops

IN_VEHICLE = ("bus_in", "train_in")   # 차내 카메라 유형 — 실측 대상


def _parse(ts) -> datetime:
    """ISO 문자열(SQLite) 또는 datetime(PostgreSQL TIMESTAMP) → UTC datetime."""
    return datetime.strptime(db.iso(ts), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def register(
    data: bytes, vehicle_id: str, camera_id: str, caller_id: str, *, captured_at: Optional[str] = None,
    kind: str = "measurement", batch_id: Optional[int] = None, batch_seq: Optional[int] = None, s: Optional[Settings] = None,
) -> Dict[str, Any]:
    s = s or get_settings()
    ops.require_ready()
    # 6.2 G10
    with db.connect() as conn:
        cam = rrepo.camera_readiness(conn, camera_id)
        if not cam:
            raise GateBlocked("G3", "CAMERA_NOT_FOUND", f"등록된 카메라가 아니다: {camera_id}", "operator", 404, subject_kind="camera", subject_id=camera_id)
        if cam["place_type"] not in IN_VEHICLE:   # UC10 A3 — 실측은 차내(버스·열차) 카메라만 (R21-D8 정정)
            raise GateBlocked("G10", "NOT_IN_VEHICLE_CAMERA", f"{camera_id} 는 차내 카메라가 아니다 (승강장 프레임은 차량 실측이 될 수 없다)", "operator", 409,
                              subject_kind="camera", subject_id=camera_id, screen="S6")
        if not cam["has_mapping"] or cam["vehicle_id"] != vehicle_id:
            raise GateBlocked("G10", "MAPPING_MISSING", f"{vehicle_id} 가 {camera_id} 에 연결되어 있지 않다 (UC12 매핑 필요)", "operator", 409,
                              subject_kind="camera", subject_id=camera_id, screen="S6")
        map_id = int(cam["map_id"])
        route_id = cam.get("route_id")
        vp = prepo.current_validity(conn)
        rv = prepo.route_validity(conn, route_id) if route_id else None
    validity_minutes = int(rv["validity_minutes"]) if rv else int(vp["default_minutes"])

    # 6.3 진단 (P5 재사용)
    row = diagnosis.diagnose(data, camera_id, caller_id, kind=kind, captured_at=captured_at, batch_id=batch_id, batch_seq=batch_seq, s=s, check_ready=False)

    # 6.4 카메라 실측
    now_dt = datetime.now(timezone.utc)
    registered_at = _fmt(now_dt)
    demo = bool(vp["demo_on"]) and (not vp["demo_end_at"] or db.iso(vp["demo_end_at"]) > registered_at)
    measured_at = registered_at if demo or not captured_at else captured_at[:19].replace("Z", "")
    try:
        measured_dt = _parse(measured_at)
    except ValueError:
        measured_dt, measured_at = now_dt, registered_at
    expires_dt = measured_dt + timedelta(minutes=validity_minutes)
    already_expired = expires_dt <= now_dt
    with db.connect() as conn:
        mrepo.supersede_camera_measurement(conn, map_id, registered_at)
        cm_id = mrepo.insert_camera_measurement(conn, {
            "assessment_id": row["assessment_id"], "map_id": map_id, "validity_policy_id": vp["policy_id"], "measured_at": measured_at,
            "registered_at": registered_at, "is_demo": 1 if demo else 0, "validity_minutes": validity_minutes, "expires_at": _fmt(expires_dt), "superseded_at": None,
        })
        # 6.5 차량 합산
        agg = aggregate(conn, vehicle_id, vp, registered_at)
    return {"assessment": diagnosis.to_assessment_schema(row), "measurement": {
        "vehicle_id": vehicle_id, "vacant_ratio_agg": agg["vacant_ratio_agg"], "crowding_level_agg": agg["crowding_level_agg"],
        "coverage_num": agg["coverage_num"], "coverage_den": agg["coverage_den"], "partial_coverage": agg["coverage_num"] < agg["coverage_den"],
        "persons_sum": agg.get("persons_sum"), "capacity": agg.get("capacity"),
        "measured_at": agg["measured_at"], "expires_at": agg["expires_at"], "applied_validity_minutes": validity_minutes,
        "demo_mode": demo, "already_expired": already_expired, "cm_id": cm_id,
    }}


def aggregate(conn, vehicle_id: str, vp: Dict[str, Any], now_iso: str) -> Dict[str, Any]:
    """BR-CV-27 (R22 개정): 시각 창 안·유효한 활성 카메라 실측의 인원을 더해 차량 전체 정원으로 나눈다.
    누락 카메라 제외, 커버리지 기록. 정원 초과는 100% (여유 0%) 에서 멈춘다. 정원이 없으면 판독 불확실."""
    mapped = rrepo.active_mappings_by_vehicle(conn, vehicle_id)
    cms = mrepo.active_camera_measurements_for_vehicle(conn, vehicle_id)
    thr = prepo.current_threshold(conn)
    window = timedelta(minutes=int(vp["window_minutes"]))
    latest = max((_parse(c["measured_at"]) for c in cms), default=None)
    now_dt = _parse(now_iso)
    demo_on = bool(vp["demo_on"]) and (not vp["demo_end_at"] or db.iso(vp["demo_end_at"]) > now_iso)
    usable = []
    for c in cms:
        in_window = latest is not None and (latest - _parse(c["measured_at"])) <= window
        valid = demo_on or _parse(c["expires_at"]) > now_dt
        if in_window and valid:
            usable.append(c)
    mrepo.supersede_vehicle_measurement(conn, vehicle_id, now_iso)
    if not usable:
        return {"vacant_ratio_agg": 0.0, "crowding_level_agg": "uncertain", "coverage_num": 0, "coverage_den": len(mapped),
                "measured_at": now_iso, "expires_at": now_iso}
    persons = sum(int(c["person_count"] or 0) for c in usable)
    capacity = next((int(c["capacity"]) for c in sorted(usable, key=lambda c: c["measured_at"], reverse=True) if c["capacity"]), None)
    vac = max(0.0, 100.0 - persons / capacity * 100.0) if capacity else 0.0
    level = ("uncertain" if not capacity or any(c["crowding_level"] == "uncertain" for c in usable)
             else map_level(vac, thr["free_min_ratio"], thr["crowded_max_ratio"]))
    expires = min(c["expires_at"] for c in usable)
    measured = max(c["measured_at"] for c in usable)
    row = {
        "vehicle_id": vehicle_id, "validity_policy_id": vp["policy_id"], "aggregated_at": now_iso, "window_minutes": int(vp["window_minutes"]),
        "measured_at": measured, "vacant_ratio_agg": round(vac, 2), "crowding_level_agg": level, "coverage_num": len(usable),
        "coverage_den": max(len(mapped), len(usable)), "persons_sum": persons, "capacity": capacity, "expires_at": expires, "is_demo": 1 if any(c["is_demo"] for c in usable) else 0, "superseded_at": None,
    }
    mrepo.insert_vehicle_measurement(conn, row, [{"cm_id": c["cm_id"], "weight_area": float(c["roi_area"])} for c in usable])
    return row


def register_batch(items: List[Dict[str, Any]], admin: str, s: Optional[Settings] = None) -> Dict[str, Any]:
    """UC10 A4 / P8 8.3: 사전 촬영 프레임 일괄 등록. 개별 실패 격리, 제출 순서 유지. 시연 모드 꺼짐이면 즉시 만료(G14)."""
    from ..repo import diagnosis as drepo

    s = s or get_settings()
    ops.require_ready()
    with db.connect() as conn:
        vp = prepo.current_validity(conn)
        cam0 = items[0]["camera_id"] if items else "unknown"
        batch_id = drepo.insert_batch(conn, {"camera_id": cam0, "purpose": "demo_preload", "submitted_by": admin,
                                             "submitted_at": db.now_iso(), "frame_count": max(1, len(items))}) if items and rrepo.camera_readiness(conn, cam0) else None
    demo = bool(vp["demo_on"]) and (not vp["demo_end_at"] or db.iso(vp["demo_end_at"]) > db.now_iso())
    out = []
    for it in sorted(items, key=lambda x: x["seq"]):
        try:
            res = register(it["data"], it["vehicle_id"], it["camera_id"], admin, captured_at=it.get("captured_at"), kind="measurement",
                           batch_id=batch_id, batch_seq=it["seq"] if batch_id else None, s=s)
            out.append({"seq": it["seq"], "vehicle_id": it["vehicle_id"], "status": "accepted", "result": res})
        except GateBlocked as g:
            out.append({"seq": it["seq"], "vehicle_id": it["vehicle_id"], "status": "rejected", "reject": g.to_dict()})
    return {"demo_mode": demo, "items": out}
