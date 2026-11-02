"""영역 B 정책 · F 스냅샷 — threshold_policy · validity_policy · validity_route_exception · route_headway."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.engine import Connection

from .. import db


def current_threshold(conn: Connection) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM v_current_threshold")


def threshold_history(conn: Connection) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT * FROM threshold_policy ORDER BY effective_from DESC")


def insert_threshold(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "threshold_policy", row)


def current_validity(conn: Connection) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM v_current_validity")


def validity_history(conn: Connection) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT * FROM validity_policy ORDER BY effective_from DESC, policy_id DESC")


def supersede_validity(conn: Connection, at: str) -> None:
    db.update(conn, "validity_policy", "superseded_at IS NULL", {"superseded_at": at})


def insert_validity(conn: Connection, row: Dict[str, Any], exceptions: List[Dict[str, Any]]) -> int:
    pid = db.insert(conn, "validity_policy", row)
    for e in exceptions:
        db.insert(conn, "validity_route_exception", {"policy_id": pid, "route_id": e["route_id"], "minutes": e["minutes"]})
    return pid


def route_exceptions(conn: Connection, policy_id: int) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT route_id, minutes FROM validity_route_exception WHERE policy_id=:p", p=policy_id)


def route_validity(conn: Connection, route_id: str) -> Optional[Dict[str, Any]]:
    """BR-CV-24 단일 산출 지점 v_route_validity_minutes."""
    return db.q1(conn, "SELECT * FROM v_route_validity_minutes WHERE route_id=:r", r=route_id)


def route_validity_all(conn: Connection) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT * FROM v_route_validity_minutes ORDER BY route_id")


def insert_headway(conn: Connection, route_id: str, fetched_at: str, minutes: Optional[int], status: str) -> None:
    db.insert(conn, "route_headway", {"route_id": route_id, "fetched_at": fetched_at, "headway_minutes": minutes, "source_status": status})


def latest_headway(conn: Connection, route_id: str) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM route_headway WHERE route_id=:r ORDER BY fetched_at DESC LIMIT 1", r=route_id)
