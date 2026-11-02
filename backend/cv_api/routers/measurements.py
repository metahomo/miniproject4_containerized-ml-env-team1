from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from ..auth import require_admin, require_perm_caller
from ..gates import GateBlocked
from ..schemas import MeasurementBatchResponse, MeasurementResult
from ..services import measurement
from .diagnose import reject_unknown_fields
from ..settings import Settings, get_settings

router = APIRouter(prefix="/v1", tags=["diagnosis"])


@router.post("/measurements", response_model=MeasurementResult, summary="후속 차량 실측 등록 (UC10)")
async def register(
    request: Request,
    vehicle_id: str = Form(...), camera_id: str = Form(...), frame: UploadFile = File(...),
    captured_at: Optional[str] = Form(default=None), caller_id: str = Depends(require_perm_caller("measure")), s: Settings = Depends(get_settings),
) -> dict:
    await reject_unknown_fields(request, {"vehicle_id", "camera_id", "frame", "captured_at"})
    data = await frame.read()
    res = measurement.register(data, vehicle_id, camera_id, caller_id, captured_at=captured_at, s=s)
    del data
    res["measurement"].pop("cm_id", None)
    return res


@router.post("/measurements/batch", response_model=MeasurementBatchResponse, summary="시연용 사전 촬영 프레임 일괄 등록 (UC10 A4)")
async def register_batch(
    seq: List[int] = Form(...), vehicle_id: List[str] = Form(...), camera_id: List[str] = Form(...), frame: List[UploadFile] = File(...),
    admin: str = Depends(require_admin), s: Settings = Depends(get_settings),
) -> dict:
    if not (len(seq) == len(vehicle_id) == len(camera_id) == len(frame)):
        raise GateBlocked("G2", "BATCH_SHAPE", "seq·vehicle_id·camera_id·frame 의 개수가 같아야 한다", "self", 422, record=False)
    if len(frame) > s.BATCH_MAX_FRAMES:
        raise GateBlocked("G2", "BATCH_LIMIT", f"일괄 프레임 {len(frame)}장이 한도 {s.BATCH_MAX_FRAMES}장을 넘는다", "self", 422, record=False)
    items = [{"seq": sq, "vehicle_id": v, "camera_id": c, "data": await f.read()} for sq, v, c, f in zip(seq, vehicle_id, camera_id, frame)]
    res = measurement.register_batch(items, admin, s)
    for it in res["items"]:
        if it.get("result"):
            it["result"]["measurement"].pop("cm_id", None)
    return res
