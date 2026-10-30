"""영역 A 기준 정보 — camera · roi · vehicle_type · vehicle_spec · camera_vehicle_map · route · stop."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.engine import Connection

from .. import db


def camera_readiness(conn: Connection, camera_id: str) -> Optional[Dict[str, Any]]:
    """v_camera_readiness 한 행 + 카메라 기본 정보. 없으면 None (G3)."""
    return db.q1(
        conn,
        "SELECT c.camera_id, c.place_type, c.route_id, c.stop_id, c.vehicle_type_id, c.roi_stale, c.powered, "
        "r.has_roi, r.has_capacity, r.has_mapping, r.roi_id, r.spec_id, r.map_id, r.vehicle_id, s.capacity "
        "FROM camera c JOIN v_camera_readiness r ON r.camera_id = c.camera_id LEFT JOIN vehicle_spec s ON s.spec_id = r.spec_id "
        "WHERE c.camera_id = :cid",
        cid=camera_id,
    )


def all_camera_readiness(conn: Connection) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT c.*, r.has_roi, r.has_capacity, r.has_mapping, r.vehicle_id, s.capacity FROM camera c "
                      "JOIN v_camera_readiness r ON r.camera_id=c.camera_id LEFT JOIN vehicle_spec s ON s.spec_id = r.spec_id ORDER BY c.camera_id")


def insert_camera(conn: Connection, row: Dict[str, Any]) -> None:
    db.insert(conn, "camera", row)


def route_exists(conn: Connection, route_id: str) -> bool:
    return db.q1(conn, "SELECT 1 AS x FROM route WHERE route_id=:r", r=route_id) is not None


def stop_row(conn: Connection, stop_id: str, route_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if route_id:
        return db.q1(conn, "SELECT * FROM stop WHERE stop_id=:s AND route_id=:r", s=stop_id, r=route_id)
    return db.q1(conn, "SELECT * FROM stop WHERE stop_id=:s", s=stop_id)


def vehicle_type_exists(conn: Connection, vt: str) -> bool:
    return db.q1(conn, "SELECT 1 AS x FROM vehicle_type WHERE vehicle_type_id=:v", v=vt) is not None


def upsert_vehicle_type(conn: Connection, vt: str, name: str) -> None:
    if not vehicle_type_exists(conn, vt):
        db.insert(conn, "vehicle_type", {"vehicle_type_id": vt, "type_name": name})


# ---- ROI (판본) ----
def current_roi(conn: Connection, camera_id: str) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM v_current_roi WHERE camera_id=:c", c=camera_id)


def roi_by_id(conn: Connection, roi_id: int) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM roi WHERE roi_id=:i", i=roi_id)


def roi_history(conn: Connection, camera_id: str) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT * FROM roi WHERE camera_id=:c ORDER BY effective_from DESC", c=camera_id)


def supersede_roi(conn: Connection, camera_id: str, at: str) -> None:
    db.update(conn, "roi", "camera_id=:c AND superseded_at IS NULL", {"superseded_at": at}, c=camera_id)


def insert_roi(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "roi", row)


def clear_roi_stale(conn: Connection, camera_id: str) -> None:
    db.update(conn, "camera", "camera_id=:c", {"roi_stale": 0}, c=camera_id)


# ---- 차량 제원 (판본) ----
def current_spec(conn: Connection, vehicle_type_id: str) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM v_current_spec WHERE vehicle_type_id=:v", v=vehicle_type_id)


def spec_by_id(conn: Connection, spec_id: int) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM vehicle_spec WHERE spec_id=:i", i=spec_id)


def supersede_spec(conn: Connection, vehicle_type_id: str, at: str) -> None:
    db.update(conn, "vehicle_spec", "vehicle_type_id=:v AND superseded_at IS NULL", {"superseded_at": at}, v=vehicle_type_id)


def insert_spec(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "vehicle_spec", row)


def cameras_of_type(conn: Connection, vehicle_type_id: str) -> int:
    r = db.q1(conn, "SELECT COUNT(*) AS n FROM camera WHERE vehicle_type_id=:v", v=vehicle_type_id)
    return int(r["n"]) if r else 0


# ---- 매핑 (판본) ----
def active_mapping_by_camera(conn: Connection, camera_id: str) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM v_active_mapping WHERE camera_id=:c", c=camera_id)


def active_mappings_by_vehicle(conn: Connection, vehicle_id: str) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT * FROM v_active_mapping WHERE vehicle_id=:v ORDER BY camera_id", v=vehicle_id)


def active_mappings(conn: Connection, vehicle_id: Optional[str] = None, camera_id: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM v_active_mapping WHERE 1=1"
    p: Dict[str, Any] = {}
    if vehicle_id:
        sql += " AND vehicle_id=:v"; p["v"] = vehicle_id
    if camera_id:
        sql += " AND camera_id=:c"; p["c"] = camera_id
    return db.q(conn, sql + " ORDER BY vehicle_id, camera_id", **p)


def mapping_by_id(conn: Connection, map_id: int) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM camera_vehicle_map WHERE map_id=:m", m=map_id)


def insert_mapping(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "camera_vehicle_map", row)


def release_mapping(conn: Connection, map_id: int, at: str) -> None:
    db.update(conn, "camera_vehicle_map", "map_id=:m", {"released_at": at, "verify_status": "released"}, m=map_id)
