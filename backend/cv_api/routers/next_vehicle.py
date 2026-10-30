from fastapi import APIRouter, Depends, Query

from ..auth import require_perm_caller
from ..schemas import NextVehicleResponse
from ..services import next_vehicle
from ..settings import Settings, get_settings

router = APIRouter(prefix="/v1", tags=["next-vehicle"])


@router.get("/next-vehicle", response_model=NextVehicleResponse, summary="후속 차량 여유도 조회 (UC2)")
def get_next_vehicle(
    route_id: str = Query(...), stop_id: str = Query(...), limit: int = Query(default=3, ge=1, le=5),
    caller_id: str = Depends(require_perm_caller("next_vehicle")), s: Settings = Depends(get_settings),
) -> dict:
    return next_vehicle.query(route_id, stop_id, limit, s)
