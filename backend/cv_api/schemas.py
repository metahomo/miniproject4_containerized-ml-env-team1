"""Pydantic 계약 — specs/001-crowd-vacancy-api/contracts/openapi.yaml 과 1:1.

요청 모델은 extra="forbid" (FR-02: 정의되지 않은 항목 포함 시 422). 필드명은 design/cv_ddl.sql 컬럼명과 같다.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

FORBID = ConfigDict(extra="forbid")


class CrowdingLevel(str, Enum):
    free = "free"
    normal = "normal"
    crowded = "crowded"
    uncertain = "uncertain"


class WarningCode(str, Enum):
    blur = "blur"
    low_light = "low_light"
    backlight = "backlight"
    low_confidence = "low_confidence"
    occlusion = "occlusion"
    roi_stale = "roi_stale"
    partial_coverage = "partial_coverage"
    unknown = "unknown"


class BasisType(str, Enum):
    measured = "measured"
    no_measurement = "no_measurement"
    unavailable = "unavailable"


class ReadinessState(str, Enum):
    ready = "ready"
    preparing = "preparing"
    unavailable = "unavailable"


# ---------------------------------------------------------------- 공통
class Warning(BaseModel):
    code: WarningCode
    detail: Optional[str] = None


class GateError(BaseModel):
    gate: str
    reason_code: str
    reason: str
    resolver_role: str
    allowed_spec: Optional[Dict[str, Any]] = None
    details: Optional[List[Dict[str, Any]]] = None
    gate_event_id: Optional[int] = None


class DetectorStatus(BaseModel):
    kind: str
    model: str
    loaded: bool
    load_seconds: Optional[float] = None
    warmed_up_at: Optional[str] = None
    last_infer_ms: Optional[int] = None
    note: Optional[str] = None


class Readiness(BaseModel):
    readiness: ReadinessState
    updated_at: str
    model_commit: Optional[str] = None
    detector: Optional[DetectorStatus] = None


# ---------------------------------------------------------------- 진단
class Versions(BaseModel):
    roi_id: int
    spec_id: Optional[int] = None
    threshold_policy_id: int
    model_commit: str


class Assessment(BaseModel):
    assessment_id: int
    camera_id: str
    captured_at: Optional[str] = None
    occupied_area_ratio: float = Field(ge=0, le=100)
    vacant_capacity_ratio: float = Field(ge=0, le=100)
    crowding_level: CrowdingLevel
    is_reference_only: bool
    person_count: int                                   # R22 셈에 든 인원 (인원 세기 기준 이상 · ROI 안)
    capacity: Optional[int] = None                      # R22 차량 전체 정원 — 없으면 혼잡도 산출 불가
    over_capacity: bool = False                         # R22 인원 > 정원 (점유율은 100% 에서 멈춤)
    remaining_persons: Optional[int] = None
    remaining_not_computable: bool
    mean_confidence: float = Field(ge=0, le=1)
    warnings: List[Warning]
    notice: str
    processed_at: str
    response_ms: Optional[int] = None
    versions: Versions


class BatchItem(BaseModel):
    seq: int
    status: str
    assessment: Optional[Assessment] = None
    reject: Optional[GateError] = None


class BatchConsistency(BaseModel):
    roi_id: int
    spec_id: Optional[int] = None
    threshold_policy_id: int
    frames_discarded: int
    audit_records: int


class BatchResult(BaseModel):
    batch_id: int
    camera_id: str
    items: List[BatchItem]
    consistency: BatchConsistency


class MeasurementStatus(BaseModel):
    vehicle_id: str
    vacant_ratio_agg: float
    crowding_level_agg: CrowdingLevel
    coverage_num: int
    coverage_den: int
    partial_coverage: bool
    persons_sum: Optional[int] = None                   # R22 합산 인원 (카메라별 최신 유효 실측 인원 합)
    capacity: Optional[int] = None                      # R22 차량 전체 정원
    measured_at: str
    expires_at: str
    applied_validity_minutes: int
    demo_mode: bool
    already_expired: bool = False


class MeasurementResult(BaseModel):
    assessment: Assessment
    measurement: MeasurementStatus


class MeasurementBatchItem(BaseModel):
    seq: int
    vehicle_id: str
    status: str
    result: Optional[MeasurementResult] = None
    reject: Optional[GateError] = None


class MeasurementBatchResponse(BaseModel):
    demo_mode: bool
    items: List[MeasurementBatchItem]


# ---------------------------------------------------------------- 후속 차량
class NextVehicleItem(BaseModel):
    vehicle_id: Optional[str] = None
    expected_arrival_at: Optional[str] = None
    basis_type: BasisType
    vacant_ratio: Optional[float] = None
    persons_sum: Optional[int] = None                   # R22 실측 인원 (카메라 합)
    capacity: Optional[int] = None                      # R22 차량 전체 정원 → "30 / 80명"
    crowding_level: Optional[CrowdingLevel] = None
    measured_at: Optional[str] = None
    coverage_num: Optional[int] = None
    coverage_den: Optional[int] = None
    warnings: List[Warning] = []


class VehicleStatus(NextVehicleItem):
    """T099 버스 번호로 상태 조회 — 그 버스의 최신 유효 실측. 실측이 없거나 만료면 no_measurement (추정하지 않음, BR-CV-13)."""
    expires_at: Optional[str] = None
    demo_mode: bool = False
    notice: str


class NextVehicleResponse(BaseModel):
    route_id: str
    stop_id: str
    place_kind: str
    vehicles: List[NextVehicleItem]
    applied_validity_minutes: int
    validity_source: str
    notice: str
    demo_mode: bool
    fetched_at: str
    source_status: str


# ---------------------------------------------------------------- 관리
class CameraCreate(BaseModel):
    model_config = FORBID
    camera_id: str
    place_type: str = Field(pattern="^(platform|bus_in|train_in)$")   # train_in = 열차 차내 (R21-D8 정정)
    route_id: Optional[str] = None
    stop_id: Optional[str] = None
    vehicle_type_id: Optional[str] = None


class CameraStatus(BaseModel):
    camera_id: str
    place_type: str
    route_id: Optional[str] = None
    stop_id: Optional[str] = None
    vehicle_type_id: Optional[str] = None
    has_roi: bool
    roi_stale: bool
    has_capacity: bool
    has_mapping: bool
    vehicle_id: Optional[str] = None
    capacity: Optional[int] = None          # 현재 정원 (제원 판본) — R22 혼잡도 분모. 관리자가 S2 에서 수정
    powered: bool = False                   # 카메라 전원 (S2b). off 면 진단 요청 거부 (G4 CAMERA_POWER_OFF)


class CameraPowerSet(BaseModel):
    model_config = FORBID
    on: bool


class CameraOperationUpdate(BaseModel):
    """S2b 운영 설정. 보낸 필드만 바꾼다. frame_source 를 빈 문자열로 보내면 자동 진단 소스를 지운다."""
    model_config = FORBID
    car_position: Optional[int] = Field(default=None, ge=1)
    frame_source: Optional[str] = Field(default=None, max_length=500)
    poll_interval_s: Optional[float] = Field(default=None, ge=1, le=3600)


class CameraPowerRow(BaseModel):
    """S2b 카메라 전원 관리 표 한 행. 모든 수치는 통계적 추정치."""
    camera_id: str
    mode: str                               # rail | bus
    place_type: str
    route_id: Optional[str] = None
    route_name: Optional[str] = None        # 호선 · 노선
    vehicle_id: Optional[str] = None        # 차량번호 (활성 매핑)
    car_position: Optional[int] = None      # 위치하는 칸 (열차)
    run_state: Optional[str] = None         # running | stopped | None(매핑 없음)
    capacity: Optional[int] = None
    persons: Optional[int] = None           # 최근 진단 인원
    density: Optional[float] = None         # 밀집도 % = 인원 ÷ 정원 (R22)
    crowding_level: Optional[str] = None
    last_diagnosed_at: Optional[str] = None
    powered: bool
    powered_at: Optional[str] = None
    operation: str                          # normal | offline | off
    frame_source: Optional[str] = None
    poll_interval_s: float
    last_error: Optional[str] = None


class RoiCreate(BaseModel):
    model_config = FORBID
    polygon: List[List[float]] = Field(min_length=3)
    roi_area_m2: Optional[float] = Field(default=None, gt=0)
    footprint_m2: Optional[float] = Field(default=None, gt=0)
    effective_from: str


class Roi(BaseModel):
    roi_id: int
    camera_id: str
    polygon: List[List[float]]
    vertex_count: int
    area: float
    roi_area_m2: Optional[float] = None
    footprint_m2: Optional[float] = None
    effective_from: str
    superseded_at: Optional[str] = None
    created_by: str


class VehicleTypeCreate(BaseModel):
    model_config = FORBID
    vehicle_type_id: str
    type_name: str


class VehicleSpecCreate(BaseModel):
    model_config = FORBID
    capacity: int = Field(ge=1)
    seat_count: Optional[int] = Field(default=None, ge=0)
    source: str
    effective_from: str


class VehicleSpec(VehicleSpecCreate):
    model_config = ConfigDict(extra="ignore")
    spec_id: int
    vehicle_type_id: str
    superseded_at: Optional[str] = None
    affected_cameras: int = 0


class DemoRemapRequest(BaseModel):
    """T097 시연 카메라를 지금 운행 중인 BIS 차량으로 다시 연결. 비우면 102번·충남대학교(홈플러스유성점 방면)·CAM-DEMO-01~03."""
    model_config = FORBID
    route_id: str = "30300037"
    stop_id: str = "30300037:42620"
    camera_ids: List[str] = Field(default_factory=lambda: ["CAM-DEMO-01", "CAM-DEMO-02", "CAM-DEMO-03"], min_length=1, max_length=10)


class ThresholdPolicyCreate(BaseModel):
    model_config = FORBID
    free_min_ratio: float = Field(ge=0, le=100)
    crowded_max_ratio: float = Field(ge=0, le=100)
    effective_from: str
    count_conf_min: Optional[float] = Field(default=None, ge=0.05, le=0.95)   # R22 인원 세기 기준 (비우면 기본 0.4)


class ThresholdPolicy(ThresholdPolicyCreate):
    model_config = ConfigDict(extra="ignore")
    policy_id: int
    created_at: str
    created_by: str
    is_current: bool = False
    is_scheduled: bool = False     # 적용 시작일이 아직 오지 않은 예약 판본


class RouteException(BaseModel):
    model_config = FORBID
    route_id: str
    minutes: int = Field(ge=1)


class ValidityPolicyCreate(BaseModel):
    model_config = FORBID
    factor: float = Field(gt=0)
    cap_minutes: int = Field(ge=1)
    default_minutes: int = Field(default=10, ge=1)
    window_minutes: int = Field(default=1, ge=1)
    route_exceptions: List[RouteException] = []
    demo_on: bool = False
    demo_end_at: Optional[str] = None


class ValidityPreviewRow(BaseModel):
    route_id: str
    route_name: Optional[str] = None      # 버스 번호 (예: 102번) — 화면 표시용
    headway_minutes: Optional[int] = None
    validity_minutes: int
    validity_source: str


class ValidityPolicyView(BaseModel):
    policy: Dict[str, Any]
    preview: List[ValidityPreviewRow]


class MappingCreate(BaseModel):
    model_config = FORBID
    camera_id: str
    vehicle_id: str
    vehicle_type_id: Optional[str] = None


class Mapping(BaseModel):
    map_id: int
    camera_id: str
    vehicle_id: str
    vehicle_type_id: Optional[str] = None
    verify_status: str
    verified_at: Optional[str] = None
    effective_from: str
    input_method: str
    sibling_cameras: List[str] = []


class CsvRow(BaseModel):
    row: int
    camera_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    status: str
    reason: Optional[str] = None


class CsvResult(BaseModel):
    saved: int
    rejected: int
    rows: List[CsvRow]


class FleetVehicle(BaseModel):
    vehicle_id: str
    route_id: str
    vehicle_type_id: Optional[str] = None


class FleetList(BaseModel):
    source_status: str
    fetched_at: Optional[str] = None
    vehicles: List[FleetVehicle]


class VerificationItemCreate(BaseModel):
    """수작업 정답 — 사람이 센 인원(manual_persons, 2026-09-30 사용자 요청)을 주면 서버가 그 프레임의 정원·등급 기준으로
    잔여 %·등급을 만든다(R22 와 같은 식). 잔여 %·등급을 직접 주는 이전 방식도 그대로 받는다."""
    model_config = FORBID
    seq: int
    manual_persons: Optional[int] = Field(default=None, ge=0, le=1000)
    manual_ratio: Optional[float] = Field(default=None, ge=0, le=100)
    manual_level: Optional[str] = Field(default=None, pattern="^(free|normal|crowded)$")


class VerificationRunCreate(BaseModel):
    model_config = FORBID
    batch_id: int
    items: List[VerificationItemCreate]


class VerificationRun(BaseModel):
    run_id: int
    batch_id: int
    ratio_match_rate: float
    level_match_rate: float
    verdict: str
    versions: Dict[str, Any]
    items: List[Dict[str, Any]]


class OpsStatus(BaseModel):
    readiness: Readiness
    demo_on: bool
    demo_end_at: Optional[str] = None
    roi_stale_cameras: List[str]
    expired_measurements_today: int
    bis_calls_today: int = 0          # 이 프로세스가 오늘(KST) 보낸 BIS API 호출 수 — 공공데이터포털 일일 한도 점검 (시연 예비 절차)


class GateEvent(BaseModel):
    event_id: int
    gate_code: str
    screen_code: str
    subject_kind: str
    subject_id: str
    occurred_at: str
    reason_code: str
    reason_text: Optional[str] = None
    resolver_role: str
    request_sent_at: Optional[str] = None
    request_sent_by: Optional[str] = None
    resolved_at: Optional[str] = None


class IntegrationCreate(BaseModel):
    model_config = FORBID
    endpoint_url: str


class Integration(BaseModel):
    integration_id: int
    instance_id: int
    registered_at: str
    registered_by: str
    test_request_id: Optional[int] = None
    first_response_ms: Optional[int] = None
    status: str
    reverted_reason: Optional[str] = None


class ApiGuideCatalogRow(BaseModel):
    feature_code: str
    uc_ref: str
    path: Optional[str] = None
    method: Optional[str] = None
    input_desc: str
    output_desc: str
    error_reasons: Optional[str] = None
    warning_types: Optional[str] = None


class ApiGuide(BaseModel):
    version: str
    updated_at: str
    readiness: Readiness
    catalog: List[ApiGuideCatalogRow]
    guideline_md: str
    manual_md: str
    model_card_md: str
    openapi_url: str


class DetectorPreloadResult(BaseModel):
    kind: str
    model: str
    action: str
    seconds: float
    done_reason: Optional[str] = None


# ---------------------------------------------------------------- 계정·역할·API 키 (RBAC, T107)
class SignupRequest(BaseModel):
    """회원가입 — 바로 일반 사용자로 로그인 (API 키는 따로 신청 → 운영 관리자 승인, T108)."""
    model_config = FORBID
    login_id: str = Field(min_length=3, max_length=40)
    name: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=8, max_length=128)
    org: Optional[str] = Field(default=None, max_length=80)
    email: Optional[str] = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    model_config = FORBID
    login_id: str = Field(max_length=40)
    password: str = Field(max_length=128)


class AccountCreate(SignupRequest):
    """운영 관리자가 직접 만드는 계정 (관제 담당자·운영 관리자 등) — 바로 사용 가능."""
    role: str = Field(pattern="^(admin|controller|user)$")


class AccountUpdate(BaseModel):
    model_config = FORBID
    role: Optional[str] = Field(default=None, pattern="^(admin|controller|user)$")
    status: Optional[str] = Field(default=None, pattern="^(pending|active|disabled)$")


class RbacUpdate(BaseModel):
    """운영 관리자: 권한 매트릭스(S10) 저장 — 권한마다 허용할 역할 전체. 빠진 권한은 그대로 둔다."""
    model_config = FORBID
    permissions: Dict[str, List[str]] = Field(description="권한 → 허용 역할 목록 (예: {\"measure\": [\"integration\", \"controller\", \"admin\"]})")


class KeyReview(BaseModel):
    """운영 관리자: API 키 승인·반려."""
    model_config = FORBID
    status: str = Field(pattern="^(active|rejected)$", description="active = 승인, rejected = 반려")


class KeyCreate(BaseModel):
    model_config = FORBID
    name: str = Field(min_length=1, max_length=40, description="연계 시스템 이름 (예: 정류장 전광판)")
