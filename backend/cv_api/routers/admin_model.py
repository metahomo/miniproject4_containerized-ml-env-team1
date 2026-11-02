"""운영 관리자 API 중 검출기가 필요한 것 — 웹서비스 연동(P1 1.5~1.6)·검출기 적재 상태/미리 올리기.

진단 API 서버(9544)가 서빙한다. 모델이 이 프로세스 안에 적재되어 있기 때문이다. 경로는 `/v1/admin/*` 그대로.
"""
from __future__ import annotations

import time
from typing import List

from fastapi import APIRouter, Depends, File, Query, UploadFile

from .. import db
from ..auth import require_admin, require_admin_route
from ..gates import GateBlocked
from ..predict import OllamaVLDetector
from ..repo import ops as ops_repo
from ..schemas import DetectorPreloadResult, Integration, IntegrationCreate
from ..services import ops
from ..settings import Settings, get_settings

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin_route)])   # 운영 관리자 + 관제 담당자 읽기 경로 (RBAC)


# ---- 연동 (P1 1.5~1.6) ----
@router.get("/integrations", response_model=List[Integration], summary="웹서비스 연동 목록")
def integrations() -> list:
    with db.connect() as conn:
        return ops_repo.integrations(conn)


@router.post("/integrations", response_model=Integration, status_code=201, summary="웹서비스 연동 등록 (P1 1.5) — G0 통과 후")
def integration_create(body: IntegrationCreate, admin: str = Depends(require_admin)) -> dict:
    ops.require_ready()
    with db.connect() as conn:
        iid = ops_repo.insert_integration(conn, {"instance_id": ops.runtime.instance_id, "registered_at": db.now_iso(), "registered_by": admin,
                                                 "test_request_id": None, "first_response_ms": None, "status": "registered", "reverted_reason": None})
        ops_repo.update_instance(conn, ops.runtime.instance_id, {"endpoint_url": body.endpoint_url})
        return ops_repo.integration_row(conn, iid)


@router.post("/integrations/{integration_id}/test", response_model=Integration, summary="연동 시험 호출 (P1 1.6, G16)")
async def integration_test(integration_id: int, camera_id: str = Query(...), frame: UploadFile = File(...), admin: str = Depends(require_admin),
                           s: Settings = Depends(get_settings)) -> dict:
    from ..services import diagnosis

    data = await frame.read()
    t0 = time.perf_counter()
    with db.connect() as conn:
        row = ops_repo.integration_row(conn, integration_id)
    if not row:
        raise GateBlocked("G16", "INTEGRATION_NOT_FOUND", f"연동이 없다: {integration_id}", "self", 404, record=False)
    try:
        res = diagnosis.diagnose(data, camera_id, admin, kind="test_call", s=s)
        ms = int((time.perf_counter() - t0) * 1000)
        with db.connect() as conn:
            ops_repo.update_integration(conn, integration_id, {"test_request_id": res["request_id"], "first_response_ms": ms, "status": "confirmed"})
    except GateBlocked as g:
        with db.connect() as conn:
            ops_repo.update_integration(conn, integration_id, {"status": "reverted", "reverted_reason": f"{g.gate} {g.reason}"[:200]})
        raise GateBlocked("G16", "TEST_CALL_FAILED", f"시험 호출 실패 — 연동 등록 되돌림 ({g.gate} {g.reason})", "self", 409, record=False) from g
    finally:
        del data
    with db.connect() as conn:
        return ops_repo.integration_row(conn, integration_id)


# ---- 검출기 적재 (모델 로딩 시간 관리) ----
@router.get("/detector", summary="검출기 적재 상태 (종류·모델·적재 소요·웜업 시각·마지막 추론 ms)")
def detector_status(s: Settings = Depends(get_settings)) -> dict:
    out = ops.runtime.state.as_dict()
    out["available"] = {"yolov8": s.MODEL_WEIGHTS.exists(), "ollama_vl": None}
    det = ops.runtime.detector
    if isinstance(det, OllamaVLDetector):
        try:
            from .. import ollama_client
            out["ollama"] = {"version": ollama_client.health(), "loaded_models": ollama_client.loaded_models()}
        except Exception as e:  # noqa: BLE001
            out["ollama"] = {"error": str(e)}
    return out


@router.post("/detector/preload", response_model=DetectorPreloadResult, summary="검출기 (재)적재·웜업 — Ollama 면 미리 올리기(가이드 1.6, 1회)")
def detector_preload(s: Settings = Depends(get_settings)) -> dict:
    try:
        return ops.preload_detector(s)
    except Exception as e:  # noqa: BLE001
        raise GateBlocked("G5", "PRELOAD_FAILED", f"적재 실패 — {e}", "operator", 503, subject_kind="instance", subject_id=str(ops.runtime.instance_id or 0)) from e
