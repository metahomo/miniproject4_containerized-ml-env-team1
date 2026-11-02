"""게이트 모듈 — SD_01 §14 G0~G17 → HTTP 상태 (research R7) + gate_event 기록 (SD_03 1급 엔티티).

처리 중단형: G0·G5 503, G1 401/403, G2·G8·G9 422, G3·G11 404, G4·G10 409, G15·G16 409, G17 409
출력 차단형(G6·G7·G12·G13)은 예외가 아니라 200 응답의 상태 필드로 표현한다 — 여기서 다루지 않는다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from . import db

GATE_STATUS = {
    "G0": 503, "G1": 401, "G2": 422, "G3": 404, "G4": 409, "G5": 503,
    "G8": 422, "G9": 422, "G10": 409, "G11": 404, "G14": 409, "G15": 409, "G16": 409, "G17": 409,
}

# 게이트 → 화면 (gate_event.screen_code 기본값, SD_02 §14)
GATE_SCREEN = {
    "G0": "S0", "G1": "S0", "G2": "S5", "G3": "S2", "G4": "S5", "G5": "S1", "G8": "S3", "G9": "S2",
    "G10": "S6", "G11": "S7", "G14": "S8", "G15": "S1", "G16": "S1", "G17": "S9",
}


class GateBlocked(Exception):
    """게이트 미통과. 예외 핸들러가 GateError JSON 으로 바꾸고 gate_event 를 기록한다."""

    def __init__(
        self,
        gate: str,
        reason_code: str,
        reason: str,
        resolver_role: str = "self",
        http_status: Optional[int] = None,
        *,
        subject_kind: Optional[str] = None,
        subject_id: Optional[str] = None,
        allowed_spec: Optional[Dict[str, Any]] = None,
        details: Optional[List[Dict[str, Any]]] = None,
        screen: Optional[str] = None,
        record: bool = True,
    ):
        super().__init__(reason)
        self.gate, self.reason_code, self.reason = gate, reason_code, reason
        self.resolver_role = resolver_role
        self.http_status = http_status or GATE_STATUS.get(gate, 409)
        self.subject_kind, self.subject_id = subject_kind, subject_id
        self.allowed_spec, self.details = allowed_spec, details
        self.screen = screen or GATE_SCREEN.get(gate, "S0")
        self.record = record and subject_kind is not None and subject_id is not None
        self.gate_event_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "resolver_role": self.resolver_role,
            "allowed_spec": self.allowed_spec,
            "details": self.details,
            "gate_event_id": self.gate_event_id,
        }


def record_gate_event(exc: GateBlocked) -> Optional[int]:
    """해제 주체가 타인(operator/external)인 게이트만 이벤트로 남긴다 — C7 요청의 대상이 된다.
    본인 해제(값 수정)는 반려 응답 자체가 기록이다(SD_03 §11 G2·G8)."""
    if not exc.record or exc.resolver_role == "self":
        return None
    role = exc.resolver_role if exc.resolver_role in ("self", "operator", "external", "undefined") else "operator"
    with db.connect() as conn:
        # 같은 대상·같은 게이트의 열린 이벤트가 있으면 재사용
        existing = db.q1(
            conn,
            "SELECT event_id FROM gate_event WHERE gate_code=:g AND subject_kind=:k AND subject_id=:i AND resolved_at IS NULL "
            "ORDER BY occurred_at DESC LIMIT 1",
            g=exc.gate, k=exc.subject_kind, i=exc.subject_id,
        )
        if existing:
            return int(existing["event_id"])
        return db.insert(conn, "gate_event", {
            "gate_code": exc.gate, "screen_code": exc.screen, "subject_kind": exc.subject_kind,
            "subject_id": str(exc.subject_id), "occurred_at": db.now_iso(), "reason_code": exc.reason_code,
            "reason_text": exc.reason, "resolver_role": role,
        })


async def gate_exception_handler(_request: Request, exc: GateBlocked) -> JSONResponse:
    try:
        exc.gate_event_id = record_gate_event(exc)
    except Exception:  # 기록 실패가 응답을 막지 않는다
        exc.gate_event_id = None
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())


def resolve_gate_events(conn, gate: str, subject_kind: str, subject_id: str, resolved_by: str, ref: str) -> int:
    return db.update(
        conn, "gate_event",
        "gate_code=:g AND subject_kind=:k AND subject_id=:i AND resolved_at IS NULL",
        {"resolved_at": db.now_iso(), "resolved_by": resolved_by, "resolution_ref": ref},
        g=gate, k=subject_kind, i=subject_id,
    )
