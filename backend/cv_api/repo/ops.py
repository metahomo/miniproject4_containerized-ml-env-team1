"""영역 E 운영 — model_package · server_instance · integration · gate_event · quality_metric, 영역 G api_guide."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .. import db


def upsert_model_package(conn: Connection, rec: Dict[str, Any]) -> int:
    row = db.q1(conn, "SELECT model_package_id FROM model_package WHERE commit_hash=:c AND weights_file=:w", c=rec["commit_hash"], w=rec["weights_file"])
    if row:
        return int(row["model_package_id"])
    return db.insert(conn, "model_package", rec)


def model_package(conn: Connection, model_package_id: int) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM model_package WHERE model_package_id=:i", i=model_package_id)


def insert_instance(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "server_instance", row)


def update_instance(conn: Connection, instance_id: int, set_: Dict[str, Any]) -> None:
    db.update(conn, "server_instance", "instance_id=:i", set_, i=instance_id)


def readiness(conn: Connection) -> Optional[Dict[str, Any]]:
    """G0 단일 판정 지점 v_readiness + 인스턴스 부가 정보."""
    return db.q1(
        conn,
        "SELECT r.*, s.model_package_id, s.detector_kind, s.load_seconds, s.warmup_done_at, m.commit_hash, m.weights_file "
        "FROM v_readiness r JOIN server_instance s ON s.instance_id=r.instance_id "
        "LEFT JOIN model_package m ON m.model_package_id=s.model_package_id",
    )


def insert_integration(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "integration", row)


def update_integration(conn: Connection, integration_id: int, set_: Dict[str, Any]) -> None:
    db.update(conn, "integration", "integration_id=:i", set_, i=integration_id)


def integration_row(conn: Connection, integration_id: int) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM integration WHERE integration_id=:i", i=integration_id)


def integrations(conn: Connection) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT * FROM integration ORDER BY registered_at DESC")


def open_gate_events(conn: Connection, subject_kind: Optional[str], subject_id: Optional[str], requested_only: bool = False) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM v_gate_open WHERE 1=1"
    p: Dict[str, Any] = {}
    if requested_only:     # C7 «요청 보내기»로 운영 관리자에게 온 것 — S1 '받은 요청' (결정 D10)
        sql += " AND request_sent_at IS NOT NULL"
        return db.q(conn, sql + " ORDER BY request_sent_at DESC")
    if subject_kind:
        sql += " AND subject_kind=:k"; p["k"] = subject_kind
    if subject_id:
        sql += " AND subject_id=:i"; p["i"] = subject_id
    return db.q(conn, sql + " ORDER BY occurred_at DESC", **p)


def gate_event(conn: Connection, event_id: int) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM gate_event WHERE event_id=:e", e=event_id)


def mark_request_sent(conn: Connection, event_id: int, by: str, at: str) -> None:
    db.update(conn, "gate_event", "event_id=:e", {"request_sent_at": at, "request_sent_by": by}, e=event_id)


def roi_stale_cameras(conn: Connection) -> List[str]:
    return [r["camera_id"] for r in db.q(conn, "SELECT camera_id FROM camera WHERE roi_stale=1 ORDER BY camera_id")]


def insert_quality_metric(conn: Connection, row: Dict[str, Any]) -> None:
    db.insert(conn, "quality_metric", row)


def latest_quality_metrics(conn: Connection, limit: int = 24) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT * FROM quality_metric ORDER BY computed_at DESC LIMIT :l", l=limit)


# ---- G 안내 ----
def current_guide(conn: Connection) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM api_guide ORDER BY updated_at DESC, guide_id DESC LIMIT 1")


def upsert_guide(conn: Connection, version: str, status: str, contract_hash: str, at: str, by: str) -> int:
    row = db.q1(conn, "SELECT guide_id FROM api_guide WHERE version=:v", v=version)
    if row:
        db.update(conn, "api_guide", "guide_id=:g", {"status": status, "contract_hash": contract_hash, "verified_at": at, "verified_by": by,
                                                      "published_at": at if status == "published" else None, "updated_at": at}, g=row["guide_id"])
        return int(row["guide_id"])
    return db.insert(conn, "api_guide", {"version": version, "status": status, "contract_hash": contract_hash, "verified_at": at, "verified_by": by,
                                         "published_at": at if status == "published" else None, "updated_at": at})


def replace_endpoints(conn: Connection, guide_id: int, rows: List[Dict[str, Any]]) -> None:
    conn.execute(text("DELETE FROM api_endpoint WHERE guide_id = :g"), {"g": guide_id})   # 방언 중립 자리표시자 (PostgreSQL 호환)
    for r in rows:
        db.insert(conn, "api_endpoint", {"guide_id": guide_id, **r})


def endpoints(conn: Connection, guide_id: int) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT * FROM api_endpoint WHERE guide_id=:g ORDER BY feature_code", g=guide_id)
