from fastapi import APIRouter

from ..schemas import ApiGuide
from ..services import guide

router = APIRouter(prefix="/v1", tags=["guide"])


@router.get("/api-guide", response_model=ApiGuide, summary="API 활용 안내 (UC15) — 준비 중이어도 열람 가능")
def api_guide() -> dict:
    return guide.payload()
