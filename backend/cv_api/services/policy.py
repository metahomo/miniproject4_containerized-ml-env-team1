"""P3 진단 정책 — ThresholdPolicy(UC8), ValidityPolicy·시연 모드(UC11), 노선별 유효 시간 미리보기(BR-CV-24), G8·G12."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError

from .. import db
from ..external import get_providers
from ..gates import GateBlocked
from ..repo import diagnosis as drepo
from ..repo import policy as prepo
from ..repo import reference as rrepo
from ..settings import Settings, get_settings


def threshold_list() -> List[Dict[str, Any]]:
    with db.connect() as conn:
        cur = prepo.current_threshold(conn)
        rows = prepo.threshold_history(conn)
    now = db.now_iso()
    for r in rows:
        r["is_current"] = bool(cur and cur["policy_id"] == r["policy_id"])
        r["is_scheduled"] = db.iso(r["effective_from"]) > now    # 아직 적용 전인 예약 판본 — S3 가 경고한다 (2026-09-30)
    return rows


def save_threshold(body: Dict[str, Any], by: str) -> Dict[str, Any]:
    details = []
    if not (0 <= body["free_min_ratio"] <= 100 and 0 <= body["crowded_max_ratio"] <= 100):
        details.append({"field": "ratio", "reason": "0~100% 범위"})
    if body["crowded_max_ratio"] >= body["free_min_ratio"]:
        details.append({"field": "crowded_max_ratio", "reason": "혼잡 상한 < 여유 하한"})
    now = db.now_iso()
    if body["effective_from"] < now:
        details.append({"field": "effective_from", "reason": "적용 시작일이 과거다 (UC8 E4)"})
    if details:
        raise GateBlocked("G8", "THRESHOLD_INVALID", "저장 거부 — " + "; ".join(d["reason"] for d in details), "self", 422, details=details, record=False)
    with db.connect() as conn:
        try:
            cc = body.get("count_conf_min")
            pid = prepo.insert_threshold(conn, {**body, "count_conf_min": cc if cc is not None else get_settings().COUNT_CONF_MIN,
                                                "created_at": now, "created_by": by})
        except IntegrityError as e:  # 트리거·UNIQUE 위반도 G8
            raise GateBlocked("G8", "THRESHOLD_REJECTED", f"저장 거부 — {str(e.orig)[:120]}", "self", 422, record=False) from e
        drepo.invalidate_runs(conn, f"threshold policy {pid}", now)   # H8 만료 (UC8 A4)
        row = db.q1(conn, "SELECT * FROM threshold_policy WHERE policy_id=:p", p=pid)
    row["is_current"] = db.iso(row["effective_from"]) <= now
    return row


def refresh_headways(conn, s: Settings) -> None:
    """BIS·배차에서 노선별 배차 간격을 조회해 스냅샷으로 남긴다. 장애면 stale(24h) → 이후 none."""
    prov = get_providers(s)
    now = db.now_iso()
    for r in db.q(conn, "SELECT route_id FROM route"):
        last0 = prepo.latest_headway(conn, r["route_id"])
        if last0 and db.iso(last0["fetched_at"]) == now:      # 같은 초에 이미 스냅샷이 있으면 건너뛴다 (PK route_id+fetched_at)
            continue
        try:
            res = prov.headway.headway(r["route_id"])
            status, minutes = res.source_status, res.headway_minutes
        except Exception:  # noqa: BLE001 — 연계 장애 (G12)
            status, minutes = "unavailable", None
        if status in ("unavailable", "timeout"):
            last = prepo.latest_headway(conn, r["route_id"])
            if last and last["headway_minutes"] is not None:
                age = datetime.now(timezone.utc) - datetime.strptime(db.iso(last["fetched_at"]), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                if age <= timedelta(hours=s.HEADWAY_STALE_HOURS):
                    prepo.insert_headway(conn, r["route_id"], now, last["headway_minutes"], "stale"); continue
            prepo.insert_headway(conn, r["route_id"], now, None, "none"); continue
        prepo.insert_headway(conn, r["route_id"], now, minutes, status if minutes is not None else "none")


def validity_view(s: Optional[Settings] = None, refresh: bool = True) -> Dict[str, Any]:
    s = s or get_settings()
    with db.connect() as conn:
        if refresh:
            refresh_headways(conn, s)
        cur = prepo.current_validity(conn) or {}
        exc = prepo.route_exceptions(conn, cur["policy_id"]) if cur else []
        preview = prepo.route_validity_all(conn)
        names = {r["route_id"]: r["route_name"] for r in db.q(conn, "SELECT route_id, route_name FROM route")}   # 버스 번호 (2026-09-30)
    pol = {**cur, "route_exceptions": exc, "demo_on": bool(cur.get("demo_on"))} if cur else {}
    return {"policy": pol, "preview": [{"route_id": p["route_id"], "route_name": names.get(p["route_id"]), "headway_minutes": p["headway_minutes"],
                                        "validity_minutes": int(p["validity_minutes"]), "validity_source": p["validity_source"]} for p in preview]}


def save_validity(body: Dict[str, Any], by: str, s: Optional[Settings] = None) -> Dict[str, Any]:
    s = s or get_settings()
    details = []
    if body["factor"] <= 0 or body["cap_minutes"] <= 0 or body["default_minutes"] <= 0 or body["window_minutes"] <= 0:
        details.append({"field": "values", "reason": "양수"})
    if body["cap_minutes"] < body["default_minutes"]:
        details.append({"field": "cap_minutes", "reason": "상한 ≥ 기본값"})
    demo_end = body.get("demo_end_at")
    if body.get("demo_on") and not demo_end:
        demo_end = (datetime.now(timezone.utc) + timedelta(hours=s.DEMO_DEFAULT_HOURS)).strftime("%Y-%m-%dT%H:%M:%S")   # 기본 +2h
    with db.connect() as conn:
        for e in body.get("route_exceptions", []):
            if not rrepo.route_exists(conn, e["route_id"]):
                details.append({"field": "route_exceptions", "reason": f"예외 노선이 기준 정보에 없다: {e['route_id']}"})
        if details:
            raise GateBlocked("G8", "VALIDITY_INVALID", "저장 거부 — " + "; ".join(d["reason"] for d in details), "self", 422, details=details, record=False)
        now = db.now_iso()
        prepo.supersede_validity(conn, now)
        try:
            prepo.insert_validity(conn, {
                "basis": "headway", "factor": body["factor"], "cap_minutes": body["cap_minutes"], "default_minutes": body["default_minutes"],
                "window_minutes": body["window_minutes"], "demo_on": 1 if body.get("demo_on") else 0, "demo_end_at": demo_end if body.get("demo_on") else None,
                "effective_from": now, "superseded_at": None, "created_at": now, "created_by": by,
            }, body.get("route_exceptions", []))
        except IntegrityError as e:
            raise GateBlocked("G8", "VALIDITY_REJECTED", f"저장 거부 — {str(e.orig)[:120]}", "self", 422, record=False) from e
    return validity_view(s, refresh=True)


def set_demo(on: bool, by: str, demo_end_at: Optional[str] = None, s: Optional[Settings] = None) -> Dict[str, Any]:
    """P8 8.2/8.5: 현재 규칙을 유지한 채 시연 모드만 전환 (새 판본)."""
    with db.connect() as conn:
        cur = prepo.current_validity(conn)
        exc = prepo.route_exceptions(conn, cur["policy_id"]) if cur else []
    body = {"factor": cur["factor"], "cap_minutes": cur["cap_minutes"], "default_minutes": cur["default_minutes"],
            "window_minutes": cur["window_minutes"], "route_exceptions": exc, "demo_on": on, "demo_end_at": demo_end_at}
    return save_validity(body, by, s)
