from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from ..auth import require_admin, require_perm_caller
from ..gates import GateBlocked
from ..schemas import Assessment, BatchResult
from ..services import diagnosis
from ..settings import Settings, get_settings

router = APIRouter(prefix="/v1", tags=["diagnosis"])


ALLOWED_FIELDS = {"camera_id", "frame", "captured_at"}


async def reject_unknown_fields(request: Request, allowed: set) -> None:
    """FR-02 / G2: 정의되지 않은 항목이 포함된 요청은 진단 없이 반려한다 (multipart 는 Pydantic extra=forbid 가 닿지 않음)."""
    form = await request.form()
    unknown = sorted(set(form.keys()) - allowed)
    if unknown:
        raise GateBlocked("G2", "UNDEFINED_FIELDS", f"반려 — 정의되지 않은 항목 포함: {', '.join(unknown)}", "self", 422,
                          allowed_spec={"fields": sorted(allowed)}, record=False)


@router.post("/diagnose", response_model=Assessment, summary="현재 프레임 잔여 공간 진단 (UC1)")
async def diagnose(
    request: Request,
    camera_id: str = Form(...),
    frame: UploadFile = File(...),
    captured_at: Optional[str] = Form(default=None),
    caller_id: str = Depends(require_perm_caller("diagnose")),
    s: Settings = Depends(get_settings),
) -> dict:
    await reject_unknown_fields(request, ALLOWED_FIELDS)
    data = await frame.read()
    row = diagnosis.diagnose(data, camera_id, caller_id, kind="single", captured_at=captured_at, s=s)
    del data
    out = diagnosis.to_assessment_schema(row)
    request.state.log_result = {"label": out["crowding_level"], "score": out["mean_confidence"],   # 요청 로그 (D5) — 원문 없음
                                "model_version": out["versions"]["model_commit"]}
    return out


@router.post("/diagnose/batch", response_model=BatchResult, summary="사전 녹화 프레임 일괄 검증 (UC4)")
async def diagnose_batch(
    request: Request,
    camera_id: str = Form(...),
    frames: List[UploadFile] = File(...),
    admin: str = Depends(require_admin),
    s: Settings = Depends(get_settings),
) -> dict:
    from ..services import verification

    await reject_unknown_fields(request, {"camera_id", "frames"})
    if len(frames) > s.BATCH_MAX_FRAMES:
        raise GateBlocked("G2", "BATCH_LIMIT", f"일괄 프레임 {len(frames)}장이 한도 {s.BATCH_MAX_FRAMES}장을 넘는다", "self", 422,
                          allowed_spec=diagnosis.allowed_spec(s), record=False)
    payloads = [(i + 1, await f.read()) for i, f in enumerate(frames)]
    return verification.run_batch(camera_id, payloads, admin, s)
