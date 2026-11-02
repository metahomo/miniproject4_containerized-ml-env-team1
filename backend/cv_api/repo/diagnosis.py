"""영역 C 진단 — batch · diagnosis_request · assessment · assessment_warning · verification_* · quality_metric."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.engine import Connection

from .. import db


def insert_request(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "diagnosis_request", row)


def finish_request(conn: Connection, request_id: int, responded_at: str) -> None:
    db.update(conn, "diagnosis_request", "request_id=:r", {"responded_at": responded_at}, r=request_id)


def insert_assessment(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "assessment", row)


def insert_warnings(conn: Connection, assessment_id: int, warnings: List[Dict[str, Any]]) -> None:
    seen = set()
    for w in warnings:
        if w["code"] in seen:
            continue
        seen.add(w["code"])
        db.insert(conn, "assessment_warning", {
            "assessment_id": assessment_id, "warning_code": w["code"], "raw_code": w.get("raw_code"), "detail": w.get("detail"),
        })


def assessment_view(conn: Connection, assessment_id: int) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM v_assessment WHERE assessment_id=:a", a=assessment_id)


def assessment_by_request(conn: Connection, request_id: int) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM v_assessment WHERE request_id=:r", r=request_id)


def warnings_of(conn: Connection, assessment_id: int) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT warning_code AS code, detail FROM assessment_warning WHERE assessment_id=:a ORDER BY warning_code", a=assessment_id)


def insert_batch(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "batch", row)


def batch_row(conn: Connection, batch_id: int) -> Optional[Dict[str, Any]]:
    return db.q1(conn, "SELECT * FROM batch WHERE batch_id=:b", b=batch_id)


def batch_requests(conn: Connection, batch_id: int) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT * FROM diagnosis_request WHERE batch_id=:b ORDER BY batch_seq", b=batch_id)


def insert_verification_run(conn: Connection, row: Dict[str, Any]) -> int:
    return db.insert(conn, "verification_run", row)


def insert_verification_item(conn: Connection, row: Dict[str, Any]) -> None:
    db.insert(conn, "verification_item", row)


def verification_items_view(conn: Connection, run_id: int) -> List[Dict[str, Any]]:
    return db.q(conn, "SELECT * FROM v_verification_item WHERE run_id=:r ORDER BY batch_seq", r=run_id)


def invalidate_runs(conn: Connection, reason: str, at: str) -> int:
    return db.update(conn, "verification_run", "invalidated_at IS NULL", {"invalidated_at": at, "invalidated_reason": reason})


def audit_records(conn: Connection, since: Optional[str], until: Optional[str], limit: int = 500) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM v_audit_record WHERE 1=1"
    p: Dict[str, Any] = {"lim": limit}
    if since:
        sql += " AND at >= :s"; p["s"] = since
    if until:
        sql += " AND at <= :u"; p["u"] = until
    return db.q(conn, sql + " ORDER BY at DESC LIMIT :lim", **p)
