"""영역 D 실측 — camera_measurement · vehicle_measurement · vehicle_measurement_component · arrival_snapshot."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.engine import Connection

from .. import db


def supersede_camera_measurement(conn: Connection, map_id: int, at: str) -> None:
    db.update(conn, "camera_measurement", "map_id=:m AND superseded_at IS NULL", {"superseded_at": at}, m=map_id)


def insert_camera_measurement(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "camera_measurement", row)


def active_camera_measurements_for_vehicle(conn: Connection, vehicle_id: str) -> List[Dict[str, Any]]:
    """차량에 매핑된 카메라들의 활성 실측 + 결과값·인원·정원·ROI 면적."""
    return db.q(
        conn,
        "SELECT cm.*, m.camera_id, a.vacant_capacity_ratio, a.crowding_level, a.person_count, s.capacity, r.area AS roi_area "
        "FROM camera_measurement cm JOIN camera_vehicle_map m ON m.map_id = cm.map_id "
        "JOIN assessment a ON a.assessment_id = cm.assessment_id JOIN roi r ON r.roi_id = a.roi_id "
        "LEFT JOIN vehicle_spec s ON s.spec_id = a.spec_id "
        "WHERE m.vehicle_id=:v AND m.released_at IS NULL AND cm.superseded_at IS NULL",
        v=vehicle_id,
    )


def supersede_vehicle_measurement(conn: Connection, vehicle_id: str, at: str) -> None:
    db.update(conn, "vehicle_measurement", "vehicle_id=:v AND superseded_at IS NULL", {"superseded_at": at}, v=vehicle_id)


def insert_vehicle_measurement(conn: Connection, row: Dict[str, Any], components: List[Dict[str, Any]]) -> int:
    vm_id = db.insert(conn, "vehicle_measurement", row)
    for c in components:
        db.insert(conn, "vehicle_measurement_component", {"vm_id": vm_id, "cm_id": c["cm_id"], "weight_area": c["weight_area"]})
    return vm_id


def vehicle_status(conn: Connection, vehicle_id: str) -> Optional[Dict[str, Any]]:
    """G13 단일 판정 지점 v_vehicle_measurement_status."""
    return db.q1(conn, "SELECT * FROM v_vehicle_measurement_status WHERE vehicle_id=:v", v=vehicle_id)


def warnings_for_vehicle(conn: Connection, vm_id: int) -> List[Dict[str, Any]]:
    return db.q(
        conn,
        "SELECT DISTINCT w.warning_code AS code, w.detail FROM vehicle_measurement_component c "
        "JOIN camera_measurement cm ON cm.cm_id=c.cm_id JOIN assessment_warning w ON w.assessment_id=cm.assessment_id "
        "WHERE c.vm_id=:vm ORDER BY w.warning_code",
        vm=vm_id,
    )


def insert_arrival(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "arrival_snapshot", row)


def expired_today(conn: Connection, day_prefix: str) -> int:
    r = db.q1(
        conn,
        # 날짜 범위 비교 — LIKE 는 PostgreSQL TIMESTAMP 에 쓸 수 없다 (T073 후속). ISO 문자열 비교라 SQLite 도 같다
        "SELECT COUNT(*) AS n FROM camera_measurement WHERE superseded_at IS NULL AND expires_at >= :d0 AND expires_at <= :now",
        d0=day_prefix + "T00:00:00", now=db.now_iso(),
    )
    return int(r["n"]) if r else 0
