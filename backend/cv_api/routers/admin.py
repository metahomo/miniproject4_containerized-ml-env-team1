"""운영 관리자 API — X-Admin-Key (G1). UC6·7·8·11·12 + 카메라 등록(R9) + 검증 판정(UC4) + 운영 상태·게이트·집계.

웹 백엔드(9524)가 서빙한다. DB 만 읽고 쓰며 검출기를 쓰지 않는다. 검출기가 필요한 연동·적재는 `admin_model.py`(진단 API 9544).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile

from .. import db
from ..auth import require_admin, require_admin_route
from ..repo import diagnosis as drepo
from ..repo import measurement as mrepo
from ..repo import ops as ops_repo
from ..schemas import (
    CameraCreate, CameraOperationUpdate, CameraPowerRow, CameraPowerSet, CameraStatus, CsvResult, DemoRemapRequest, FleetList, GateEvent, Mapping,
    MappingCreate, OpsStatus, Roi, RoiCreate, ThresholdPolicy, ThresholdPolicyCreate, ValidityPolicyCreate, ValidityPolicyView,
    VehicleSpec, VehicleSpecCreate, VerificationRun, VerificationRunCreate,
)
from ..services import camera_power, demo_remap, ops, policy, reference, verification
from ..external.bis import calls_today as bis_calls_today
from ..settings import Settings, get_settings

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin_route)])   # 운영 관리자 + 관제 담당자 읽기 경로 (RBAC)


# ---- 카메라·ROI·제원 ----
@router.get("/cameras", response_model=List[CameraStatus], summary="카메라 목록·현황")
def cameras() -> list:
    return reference.list_cameras()


@router.post("/cameras", response_model=CameraStatus, status_code=201, summary="카메라 등록 (G3 해제 경로)")
def create_camera(body: CameraCreate, admin: str = Depends(require_admin)) -> dict:
    return reference.register_camera(body.model_dump(), admin)


@router.get("/camera-power", response_model=List[CameraPowerRow], summary="카메라 전원 관리 표 (S2b) — 호선·차량·칸·운행·정원·인원·밀집도·동작여부")
def camera_power_list() -> list:
    return camera_power.overview()


@router.post("/cameras/{camera_id}/power", response_model=CameraPowerRow, summary="카메라 전원 켜기·끄기 (S2b). off 면 진단 요청 거부, on 이면 주기 자동 진단")
def camera_power_set(camera_id: str, body: CameraPowerSet, admin: str = Depends(require_admin)) -> dict:
    return camera_power.set_power(camera_id, body.on, admin)


@router.patch("/cameras/{camera_id}/operation", response_model=CameraPowerRow, summary="카메라 운영 설정 (S2b) — 칸·프레임 소스·진단 주기")
def camera_operation(camera_id: str, body: CameraOperationUpdate, s: Settings = Depends(get_settings)) -> dict:
    return camera_power.update_settings(camera_id, body.model_dump(exclude_unset=True), s)


@router.get("/cameras/{camera_id}", response_model=CameraStatus, summary="카메라 현황 (v_camera_readiness)")
def camera(camera_id: str) -> dict:
    return reference.camera_status(camera_id)


@router.get("/cameras/{camera_id}/roi", response_model=List[Roi], summary="ROI 판본 목록")
def roi_list(camera_id: str) -> list:
    return reference.roi_history(camera_id)


@router.post("/cameras/{camera_id}/roi", response_model=Roi, status_code=201, summary="ROI 등록·수정 (UC6)")
def roi_save(camera_id: str, body: RoiCreate, admin: str = Depends(require_admin)) -> dict:
    return reference.save_roi(camera_id, body.model_dump(), admin)


@router.post("/vehicle-types/{vehicle_type_id}/spec", response_model=VehicleSpec, status_code=201, summary="차량 제원 등록·수정 (UC7)")
def spec_save(vehicle_type_id: str, body: VehicleSpecCreate, admin: str = Depends(require_admin)) -> dict:
    return reference.save_spec(vehicle_type_id, body.model_dump(), admin)


# ---- 매핑 ----
@router.get("/mappings", response_model=List[Mapping], summary="활성 매핑 목록")
def mappings(vehicle_id: Optional[str] = None, camera_id: Optional[str] = None) -> list:
    return reference.list_mappings(vehicle_id, camera_id)


@router.post("/mappings", response_model=Mapping, status_code=201, summary="카메라·차량 식별자 매핑 (UC12)")
def mapping_save(body: MappingCreate, admin: str = Depends(require_admin), s: Settings = Depends(get_settings)) -> dict:
    return reference.save_mapping(body.model_dump(), admin, "select", s)


@router.delete("/mappings/{map_id}", status_code=204, summary="매핑 해제 (UC12 A3)")
def mapping_release(map_id: int, admin: str = Depends(require_admin)) -> None:
    reference.release_mapping(map_id, admin)


@router.post("/demo/bis-remap", summary="시연 카메라를 지금 도착 예정인 BIS 차량으로 다시 연결 (T097, S8)")
def demo_bis_remap(body: Optional[DemoRemapRequest] = None, admin: str = Depends(require_admin), s: Settings = Depends(get_settings)) -> dict:
    b = body or DemoRemapRequest()
    return demo_remap.remap(admin, b.route_id, b.stop_id, b.camera_ids, s)


@router.post("/mappings/csv", response_model=CsvResult, summary="CSV 일괄 등록 (UC12 A1)")
async def mapping_csv(file: UploadFile = File(...), admin: str = Depends(require_admin), s: Settings = Depends(get_settings)) -> dict:
    return reference.import_csv(await file.read(), admin, s)


@router.get("/fleet", response_model=FleetList, summary="운행 정보 차량 목록 (자동완성)")
def fleet(route_id: str = Query(...), q: Optional[str] = None, s: Settings = Depends(get_settings)) -> dict:
    return reference.fleet(route_id, q, s)


# ---- 정책 ----
@router.get("/policies/threshold", response_model=List[ThresholdPolicy], summary="등급 기준 현재·이력 (UC8)")
def threshold_list() -> list:
    return policy.threshold_list()


@router.post("/policies/threshold", response_model=ThresholdPolicy, status_code=201, summary="등급 경계 조정 (UC8)")
def threshold_save(body: ThresholdPolicyCreate, admin: str = Depends(require_admin)) -> dict:
    return policy.save_threshold(body.model_dump(), admin)


@router.get("/policies/validity", response_model=ValidityPolicyView, summary="유효 시간 규칙·시연 모드·노선별 미리보기 (UC11)")
def validity_get(s: Settings = Depends(get_settings)) -> dict:
    return policy.validity_view(s)


@router.post("/policies/validity", response_model=ValidityPolicyView, status_code=201, summary="유효 시간 규칙·시연 모드 설정 (UC11)")
def validity_save(body: ValidityPolicyCreate, admin: str = Depends(require_admin), s: Settings = Depends(get_settings)) -> dict:
    return policy.save_validity(body.model_dump(), admin, s)


# ---- 검증 ----
@router.post("/verification-runs", response_model=VerificationRun, status_code=201, summary="정확도 판정 (UC4 6단계, SC-01·02)")
def verification_run(body: VerificationRunCreate, admin: str = Depends(require_admin)) -> dict:
    return verification.create_run(body.model_dump(), admin)


# ---- 운영 상태·게이트·집계 ----
@router.get("/ops-status", response_model=OpsStatus, summary="운영 상태 (S0 — P0 산출물)")
def ops_status() -> dict:
    with db.connect() as conn:
        v = db.q1(conn, "SELECT * FROM v_current_validity")
        stale = ops_repo.roi_stale_cameras(conn)
        expired = mrepo.expired_today(conn, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    return {"readiness": ops.readiness_payload(), "demo_on": bool(v and v["demo_on"]), "demo_end_at": v["demo_end_at"] if v else None,
            "roi_stale_cameras": stale, "expired_measurements_today": expired, "bis_calls_today": bis_calls_today()}


@router.get("/gate-events", response_model=List[GateEvent], summary="열린 게이트 이벤트 (C2). requested_only=true 면 S1 '받은 요청' (C7)")
def gate_events(subject_kind: Optional[str] = None, subject_id: Optional[str] = None, requested_only: bool = False) -> list:
    with db.connect() as conn:
        return ops_repo.open_gate_events(conn, subject_kind, subject_id, requested_only)


@router.get("/audit", summary="집계 기록 (FR-17, v_audit_record — 개인 정보 없음)")
def audit(since: Optional[str] = None, until: Optional[str] = None, limit: int = Query(default=200, le=2000)) -> list:
    with db.connect() as conn:
        return drepo.audit_records(conn, since, until, limit)


@router.get("/quality-metrics", summary="운영 지표 (P0 0.2)")
def quality_metrics() -> list:
    with db.connect() as conn:
        return ops_repo.latest_quality_metrics(conn)
