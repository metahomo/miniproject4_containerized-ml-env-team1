"""P9 API 활용 안내 — 카탈로그(UC15 표, openapi 와 대조 G17), 가이드라인·매뉴얼·모델 카드(마크다운 파일)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from .. import db
from ..repo import ops as ops_repo
from ..settings import get_settings
from . import ops

GUIDE_DIR = Path(__file__).resolve().parent.parent / "guide"
GUIDE_VERSION = "v1.3"   # 2026-09-29: 로그인 필수·키 승인(T108), R22 인원 ÷ 정원, 공개 주소 /API, 이용자 조회·로그인, 웹 변환, 실제 BIS(102번), 카탈로그 = 전체 엔드포인트

_UC1_ERR = "401/403 키(G1), 422 규격 외(G2), 404 카메라 미등록(G3), 409 ROI 미등록(G4), 503 준비 중·모델 불가(G0·G5)"
_WARN = "blur low_light backlight low_confidence occlusion roi_stale unknown(model_unavailable·capacity_missing)"

# 기능 단위 카탈로그 (UC15). path 에 쉼표로 여러 경로 — G17 이 전부 실제 계약(openapi)에 있는지 대조한다.
# 연계 개발자용(호출 키) → 웹 화면용 → 운영 관리자용(관리자 키) 순.
CATALOG: List[Dict[str, Any]] = [
    # ---- 연계 시스템·이용자 (X-API-Key) ----
    {"feature_code": "readiness", "uc_ref": "UC9", "path": "/v1/readiness", "method": "GET",
     "input_desc": "— (키 없이도 된다)", "output_desc": "ready / preparing / unavailable + 검출기 적재 상태·소요 시간", "error_reasons": "—", "warning_types": "—"},
    {"feature_code": "diagnose", "uc_ref": "UC1 UC13", "path": "/v1/diagnose", "method": "POST",
     "input_desc": "multipart: camera_id, frame(JPEG/PNG 1장, 짧은 변 240~긴 변 4096px, 10MB 이하), captured_at(선택)",
     "output_desc": "Assessment — person_count(현재 인원) / capacity(차량 전체 정원), occupied_area_ratio(혼잡 % = 인원÷정원, 100 상한), over_capacity(정원 초과), vacant_capacity_ratio(여유 %), crowding_level, remaining_persons, mean_confidence, warnings, notice, versions",
     "error_reasons": _UC1_ERR + ". 정원 미등록이면 200 + uncertain(G7, 인원만)", "warning_types": _WARN},
    {"feature_code": "next_vehicle", "uc_ref": "UC2", "path": "/v1/next-vehicle", "method": "GET",
     "input_desc": "route_id(BIS 노선 코드, 102번=30300037), stop_id(노선코드:정류소ID, 충남대학교=30300037:42620·42600), limit",
     "output_desc": "NextVehicleEstimate — 차량별 도착 예정 시각(UTC), basis_type(measured/no_measurement/unavailable), 실측이면 persons_sum / capacity 명·잔여 %·등급·커버리지, 적용 유효 시간, 시연 표시",
     "error_reasons": "401/403 키(G1), 404 노선·정류장 없음(G11), 503 준비 중. BIS 장애는 200 + unavailable(G12)", "warning_types": "partial_coverage + 실측의 경고"},
    {"feature_code": "measurement", "uc_ref": "UC10", "path": "/v1/measurements", "method": "POST",
     "input_desc": "multipart: vehicle_id(BIS 차량 번호), camera_id(차내 카메라), frame, captured_at(선택)",
     "output_desc": "Assessment + 실측 등록 상태 — persons_sum(카메라별 인원 합) / capacity, vacant_ratio_agg, 등급, 커버리지, 만료 시각, 시연",
     "error_reasons": "409 매핑 없음·차내 카메라 아님(G10), 그 외 diagnose 와 같다", "warning_types": "diagnose 와 같다 + partial_coverage"},
    {"feature_code": "lookup", "uc_ref": "UC2 (이용자 — 이름으로 찾기)", "method": "GET", "path": "/v1/reference/routes, /v1/reference/stops, /v1/reference/stops/{stop_id}/routes",
     "input_desc": "routes: q(노선 번호, 예 102) / stops: route_id 또는 q(정류장 이름, 예 충남대), limit / stops/{stop_id}/routes: 정류장 하나",
     "output_desc": "노선 route_id·route_no(«102번 · 간선 · 수통골기점지↔대전역/역전시장» — 번호가 같은 노선을 유형·기점↔반환점으로 구분) / 정류장 stop_id·stop_name(같은 이름 양방향은 '(다음 정류장 방면)')·노선 / 그 정류장에 서는 노선만(노선별 stop_id) — next-vehicle 에 넣을 코드를 이름으로 찾는다",
     "error_reasons": "401/403 키(G1), 422 route_id·q 둘 다 없음, 404 정류장 없음(G3)", "warning_types": "—"},
    {"feature_code": "vehicle_status", "uc_ref": "UC2 (버스 번호로 조회)", "path": "/v1/vehicles/{vehicle_id}", "method": "GET",
     "input_desc": "vehicle_id — BIS 차량 번호(예 대전75자9022)",
     "output_desc": "그 버스의 최신 유효 실측: persons_sum / capacity 명, vacant_ratio, crowding_level, 측정·만료 시각, 커버리지. 실측이 없거나 만료면 no_measurement(추정 없음)",
     "error_reasons": "401/403 키(G1)", "warning_types": "실측의 경고 + partial_coverage"},
    {"feature_code": "reference", "uc_ref": "UC1 UC2 (이용자 조회)", "method": "GET",
     "path": "/v1/reference/cameras, /v1/reference/cameras/{camera_id}, /v1/reference/cameras/{camera_id}/roi, /v1/reference/threshold, /v1/reference/ops-status",
     "input_desc": "— (보기 전용)", "output_desc": "카메라 목록·현재 정원, 현재 ROI 다각형, 현재 등급 기준·인원 세기 기준, 운영 상태 요약(시연 모드·ROI 검증 필요·만료 실측)",
     "error_reasons": "401/403 키(G1), 404 카메라·ROI 없음", "warning_types": "—"},
    {"feature_code": "gate_request", "uc_ref": "C7 (게이트 해제 요청)", "path": "/v1/gate-events/{event_id}/request", "method": "POST",
     "input_desc": "event_id — 차단 응답의 gate_event_id", "output_desc": "요청 보낸 시각. 운영 관리자 S1 '받은 요청'에 나타난다",
     "error_reasons": "404 이벤트 없음", "warning_types": "—"},
    {"feature_code": "auth_whoami", "uc_ref": "G1 (호출 주체 확인)", "path": "/v1/auth/whoami", "method": "GET",
     "input_desc": "X-API-Key 또는 X-Admin-Key", "output_desc": "caller_id, role(user·integration·webservice·controller·admin)·role_label — 웹 «관리자 키로» 로그인이 키 확인에 쓴다",
     "error_reasons": "401 키 없음, 403 키 불일치", "warning_types": "—"},
    {"feature_code": "auth_account", "uc_ref": "G1 RBAC (회원가입·로그인)", "method": None,
     "path": "/v1/auth/signup, /v1/auth/login, /v1/auth/logout, /v1/auth/me, /v1/auth/roles",
     "input_desc": "가입: login_id·name·password(8자+)·org / 로그인: login_id·password (키 없이)",
     "output_desc": "가입 = 바로 일반 사용자 / 로그인 = Bearer 토큰(12시간)·계정 / 역할·권한 표(유스케이스 액터 기준)",
     "error_reasons": "422 입력 검증·아이디 중복, 401 LOGIN_FAILED, 403 ACCOUNT_DISABLED(정지)", "warning_types": "—"},
    {"feature_code": "my_keys", "uc_ref": "G1 RBAC (일반 사용자 키 신청)", "method": None, "path": "/v1/auth/keys, /v1/auth/keys/{key_id}",
     "input_desc": "로그인 토큰(일반 사용자·운영 관리자). 신청: name(연계 시스템 이름)",
     "output_desc": "신청 = cvk_… 키 원문(이때 한 번만)·status pending — 운영 관리자 승인 뒤 사용 / 목록 = 앞자리·상태·마지막 사용 / 폐기 = 즉시 거부",
     "error_reasons": "401 로그인 필요, 403 역할 없음, 키 호출 403 KEY_PENDING(승인 전)·KEY_REJECTED", "warning_types": "—"},
    {"feature_code": "api_guide", "uc_ref": "UC15", "path": "/v1/api-guide", "method": "GET", "input_desc": "—",
     "output_desc": "카탈로그(이 표), 가이드라인, 매뉴얼, 모델 카드, 준비 상태", "error_reasons": "401/403 키(G1)", "warning_types": "—"},
    # ---- 본 웹서비스 화면용 (X-API-Key) — 규격 밖 사진·영상 변환 ----
    {"feature_code": "web_media", "uc_ref": "UC1 UC5 UC10 (웹 화면)", "method": "POST",
     "path": "/v1/web/diagnose, /v1/web/diagnose-video, /v1/web/measurements",
     "input_desc": "사진(HEIC·WebP 등 포함, 50MB 이하) 또는 영상(500MB 이하, interval_s·at_s) — 규격(JPEG, 긴 변 1920px 이하)으로 바꿔 진단",
     "output_desc": "diagnose·measurements 응답 + normalization(무엇을 바꿨는지). 영상은 시각별 결과·평활값·요약",
     "error_reasons": "422 짧은 변 240px 미만(키우지 않음)·읽을 수 없음, 그 외 diagnose 와 같다", "warning_types": "diagnose 와 같다"},
    {"feature_code": "web_samples", "uc_ref": "UC15 (웹 화면 샘플)", "path": "/v1/web/samples, /v1/web/samples/{file}", "method": "GET",
     "input_desc": "file — 목록에 있는 파일만", "output_desc": "시연용 자유 이용 샘플 사진·영상 목록과 파일", "error_reasons": "404 목록에 없는 파일", "warning_types": "—"},
    # ---- 운영 관리자 (X-Admin-Key) ----
    {"feature_code": "diagnose_batch", "uc_ref": "UC4", "path": "/v1/diagnose/batch", "method": "POST",
     "input_desc": "camera_id, frames(20장 이하, 순서)", "output_desc": "프레임별 Assessment (제출 순서) + 정합성", "error_reasons": "관리자 키. 422 장수 한도·규격 외, 404, 409, 503", "warning_types": "diagnose 와 같다"},
    {"feature_code": "measurement_batch", "uc_ref": "UC10 A4", "path": "/v1/measurements/batch", "method": "POST",
     "input_desc": "items(seq, vehicle_id, camera_id, frame)", "output_desc": "항목별 결과, demo_mode", "error_reasons": "관리자 키. 시연 모드 꺼짐이면 즉시 만료(G14)", "warning_types": "diagnose 와 같다"},
    {"feature_code": "admin_reference", "uc_ref": "UC6 UC7 UC12 (+카메라 등록)", "method": None,
     "path": "/v1/admin/cameras, /v1/admin/cameras/{camera_id}, /v1/admin/cameras/{camera_id}/roi, /v1/admin/vehicle-types/{vehicle_type_id}/spec, /v1/admin/fleet",
     "input_desc": "카메라 등록(POST)·조회, ROI 다각형 저장(POST, «전체 화면» 0,0~4096,4096 가능), 차량 전체 정원(POST), 운행 차량 자동완성(GET)", "output_desc": "저장 결과·판본·이력",
     "error_reasons": "관리자 키(G1). 422 값 검증(G8)·존재(G9)", "warning_types": "—"},
    {"feature_code": "admin_camera_power", "uc_ref": "S2b (카메라 전원 관리)", "method": None,
     "path": "/v1/admin/camera-power, /v1/admin/cameras/{camera_id}/power, /v1/admin/cameras/{camera_id}/operation",
     "input_desc": "전원 표 조회(GET), 켜기·끄기(POST on=true/false), 칸·프레임 소스(스냅샷 URL 또는 sample:<파일>)·진단 주기 초(PATCH)",
     "output_desc": "호선·차량번호·칸·운행 상태·정원·현재 인원·밀집도(%)·동작여부(정상/오프라인/꺼짐)",
     "error_reasons": "관리자 키(G1). 404 카메라 없음(G3). 422 프레임 소스 형식(G8). 꺼진 카메라의 진단 요청은 409 CAMERA_POWER_OFF(G4)", "warning_types": "—"},
    {"feature_code": "admin_mapping", "uc_ref": "UC12", "method": None, "path": "/v1/admin/mappings, /v1/admin/mappings/{map_id}, /v1/admin/mappings/csv",
     "input_desc": "카메라↔BIS 차량 번호 매핑(POST)·목록(GET)·해제(DELETE)·CSV 일괄(POST)", "output_desc": "매핑·검증 상태(verified/unverified), 같은 차량의 다른 카메라",
     "error_reasons": "관리자 키(G1). 422 운행 정보에 없는 차량·중복(G9)", "warning_types": "—"},
    {"feature_code": "admin_policy", "uc_ref": "UC8 UC11", "path": "/v1/admin/policies/threshold, /v1/admin/policies/validity", "method": None,
     "input_desc": "등급 경계(여유 하한·혼잡 상한)·인원 세기 기준(0.05~0.95) / 유효 시간 규칙·시연 모드 (GET 조회 / POST 저장)", "output_desc": "정책 판본, 노선별 유효 시간 미리보기",
     "error_reasons": "관리자 키(G1). 422 값 검증·과거 적용일(G8)", "warning_types": "—"},
    {"feature_code": "admin_verification", "uc_ref": "UC4 (SC-01·02)", "path": "/v1/admin/verification-runs", "method": "POST",
     "input_desc": "batch_id, 항목별 사람이 센 인원(manual_persons — 정원·등급 기준으로 잔여 %·등급을 만든다) 또는 수작업 잔여 %·등급(manual_ratio, manual_level)", "output_desc": "잔여 비율 ±10%p 일치율·등급 일치율·판정(pass/fail)",
     "error_reasons": "관리자 키(G1)", "warning_types": "—"},
    {"feature_code": "admin_ops", "uc_ref": "UC9 FR-17 (운영 상태)", "method": "GET",
     "path": "/v1/admin/ops-status, /v1/admin/gate-events, /v1/admin/audit, /v1/admin/quality-metrics",
     "input_desc": "— / requested_only·subject 필터", "output_desc": "운영 상태, 열린 게이트·받은 요청, 집계 기록(개인 정보 없음), 시간대·조도별 신뢰도 지표",
     "error_reasons": "관리자 키(G1)", "warning_types": "—"},
    {"feature_code": "admin_model", "uc_ref": "UC14 (서버·모델·연동)", "method": None,
     "path": "/v1/admin/detector, /v1/admin/detector/preload, /v1/admin/integrations, /v1/admin/integrations/{integration_id}/test",
     "input_desc": "검출기 상태 조회·재적재, 웹서비스 연동 등록·시험 호출", "output_desc": "적재 상태·소요 시간, 연동 등록·첫 응답 시간",
     "error_reasons": "관리자 키(G1), 503 준비 전 연동(G0)", "warning_types": "—"},
    {"feature_code": "admin_accounts", "uc_ref": "G1 RBAC (계정·키 관리)", "method": None,
     "path": "/v1/admin/accounts, /v1/admin/accounts/{account_id}, /v1/admin/accounts/{account_id}/changes, /v1/admin/api-keys, /v1/admin/api-keys/{key_id}, /v1/admin/rbac",
     "input_desc": "계정 목록(status 필터)·만들기(role)·정지(disabled)·역할 변경 / 키 목록(status=pending 승인 대기)·승인(active)·반려(rejected)·폐기 / 권한 매트릭스 보기·저장(권한 → 허용 역할)",
     "output_desc": "계정(비밀번호 없음)·사용 중 키 수 / 키 앞자리·소유자·상태·마지막 사용 / 역할×기능 유효 권한·기본값·잠긴 칸",
     "error_reasons": "운영 관리자만(G1), 404 없음", "warning_types": "—"},
    {"feature_code": "admin_demo", "uc_ref": "UC10 UC12 (시연 S8)", "path": "/v1/admin/demo/bis-remap", "method": "POST",
     "input_desc": "route_id(기본 30300037), stop_id(기본 30300037:42620), camera_ids(기본 CAM-DEMO-01~03)",
     "output_desc": "카메라별 이전/지금 차량·도착 예정 시각·처리(kept/changed/unchanged) — 곧 도착할 BIS 차량으로 다시 연결",
     "error_reasons": "관리자 키(G1), 404 카메라·정류장 없음. 도착 정보 없음·BIS 장애면 바꾸지 않음", "warning_types": "—"},
]


_ORDER = {r["feature_code"]: i for i, r in enumerate(CATALOG)}


def _read(name: str) -> str:
    p = GUIDE_DIR / name
    return p.read_text(encoding="utf-8") if p.exists() else f"({name} 없음)"


def contract_hash(openapi: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(sorted(openapi.get("paths", {}).keys())).encode()).hexdigest()


def verify_and_publish(openapi: Dict[str, Any], by: str = "system") -> Dict[str, Any]:
    """G17: 카탈로그 경로가 실제 openapi 에 전부 있어야 published. 아니면 mismatch."""
    paths = set(openapi.get("paths", {}).keys())
    missing = []
    for row in CATALOG:
        for p in [x.strip() for x in row["path"].split(",")]:
            if p not in paths:
                missing.append(p)
    status = "published" if not missing else "mismatch"
    now = db.now_iso()
    with db.connect() as conn:
        gid = ops_repo.upsert_guide(conn, GUIDE_VERSION, status, contract_hash(openapi), now, by)
        ops_repo.replace_endpoints(conn, gid, [{k: v for k, v in r.items()} for r in CATALOG])
    return {"guide_id": gid, "status": status, "missing": missing}


def payload() -> Dict[str, Any]:
    with db.connect() as conn:
        g = ops_repo.current_guide(conn)
        rows = ops_repo.endpoints(conn, g["guide_id"]) if g else []
    return {
        "version": g["version"] if g else GUIDE_VERSION, "updated_at": g["updated_at"] if g else db.now_iso(),
        "readiness": ops.readiness_payload(),
        "catalog": [{k: r.get(k) for k in ("feature_code", "uc_ref", "path", "method", "input_desc", "output_desc", "error_reasons", "warning_types")}
                    for r in sorted(rows or CATALOG, key=lambda r: _ORDER.get(r["feature_code"], len(_ORDER)))],   # 연계 → 웹 → 관리 순
        "guideline_md": _read("guideline.md"), "manual_md": _read("manual.md"), "model_card_md": _read("model_card.md"),
        "openapi_url": "/openapi.json",
    }
