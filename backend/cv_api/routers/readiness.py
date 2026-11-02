from fastapi import APIRouter

from ..schemas import Readiness
from ..services import ops

router = APIRouter(prefix="/v1", tags=["readiness"])


@router.get("/readiness", response_model=Readiness, summary="준비 상태 확인 (UC9, G0)")
def readiness() -> dict:
    return ops.readiness_payload()
