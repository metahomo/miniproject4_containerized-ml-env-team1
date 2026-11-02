from fastapi import APIRouter, Depends

from .. import db
from ..auth import require_caller
from ..gates import GateBlocked
from ..repo import ops as ops_repo
from ..schemas import GateEvent

router = APIRouter(prefix="/v1", tags=["diagnosis"])


@router.post("/gate-events/{event_id}/request", response_model=GateEvent, summary="운영 관리자에게 해제 요청 보내기 (C7, U5)")
def send_request(event_id: int, caller_id: str = Depends(require_caller)) -> dict:
    with db.connect() as conn:
        ev = ops_repo.gate_event(conn, event_id)
        if not ev:
            raise GateBlocked("G8", "EVENT_NOT_FOUND", f"게이트 이벤트가 없다: {event_id}", "self", 404, record=False)
        if ev["resolver_role"] == "self":
            raise GateBlocked("G8", "SELF_RESOLVABLE", "해제 주체가 본인인 게이트에는 요청을 보내지 않는다 — 값을 수정해 재시도", "self", 409, record=False)
        if not ev["request_sent_at"]:
            ops_repo.mark_request_sent(conn, event_id, caller_id, db.now_iso())
        return ops_repo.gate_event(conn, event_id)
