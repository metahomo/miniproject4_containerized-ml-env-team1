# Data Model — 001-crowd-vacancy-api

**작성일**: 2026-09-28 · **단계**: Phase 1 · **정본**: `design/SD_03_데이터베이스설계서_잔여공간진단서비스.md` + `design/cv_ddl.sql`(SQLite 3종 검증 완료)

이 문서는 SD_03 을 구현 관점으로 요약하고, 계획 단계 결정(research.md)으로 바뀐 부분만 적는다. 컬럼 상세·제약·뷰 정의는 정본을 따른다.

---

## 1. 영역과 엔티티 (29 테이블 · 14 뷰)

| 영역 | 엔티티 | 핵심 관계 | 쓰기 주체 |
|:--:|---|---|---|
| A 기준 정보 | route, stop, vehicle_type, camera, roi(판본), vehicle_spec(판본), camera_vehicle_map(판본) | camera ─< roi · vehicle_type ─< vehicle_spec · camera ─< camera_vehicle_map(활성 1) | 운영 관리자 |
| B 정책 | threshold_policy(적용 시작일), validity_policy(판본·시연 모드), validity_route_exception | validity_policy ─< exception | 운영 관리자 |
| F 외부 스냅샷 | route_headway, fleet_vehicle, arrival_snapshot | route ─< 전부 | 시스템(연계 모듈) |
| C 진단 | batch, diagnosis_request, assessment, assessment_warning, verification_run, verification_item, quality_metric | request ─ assessment(1:0..1) ─< warning · batch ─< request · run ─< item | 연계·웹서비스·운영 관리자 |
| D 실측 | camera_measurement(활성 1/카메라), vehicle_measurement(활성 1/차량), vehicle_measurement_component | assessment ─ camera_measurement · vm ─< component >─ cm | 시스템 |
| E 운영·게이트 | model_package, server_instance, integration, gate_event | model_package ─< server_instance ─< integration | 운영 관리자·시스템 |
| G 안내 | api_guide, api_endpoint | guide ─< endpoint | 운영 관리자·개발 |

## 2. 원천 Key Entities → 테이블

| Key Entity | 테이블 | 비고 |
|---|---|---|
| Camera | camera + camera_vehicle_map | 연결된 차량 식별자·이력은 매핑 판본 |
| ROI | roi | 판본, `area` 고정 저장 |
| VehicleSpec | vehicle_spec | 판본, 출처 필수 |
| Frame | diagnosis_request | 메타만. 이미지 컬럼 없음(FR-11) |
| Assessment | assessment + assessment_warning | `vacant_capacity_ratio` 생성 컬럼 |
| Warning | assessment_warning.warning_code | 7종 + unknown |
| ThresholdPolicy | threshold_policy | |
| ValidityPolicy | validity_policy + validity_route_exception | 시연 모드 포함 |
| VehicleMeasurement | vehicle_measurement + component (+ camera_measurement) | 합산값 고정 저장 |
| Trip/Arrival | arrival_snapshot | 조회마다 스냅샷 |
| NextVehicleEstimate | **뷰** v_next_vehicle | 저장하지 않음 |
| AuditRecord | **뷰** v_audit_record | 저장하지 않음 |

## 3. 검증 규칙 (요구사항 → 제약)

| 요구 | 제약 | 위치 |
|---|---|---|
| FR-02 규격 외 반려 | Pydantic 스키마(extra=forbid, 형식·해상도·용량 — research R4) + `chk_reject_reason` | 앱 + DB |
| FR-03/04/05 ROI 내부·통합 면적·0~100% | `assessment.roi_id` NOT NULL, `chk_occupied_range`, GENERATED vacant | DB |
| FR-06 3단계 등급·경계 조정 | `chk_threshold_order/range`, 등급 값 집합 | DB |
| FR-07 정원 없으면 산출 불가 | `assessment.spec_id` NULL → `v_assessment.remaining_not_computable` | 뷰 |
| FR-08/09 경고·판독 불확실 | `chk_low_confidence_uncertain`, `trg_warning_uncertain` | DB |
| FR-11 원본 미보관 | 컬럼 부재 | 스키마 |
| FR-13/13a 실측 없음·추정 금지 | `v_next_vehicle.basis_type` 3값, 비실측 시 NULL | 뷰 |
| FR-13b 배차 간격 기반 유효 시간 | `v_route_validity_minutes` 단일 산출 | 뷰 |
| FR-13c 1카메라 1차량, 존재 검증 | `uq_map_active_camera`, `verify_status` | DB |
| FR-13d 시연 모드 | `chk_demo_end`, `chk_demo_measured`, `demo_flag` | DB + 뷰 |
| FR-13e 인원 합 ÷ 정원 합산(R22, 이전 면적 가중)·커버리지 | `chk_coverage`, component, `partial_coverage` | DB + 뷰 |
| FR-15 이력 | 판본 테이블 `superseded_at` | DB |
| FR-16 무차등 | caller 분기 컬럼 없음 | 스키마 |
| FR-17 집계 기록 | `v_audit_record` | 뷰 |
| FR-19 준비 상태 | `chk_ready_requires_warmup`, `v_readiness` | DB + 뷰 |

## 4. 상태 전이

### 4-1 diagnosis_request.status
`accepted` ↔ 없음 · `rejected`(G2). 수락 후 `assessment` 유무로 성공/실패(G5) 구분. `responded_at` 기록으로 종료.

### 4-2 assessment.crowding_level
`free | normal | crowded`(확정) · `uncertain`(G6 출력 차단). 확정 → 불확실 전이는 없다(행 불변). 재제출은 새 요청.

### 4-3 camera_vehicle_map.verify_status
`unverified` → `verified`(재검증 배치, R11) · 어느 쪽이든 → `released`(해제, `released_at`). 활성(`released_at IS NULL`)은 카메라당 1개.

### 4-4 camera_measurement / vehicle_measurement
`active`(superseded_at NULL) → `superseded`(새 실측). 유효성은 상태가 아니라 `v_vehicle_measurement_status.is_valid`(만료·시연) 판정.

### 4-5 validity_policy 시연 모드
`demo_on=0` → `1 + demo_end_at`(8.2) → `0`(8.5 수동 또는 P0 0.4 자동 — 새 판본). 

### 4-6 server_instance.readiness
`preparing` → `ready`(웜업·계약 확인) → `unavailable`(P0 0.5) → `preparing`(재기동). `ready` 는 CHECK 로 웜업 전 불가.

### 4-7 api_guide.status
`draft` → `verified` → `published` · 계약 변경 → `mismatch` → `draft`.

### 4-8 gate_event
발생(`occurred_at`) → [요청 전송(`request_sent_at`, 타인 해제만)] → 해제(`resolved_at`). G3 은 R9 로 해제 주체가 운영 관리자로 확정되므로 `resolver_role='operator'`.

## 5. 계획 단계에서 정본과 달라진 것

| 항목 | SD_03 | 계획 결정 | 반영 |
|---|---|---|---|
| G3 해제 주체 | `undefined` | 운영 관리자(R9, `POST /v1/admin/cameras`) | `gate_event` 삽입 시 `operator` 사용. `chk_gate_undefined` 는 유지(값이 안 쓰일 뿐) |
| `assessment.model_crowding_level` | 모델 원출력 보존 | 모델이 등급을 내지 않음(R3) → 항상 NULL | 컬럼 유지, 삽입 안 함 |
| `model_package.contract_check_result` | ok/mismatch/adapter | 확정 모델 `MaxTheTechy/yolo`(YOLOv8n) 실물 확인 결과 `adapter`(R3) | 시드 값 |
| `expires_at` 재계산 | 미결 | 재계산 안 함(R10) | 배치 없음 |
| `verify_status='unverified'` | 허용 여부 미결 | 허용(R11) | 재검증 배치 추가 |
| 보존 기간 | 미결 | 설정값 NULL(R17) | 폐기 배치는 값 있을 때만 |
| `roi` 컬럼 | polygon·vertex_count·area(픽셀) | 발 위치 방식(R20)을 위해 `roi_area_m2 REAL`(실제 바닥 면적), `footprint_m2 REAL`(카메라별 보정, NULL 이면 설정 기본값) 추가 | `cv_ddl.sql`·SD_03 갱신은 T036·T074 |
| `assessment` 컬럼 | 4필드 + 신뢰도 | `person_count INTEGER`(ROI 안 발 위치 인원) 추가 — 정원 대비 인원수 병기(R20) | 동상 |

## 6. 접근 계층

- `cv_api/db.py`: SQLAlchemy Core 엔진 + `cv_ddl.sql` 실행(기동 시 멱등 적용). SQLite/PostgreSQL 은 URL 로 전환. PostgreSQL 용 DDL 변환본은 `cv_ddl.postgres.sql`.
- 리포지토리 모듈은 영역별: `repo/reference.py`(A), `repo/policy.py`(B), `repo/external.py`(F), `repo/diagnosis.py`(C), `repo/measurement.py`(D), `repo/ops.py`(E), `repo/guide.py`(G).
- 게이트 판정은 뷰만 읽는다: `v_readiness`, `v_camera_readiness`, `v_vehicle_measurement_status`, `v_route_validity_minutes`.
