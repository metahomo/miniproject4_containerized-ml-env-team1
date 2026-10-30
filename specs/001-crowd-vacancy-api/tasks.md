# Tasks: 대전 대중교통 비식별 군중 밀집도·잔여 공간 진단 서비스

**Feature**: `001-crowd-vacancy-api` · **Date**: 2026-09-28
**Input**: `plan.md`(구조·스택), `spec.md` v1.1(S1~S7, AS1~AS7, Clarifications 3차), `data-model.md`, `contracts/openapi.yaml`(경로 21·오퍼레이션 25), `research.md`(R1~R19), `quickstart.md`, `Intent-Tasks.md`(대시보드 레이아웃 패턴, Claude Code 스킬), `design/`(UC_00~15, SD_01 P0~P9·G0~G17, SD_02 S0~S9·C1~C9, SD_03 + `cv_ddl.sql`, style-guide)

**테스트 포함 이유**: NFR-07 "입력 검증, 규격 외 반려, 일괄 처리 정합성, 경고 동봉 규칙은 배포 전 자동 검증으로 확인된다"와 Intent 의 `test_app.py`·`bench.py`. 해당 규칙은 테스트를 먼저 쓴다(TDD). 그 외 테스트는 스토리별 계약·게이트 검증이다.

**Intent-Tasks 반영**: 웹서비스 껍데기는 **대시보드 레이아웃**(좌측 접이식 사이드바에 S0~S9, 상단 헤더에 준비 칩·시연 칩·검색, 메인 영역은 카드·표) 으로 한다. SD_02 의 두 줄 내비(C1 global-nav + sub-nav)는 사이드바 + 헤더로 대체하고, **진행 레일(C1)은 메인 영역 맨 위 행**에 유지한다. 시각 값은 `design/style-guide.html` 토큰. 컴포넌트 구현 시 `frontend-design` 스킬을 쓴다.

**형식**: `- [ ] T### [P] [US#] 설명 — 파일 경로`. `[x]` = 2026-09-28 구현 완료(체크포인트 검증 포함). `[P]` = 다른 파일이라 병렬 가능. `[US#]` = 스토리 라벨.

---

## 사용자 스토리 (spec.md 시나리오 → 우선순위)

| 스토리 | 원천 시나리오 | 우선순위 | 근거 | 독립 검증 기준 |
|:--:|---|:--:|---|---|
| US1 | S1 현재 프레임 진단 + S3 정직한 실패 + S6 비정상 요청 거부 | P1 | UC1·3·5·9·13·14 High. 서비스의 본류(SD_01 P5·P1) | 시드 데이터로 카메라·ROI·정원을 넣은 뒤 `POST /v1/diagnose` 가 AS1(정상)·AS3(판독 불확실)·AS5(422 반려)·AS6(원본 미보관)·AS7(첫 요청 지연)을 통과 |
| US2 | S5 관심영역·차량 제원 관리 (+ 카메라 등록, 등급 기준, 유효 시간·시연 모드, 식별자 매핑) | P1 | UC6·12 High, UC7·8·11 Medium. G3·G4·G7·G8·G9·G10 의 해제 경로 | 관리자 키로 S2·S3 화면과 `/v1/admin/*` 로 등록·판본·이력이 되고, G8·G9 위반이 422 로 거부 |
| US3 | S2 후속 차량 여유도 조회 (실측 등록·합산·유효 시간 판정) | P1 | UC2·10 High. Intent 미션 "다음 차가 여유로운가" | 실측 등록 후 `GET /v1/next-vehicle` 이 AS2(실측)·AS2-b(실측 없음)·AS2-c(판독 불확실 실측)·AS2-e(합산·커버리지)·E9(조회 불가) 를 반환 |
| US4 | S7 시연 준비 (사전 제공 프레임 등록·시연 모드) | P2 | UC10 A4·UC11 A2. 발표 시연의 성립 조건 | `scripts/demo_prepare.py` 한 번으로 P1~P6 이 끝나고 S8 레일이 8.1→8.5 순서를 강제, AS2-d 통과 |
| US5 | S4 사전 녹화 프레임 일괄 검증 (정확도 판정) | P2 | UC4 Medium. SC-01·02 측정 수단 | 10장 일괄이 AS4(순서·단건 동일) 를 통과하고 SC-01·02 판정이 나온다 |
| US6 | API 활용 안내·웹서비스 연동 확인 | P2 | UC15·UC14 5~6단계. 추가 원천 4항 | S9 가 카탈로그·가이드라인·매뉴얼·모델 카드를 보이고, `openapi.json` 과 카탈로그가 일치(G17) |
| US7 | 운영 상시 (준비 감시·시연 자동 해제·지표·운영 상태 화면) | P3 | SD_01 P0, S0 | 시연 종료 예정 시각 경과 시 자동 해제, 준비 불가 전환 시 G0 닫힘, S0 운영 상태 표시 |

---

## Phase 1: Setup (프로젝트 초기화)

- [x] T001 백엔드 패키지 골격 생성 — `backend/pyproject.toml`(name cv-api, deps: fastapi, uvicorn[standard], pydantic>=2, sqlalchemy>=2, ultralytics, torch, opencv-python-headless, numpy, shapely, python-multipart, httpx; extras dev: pytest, pytest-asyncio), `backend/cv_api/__init__.py`, `backend/README.md`
- [x] T002 [P] 설정 모듈 — `backend/cv_api/settings.py`: research R4·R5·R6 기본값(IMAGE_FORMATS, IMAGE_MIN/MAX_SIDE, IMAGE_MAX_BYTES, BATCH_MAX_FRAMES, BLUR_LAPLACIAN_MIN, LOW_LIGHT_MEAN_MAX, BACKLIGHT_*, CONFIDENCE_MIN=0.6, OCCLUSION_IOU=0.5, OCCLUSION_RATIO=0.3, INFER_TIMEOUT_S=5, API_KEYS, ADMIN_KEYS, DATABASE_URL, MODEL_WEIGHTS, EXTERNAL_PROVIDER, RETENTION_DAYS=None, NOTICE_TEXT) 를 pydantic-settings 로 `.env` 에서 읽음 + `backend/.env.example`
- [x] T003 [P] 프론트엔드 골격 — `frontend/package.json`(react 18, typescript 5, vite 5, react-router), `frontend/vite.config.ts`, `frontend/.env.example`(VITE_API_BASE, VITE_API_KEY, VITE_ADMIN_KEY), `frontend/index.html`(나눔바른고딕 @font-face 는 style-guide 상단 블록 복사)
- [x] T004 [P] 스타일 토큰 — `design/style-guide.html` 의 `:root` 와 `.t-*`·`.btn-*`·`.utility-card`·`.status-*`·`.badge` 를 `frontend/src/styles/tokens.css` 로 복사
- [x] T005 [P] 공통 스크립트·데이터 폴더 — `scripts/`, `backend/data/`(routes.csv·stops.csv 헤더만), `backend/samples/README.md`(시연 프레임 출처 기재 규칙: 자유 이용 허가·출처 URL), `backend/models/.gitkeep`, `.gitignore`(models/*.pt, cv.db, .venv, node_modules)
- [x] T006 [P] 린트·포맷 — `backend/pyproject.toml` 에 ruff 설정, `frontend/.eslintrc.cjs`·`prettier` 설정

---

## Phase 2: Foundational (모든 스토리의 선행 — 완료 전 스토리 착수 불가)

- [x] T007 DB 접근 계층 — `backend/cv_api/db.py`: SQLAlchemy Core 엔진(`DATABASE_URL`, SQLite 는 `PRAGMA foreign_keys=ON` 이벤트), `apply_ddl()` 가 `design/cv_ddl.sql` 을 세미콜론 단위로 멱등 실행, `now_iso()` 유틸(UTC ISO-8601)
- [x] T008 [P] DDL 회귀 테스트 — `backend/tests/test_ddl.py`: `design/cv_ddl_verify.sql` 의 29건을 개별 트랜잭션으로 실행해 전부 거부됨을 확인, 뷰 6개 존재 확인 (SD_03 §15-1 재현)
- [x] T009 [P] PostgreSQL 이식본 — `design/cv_ddl.postgres.sql`: SD_03 §15-2 의 6종 치환(VARCHAR(19)→TIMESTAMP, strftime→CURRENT_TIMESTAMP, julianday→EXTRACT(EPOCH), group_concat→STRING_AGG, RAISE(ABORT)→RAISE EXCEPTION 함수+트리거, 부분 인덱스 유지). `db.py` 가 URL 접두로 파일을 고른다
- [x] T010 [P] Pydantic 계약 — `backend/cv_api/schemas.py`: `contracts/openapi.yaml` 의 스키마 33개를 모델로(모든 요청 모델 `model_config = ConfigDict(extra="forbid")`), 등급·경고·근거 유형 enum, `GateError`
- [x] T011 [P] 인증 의존성 — `backend/cv_api/auth.py`: `X-API-Key` → `caller_id`(401 없음/403 불일치), `X-Admin-Key` → 관리자(G1). 키는 settings 의 sha256 해시와 비교. FastAPI `Depends`
- [x] T012 게이트 모듈 — `backend/cv_api/gates.py`: `GateBlocked(gate, reason_code, reason, resolver_role, http_status, details)` 예외, 게이트→상태 매핑표(research R7: G0·G5 503, G1 401/403, G2·G8·G9 422, G3·G11 404, G4·G10 409), 예외 핸들러가 `GateError` JSON 으로 변환하고 `gate_event` 행을 기록(`resolver_role` 이 operator 이면 `gate_event_id` 를 응답에 포함)
- [x] T013 [P] 저장소 모듈 골격 — `backend/cv_api/repo/{reference,policy,external,diagnosis,measurement,ops,guide}.py`: 각 영역의 INSERT/SELECT 함수 서명과 뷰 조회(`v_readiness`, `v_camera_readiness`, `v_current_*`, `v_route_validity_minutes`, `v_vehicle_measurement_status`, `v_next_vehicle`, `v_assessment`, `v_verification_item`, `v_gate_open`)
- [x] T014 [P] 외부 공급자 인터페이스 — `backend/cv_api/external/base.py`(`ArrivalProvider.next_arrivals(route_id, stop_id, limit)`, `HeadwayProvider.headway(route_id)`, `FleetProvider.vehicles(route_id, q)` — 반환에 `source_status`), `backend/cv_api/external/fixture.py`(`backend/data/fixtures/*.json` 을 읽는 `FixtureProvider`: 노선 R102, 정류장 3001, 차량 1234·5678·9012·3456, 배차 12분), `backend/cv_api/external/__init__.py` 의 `get_providers(settings)`
- [x] T015 [P] 기준 정보 적재 도구 — `backend/cv_api/tools/load_reference.py`: TAGO CSV(`route_id,mode,route_name` / `stop_id,route_id,stop_name,place_kind`) → `route`·`stop` UPSERT. fixture 노선·정류장도 적재
- [x] T016 앱 골격과 lifespan — `backend/cv_api/app.py`: FastAPI 앱, 예외 핸들러 등록(T012), lifespan 에서 `apply_ddl()` → `server_instance(readiness='preparing')` 삽입 → 모델 적재·웜업(T023 이후 연결, 그 전엔 스텁) → `readiness='ready'`. 라우터 등록 지점. CORS(프론트 dev 서버)
- [x] T017 [P] 준비 상태 라우터 — `backend/cv_api/routers/readiness.py`: `GET /v1/readiness` ← `v_readiness`. 테스트 `backend/tests/test_readiness.py`(preparing/ready 전이, G0 503 매핑은 T012 로)
- [x] T018 [P] 프론트 API 클라이언트 — `frontend/src/api/client.ts`(fetch 래퍼, 키 헤더, `GateError` 파싱), `frontend/src/api/types.ts`(openapi.yaml 에서 `openapi-typescript` 로 생성, `package.json` 스크립트 `gen:api`)
- [x] T019 프론트 대시보드 껍데기 (Intent-Tasks 패턴) — `frontend/src/App.tsx`, `frontend/src/layout/Sidebar.tsx`(접이식, 항목 S0 홈·S5 진단·S7 후속 차량·S6 실측·S9 API활용 / 운영 관리자 구역 S1·S2·S3·S4·S8, 관리자 키 없으면 구역 미표시 = G1), `frontend/src/layout/Header.tsx`(브레드크럼, 준비 칩·시연 칩, 정류장·카메라 검색), `frontend/src/layout/Main.tsx`. 라우터 경로 `/`, `/diagnose`, `/next-vehicle`, `/measurements`, `/api-guide`, `/admin/{server,onboarding,policy,verification,demo}`
- [x] T020 [P] 공통 컴포넌트 1 — `frontend/src/components/Rail.tsx`(C1: 역할별 레일 3종, 잠긴 단계에 게이트 ID, 준비·시연 칩), `frontend/src/components/GateBlock.tsx`(C2: 사유·해제 주체·다음 행동, 타인 해제면 `RequestButton`), `frontend/src/components/RequestButton.tsx`(C7: `POST /v1/gate-events/{id}/request`, 전송 후 "요청 보냄 (시각)")
- [x] T021 [P] 공통 컴포넌트 2 — `frontend/src/components/StatusBadge.tsx`(C4: 7상태, 색+글자), `frontend/src/components/WarningChips.tsx`(C8: 코드+한글 사유), `frontend/src/components/ResultCard.tsx`(C3: 확정·판독 불확실·정원 없음·실측 없음 4변형, "참고" 접두, 고지 행), `frontend/src/components/SourceDrawer.tsx`(C6: Esc 닫힘·포커스 복귀), `frontend/src/components/ReadinessChip.tsx`(C5: 30초 폴링)
- [x] T022 [P] 프론트 상태 스토어 — `frontend/src/stores/readiness.ts`(`/v1/readiness` 폴링, G0 열림 여부), `frontend/src/stores/demo.ts`(`/v1/admin/policies/validity` 의 demo_on·demo_end_at)

**체크포인트**: `uvicorn cv_api.app:app` 기동 → `/v1/readiness` 200, `pytest tests/test_ddl.py` 통과, `npm run dev` 로 사이드바·헤더·빈 페이지 표시.

---

## Phase 3: US1 — 현재 프레임 진단 · 정직한 실패 · 비정상 요청 거부 (P1) 🎯 MVP

**목표**: 카메라 프레임 1장 → 잔여 %·등급·경고. 판독 미달은 `uncertain`, 규격 외는 422, 원본 미보관, 첫 요청 지연 없음.
**독립 검증**: `load_reference` + 시드 SQL 로 카메라·ROI·정원·등급 기준을 넣고 `pytest tests/test_diagnose.py tests/test_quality.py tests/test_schemas.py` 통과, `bench.py` p95 ≤ 2초.

### 테스트 (먼저 작성 — NFR-07 자동 검증 대상)

- [x] T023 [P] [US1] 규격 반려 테스트 — `backend/tests/test_schemas.py`: extra 필드 422(SC-05), 형식 BMP 422, 4097px 422, 10 MB+1 422, 손상 파일 422, 응답에 `allowed_spec` 포함, 반려 시 `assessment` 행 없음(UC5 사후조건 2)
- [x] T024 [P] [US1] 품질 검사 테스트 — `backend/tests/test_quality.py`: 합성 프레임(선명/가우시안 블러/어두움/양극 밝기)으로 `blur`·`low_light`·`backlight` 100% 검출(SC-06), 임계값이 settings 를 따름
- [x] T025 [P] [US1] 진단 게이트·결과 테스트 — `backend/tests/test_diagnose.py`(스텁 모델 주입): G0 503, 미등록 카메라 404, ROI 없음 409 + `gate_event`, 정원 없음 → `remaining_not_computable`, 신뢰도 0.5 → `uncertain`+`low_confidence`, 정상 → 등급 매핑·`versions`·`notice`·`person_count`, 발 위치가 ROI 밖인 박스는 제외(FR-03), 인원 × 발자국 / ROI 면적 계산값 검증, 동일 입력 동일 출력(NFR-06), 응답 후 이미지 버퍼 참조 없음(AS6 — 서비스 함수가 bytes 를 반환하지 않고 DB 에 blob 컬럼 없음)

### 구현

- [x] T026 [US1] 품질 검사기 — `backend/cv_api/quality.py`: `check_frame(np.ndarray) -> list[Warning]`(라플라시안 분산, 평균 밝기, 양극 히스토그램), `check_detections(boxes, confs) -> list[Warning]`(`low_confidence`, `occlusion` IoU 비율). settings 임계값 사용
- [x] T027 [US1] 모델 어댑터 — `backend/cv_api/predict.py`: `Detector` 프로토콜(`detect(image) -> list[Box(x1,y1,x2,y2,conf)]`), `YoloV8Detector`(ultralytics, `yolov8n.pt`, person 클래스 0 — `MaxTheTechy/yolo` 의 `detector.py` 접근법, `INFER_TIMEOUT_S`), `StubDetector`(테스트용 고정 박스). **계산은 발 위치 방식(`x_pym/모델선정.md`)**: `foot_points(boxes)` = 박스 아래 중앙점 → `count_in_roi(points, roi_polygon)`(shapely `contains`) → `occupied_area = count × footprint_m2`(settings `FOOTPRINT_M2` 기본 0.30, ROI 별 보정값 우선) → `occupied_area_ratio = occupied_area / roi_area_m2 × 100`(100 상한), `person_count` 도 함께 반환(정원 대비 인원수 병기). `warmup()` 더미 프레임 1회 + 4필드 계약 self-check. 가중치 경로·클래스 ID·발자국 면적은 settings(파일럿 후 `yolov8s.pt` 승격 대비)
- [x] T028 [P] [US1] 모델 가져오기 도구 — `backend/cv_api/tools/fetch_model.py`: `--repo --weights` 로 가중치를 `backend/models/` 에 받고 `model_package` 행 기록(repo `https://github.com/MaxTheTechy/yolo`, commit, weights `yolov8n.pt`, license=None, contract_check_result='adapter')
- [x] T029 [US1] 진단 서비스 — `backend/cv_api/services/diagnosis.py`: P5 5.2~5.9 순서 — 규격 검증(G2, 디코드) → 카메라·ROI·정원·등급 기준 조회(`v_camera_readiness`, G3·G4) → 품질 검사 → 추론(G5) → 등급 산출(ThresholdPolicy, G6 → `uncertain`, G7 → spec_id NULL) → `diagnosis_request`·`assessment`·`assessment_warning` 저장(roi_stale 카메라면 `roi_stale` 경고 동봉) → 이미지 버퍼 즉시 폐기 → `v_assessment` 로 응답 조립. 단건·일괄·실측이 모두 이 함수 하나를 호출한다(SD_01 §7-3·§9-3)
- [x] T030 [US1] 진단 라우터 — `backend/cv_api/routers/diagnose.py`: `POST /v1/diagnose`(multipart, `DiagnoseRequest`), 응답 `Assessment`. `app.py` 에 등록, lifespan 의 웜업을 T027 로 연결
- [x] T031 [P] [US1] 시드 SQL·픽스처 — `backend/tests/conftest.py`: 임시 SQLite + DDL + 시드(노선 R102, 정류장 3001, 유형 VT_LOW 정원 80, 카메라 CAM-B12 차내·CAM-S03 승강장, ROI, 등급 기준 50/20, 유효 시간 규칙, 모델 패키지, 인스턴스 ready), 스텁 모델 주입 픽스처, 합성 프레임 생성기
- [x] T032 [P] [US1] 벤치 — `backend/bench.py`: N회 `POST /v1/diagnose` p50/p95(NFR-01), 기동 직후 첫 요청 / 정상 중앙값 비율(SC-04), 결과를 표로 출력
- [x] T033 [US1] 프론트 S5 이용자 뷰 — `frontend/src/pages/Diagnose.tsx`: 카메라 선택, 파일 선택 시 제출 전 미리보기(제출 후 제거, U8), 촬영 시각·형식·해상도·용량 표시, «진단 요청», 결과 `ResultCard`, 반려·G4 `GateBlock`(+`RequestButton`), «후속 차량 여유도 조회 S7» 이동. 레일 "연계·웹서비스"
- [x] T034 [US1] 프론트 S5 관제 뷰 — `frontend/src/pages/DiagnoseControl.tsx`: 판독 불확실 카드, 관제 판단 라디오(저장 없음, R18), «재촬영·재제출 요청»·«ROI 검증 요청»(RequestButton), «확정 등급으로 사용» 항상 비활성 + 사유, 정원 없음·roi_stale 블록. 라우트 `/diagnose/control`

**체크포인트**: quickstart §3 의 첫 두 curl(정상·블러) 과 422 반려가 재현되고 `bench.py` p95 ≤ 2초(CPU 기준 스텁 아님).

---

## Phase 4: US2 — 기준 정보·정책 관리 (P1)

**목표**: 운영 관리자가 카메라·ROI·정원·등급 기준·유효 시간·시연 모드·식별자 매핑을 등록·판본·이력으로 관리. G8·G9 저장 차단.
**독립 검증**: 관리자 키로 `/v1/admin/*` 전 엔드포인트가 동작하고 `pytest tests/test_admin.py` 통과, S2·S3 화면에서 등록 → `v_camera_readiness` 가 has_roi/has_capacity/has_mapping = 1.

### 테스트

- [x] T035 [P] [US2] 관리 API 테스트 — `backend/tests/test_admin.py`: 관리자 키 없음 401/403(G1), 카메라 등록·중복, ROI 꼭짓점 2개 422·변 교차 422(앱 검사)·저장 후 판본 2개·roi_stale 해제, 정원 0·좌석>정원·출처 없음 422, 등급 기준 과거 시작일 422·상한≥하한 422, 유효 시간 시연 on + 종료 시각 없음 422(기본 +2시간 자동 채움 확인), 매핑 존재 검증 실패 422·동일 카메라 2번째 활성 422·해제 시 released, CSV 필수 열 누락 422·행별 격리 결과

### 구현

- [x] T036 [US2] 기준 정보 서비스 — `backend/cv_api/services/reference.py`: 카메라 등록(R9), ROI 저장(shapely 로 꼭짓점·범위·자기 교차 검사, 픽셀 면적 → `roi.area`, **실제 바닥 면적 `roi_area_m2` 와 카메라별 발자국 보정값 `footprint_m2`(선택) 입력** — `cv_ddl.sql` 의 `roi` 에 두 컬럼 추가(NULL 허용, SD_03 갱신은 T074), 이전 판본 `superseded_at`, `camera.roi_stale=0`), 제원 저장(판본), 매핑 저장(`FleetProvider` 존재 검증 → verified/unverified(R11), 활성 중복은 DB 예외를 G9 로 변환), 매핑 해제(해당 차량 `camera_measurement`·`vehicle_measurement` superseded — UC12 A3), CSV 파싱(UTF-8 BOM, 열 이름 식별, 행별 격리, R13)
- [x] T037 [P] [US2] 정책 서비스 — `backend/cv_api/services/policy.py`: 등급 기준 저장(`trg_threshold_future` 예외를 G8 로), 유효 시간 규칙 저장(새 판본 + 이전 superseded, 예외 노선, demo_on 이면 demo_end_at 기본 +2h), `v_route_validity_minutes` 미리보기(`HeadwayProvider` 로 `route_headway` 스냅샷 갱신, 장애 시 stale 24h — R11)
- [x] T038 [US2] 관리 라우터 — (`RoiCreate`·`Roi`·`Assessment` 의 `roi_area_m2`·`footprint_m2`·`person_count` 는 openapi.yaml 에 반영됨 — `schemas.py` 가 따른다)  `backend/cv_api/routers/admin.py`: `POST /v1/admin/cameras`, `GET /v1/admin/cameras/{id}`, `GET/POST .../roi`, `POST /v1/admin/vehicle-types/{id}/spec`, `GET/POST /v1/admin/policies/threshold`, `GET/POST /v1/admin/policies/validity`, `GET/POST /v1/admin/mappings`, `DELETE /v1/admin/mappings/{map_id}`, `POST /v1/admin/mappings/csv`, `GET /v1/admin/fleet`. 전부 `AdminKey` 의존성
- [x] T039 [US2] 프론트 S2 투입 등록 — `frontend/src/pages/admin/Onboarding.tsx`: 2.1 카메라 선택·현황(has_roi/roi_stale/has_capacity/has_mapping) + «카메라 등록» 다이얼로그, 탭 ROI(좌표 입력 + 캔버스에 다각형 그리기 — 배경 프레임은 브라우저 메모리에만) / 차량 제원 / 매핑(자동완성 `GET /v1/admin/fleet`, CSV 업로드 결과 표) / 이력(C9). G3·G8·G9·G12 `GateBlock`
- [x] T040 [P] [US2] 프론트 S3 정책 설정 — `frontend/src/pages/admin/Policy.tsx`: 등급 기준 표(현재/새 값/행별 검증), 유효 시간 규칙 폼 + 노선별 미리보기 표(출처 열), 시연 모드 스위치 + 종료 예정, 이력, «정확도 검증 S4 로 이동»
- [x] T041 [P] [US2] 프론트 컴포넌트 — `frontend/src/components/HistoryPanel.tsx`(C9), `frontend/src/components/PolygonEditor.tsx`(캔버스 다각형)

**체크포인트**: quickstart §2 를 화면과 curl 양쪽으로 완료, US1 의 시드 없이 화면 등록만으로 US1 진단이 성립.

---

## Phase 5: US3 — 후속 차량 실측 등록·여유도 조회 (P1)

**목표**: 차내 프레임 → 카메라 실측 → 차량 합산 → 정류장 조회 시 "실측 / 실측 없음 / 조회 불가".
**독립 검증**: `pytest tests/test_measurement.py tests/test_next_vehicle.py` 통과, quickstart §3 의 next-vehicle 응답이 AS2·AS2-b·AS2-c·AS2-e 를 재현, BIS 공급자를 끊어도 진단(US1)은 정상(NFR-08).

### 테스트

- [x] T042 [P] [US3] 실측 테스트 — `backend/tests/test_measurement.py`: 매핑 없음 409(G10 + gate_event), 승강장 카메라 409, 판독 불확실도 실측 보관(BR-CV-23), 이전 실측 superseded, 카메라 3대 중 2대 제출 → 면적 가중 평균·coverage 2/3·`partial_coverage`(AS2-e), 유효 만료 시각 = measured_at + 노선 유효 시간(예외 12분 / 기본 10분), 촬영 시각 만료 → `already_expired`
- [x] T043 [P] [US3] 조회 테스트 — `backend/tests/test_next_vehicle.py`(FixtureProvider): 기준 정보 없음 404(G11), 실측 있음 `measured`, 만료 `no_measurement` + 등급·비율 NULL(AS2-b, 추정값 없음), 판독 불확실 실측 그대로 전달(AS2-c), 공급자 예외 → `basis_type: unavailable` 200 이고 같은 세션에서 `/v1/diagnose` 정상(NFR-08), 호출 주체 두 키가 같은 응답(FR-16)

### 구현

- [x] T044 [US3] 실측 서비스 — `backend/cv_api/services/measurement.py`: P6 6.2 매핑·차내 확인(`v_camera_readiness`, G10) → `diagnosis.diagnose(kind='measurement')` → 6.4 `camera_measurement`(measured_at = captured_at, 시연 모드면 registered_at; validity_minutes ← `v_route_validity_minutes`; expires_at; 이전 superseded) → 6.5 합산(`v_active_mapping` 으로 매핑 카메라 수, 시각 창 안·유효 실측만, `roi.area` 가중, `vehicle_measurement`+`component`, 이전 superseded) → `MeasurementResult`
- [x] T045 [P] [US3] 후속 차량 서비스 — `backend/cv_api/services/next_vehicle.py`: P7 7.2 `route`·`stop` 확인(G11) → 7.3 `ArrivalProvider`(예외·타임아웃 → `arrival_snapshot.source_status`, G12) → `arrival_snapshot` 저장 → `v_next_vehicle` 조회(limit) → `applied_validity_minutes`·`demo_mode`·`notice` 조립
- [x] T046 [US3] 라우터 — `backend/cv_api/routers/measurements.py`(`POST /v1/measurements`), `backend/cv_api/routers/next_vehicle.py`(`GET /v1/next-vehicle`), `backend/cv_api/routers/gate_events.py`(`POST /v1/gate-events/{id}/request` — resolver_role self 면 409)
- [x] T047 [P] [US3] BIS 공급자 — `backend/cv_api/external/bis.py`: 대전광역시 공공데이터포털 API(`apis.data.go.kr/6300000` — 노선정보조회 `busRouteInfo`, 버스위치정보 `busposinfo/getBusPosByRtid`), httpx·`BIS_API_KEY`·제한 시간 3초, 실패 시 `unavailable`/`timeout`. 필드는 2026-09-29 실측. **도착 정보 API 가 없어** 도착 시각은 누적 거리 차 ÷ 노선 평균 속도로 추정. 테스트 `tests/test_bis.py`(6)
- [x] T048 [P] [US3] 프론트 S7 후속 차량 — `frontend/src/pages/NextVehicle.tsx`: 노선·정류장 드롭다운(`route`·`stop` 은 `GET /v1/admin/fleet` 이 아닌 공개 목록 — `GET /v1/next-vehicle` 의 404 사유로 대체하거나 `backend/data` 정적 JSON 을 프론트에 내장), 결과 표(차량·도착·잔여·등급 배지·근거·실측 시각 경과·커버리지·경고), 하단 적용 유효 시간·고지·시연 배너, G12 출력 차단 블록, G11 블록, 행 클릭 `SourceDrawer`. 갱신 주기 30초
- [x] T049 [P] [US3] 프론트 S6 실측 등록 — `frontend/src/pages/Measurement.tsx`: 차량 식별자·차내 카메라(차내 유형만)·프레임·촬영 시각, 결과(카메라 진단 + 차량 합산 + 만료·유효 시간·시연), 판독 불확실 보관 안내 + «같은 차량 재제출», G10 블록 + RequestButton

**체크포인트**: 카메라 2대를 한 차량에 매핑하고 프레임 2장을 등록 → S7 에서 커버리지 2/2 로 표시. 공급자를 fixture→bis 로 바꿔도 코드 변경 없음.

---

## Phase 6: US4 — 시연 준비·수행 (P2)

**목표**: 사전 촬영 프레임 일괄 등록 + 시연 모드로 발표 시연이 성립. 8.1→8.5 순서 강제.
**독립 검증**: `python scripts/demo_prepare.py --reset` 한 번으로 S7 장면 1 응답이 나오고, 시연 모드를 끄면 같은 조회가 `no_measurement` 로 바뀐다(AS2-d, G14).

- [x] T050 [P] [US4] 시연 테스트 — `backend/tests/test_demo.py`: 시연 모드 꺼짐 상태 일괄 등록 → 각 항목 `already_expired`·`demo_mode:false`(G14), 켜짐 → measured_at = registered_at·`demo_mode:true`·S7 `measured`, 종료 예정 시각 경과(시각 고정 픽스처) → `demo_flag` 0
- [x] T051 [US4] 일괄 실측 라우터 — `backend/cv_api/routers/measurements.py` 에 `POST /v1/measurements/batch`(관리자 키, `batch(purpose='demo_preload')`, 항목별 `measurement.register` 반복, 개별 실패 격리, 제출 순서 유지)
- [x] T052 [US4] 시연 준비 스크립트 — `scripts/demo_prepare.py`: quickstart §2·§3 의 P1~P6 을 httpx 로 순서대로 호출(카메라 3대 CAM-DEMO-01~03 ← 사진 1장 = 카메라 1대, ROI, 정원, 매핑 1234·5678·9012 + 실측 없는 3456, 시연 모드 on, 사전 프레임 3장 `backend/samples/` 일괄 등록), 각 단계 게이트 실패 시 G 번호·사유 출력 후 중단, `--reset` 은 DB 파일 삭제 후 재기동 안내. HG/시연웹/01-시연-시나리오.md §3 준수
- [x] T053 [US4] 프론트 S8 시연 — `frontend/src/pages/admin/Demo.tsx`: 시연 레일(8.1~8.5 잠금 + 게이트 ID), 8.1 매핑 확인 표(«S2 에서 매핑 등록» 이동·복귀 시 재확인), 8.2 종료 예정 시각 + «시연 모드 켜기», 8.3 프레임 표 + «일괄 등록», 8.4 «S7 열기»(시연 노선·정류장 사전 입력), 8.5 «끄기» + 자동 해제 안내
- [X] T054 [P] [US4] 시연 자산 — `backend/samples/`: 혼잡·여유·흐림 버스 차내 사진 3장(자유 이용 허가, `README.md` 에 출처·라이선스 기재, 흐림은 원본을 가우시안 블러 처리), 각 사진용 ROI 좌표 JSON — **2026-09-29 대체 완료(사용자 결정 ④)**: 사진 대신 샘플 영상(`samples/videos`, CC BY-SA·CC0, 출처 README)에서 프레임을 뽑는다(`demo_prepare.py`). R22 에서는 도형 합성 그림이 0명이라 쓰지 않는다

**체크포인트**: HG/시연웹 §1-1 의 화면 1~6 을 리허설로 재현.

---

## Phase 7: US5 — 사전 녹화 프레임 일괄 검증 (P2)

**목표**: N장 일괄 → 프레임별 결과(순서·단건 동일) → 수작업값 대비 SC-01·02 판정 → S3·S1 환류.
**독립 검증**: `pytest tests/test_batch.py` 통과, S4 에서 10장 검증 → 판정 표시·검증 결과 저장.

- [x] T055 [P] [US5] 일괄 테스트 — `backend/tests/test_batch.py`: 순서 보존(`batch_seq`), 각 항목이 단건 진단과 동일(같은 스텁 입력 → 같은 출력, NFR-06·BR-CV-12), 21장 422, 규격 위반 1장만 반려하고 나머지 진단(R14), 정합성 블록(roi/spec/threshold 동일, 폐기·기록 건수), 판정 — 87%/78% → fail, 판독 불확실·반려 행 제외
- [x] T056 [US5] 일괄 진단 라우터 — `backend/cv_api/routers/diagnose.py` 에 `POST /v1/diagnose/batch`(관리자 키, `batch(purpose='verification')`, `diagnosis.diagnose(kind='batch_item')` 반복, `BatchResult`)
- [x] T057 [P] [US5] 검증 서비스·라우터 — `backend/cv_api/services/verification.py`(`verification_item` 저장 → `v_verification_item` → 일치율 2종·verdict → `verification_run`(판본 FK 고정)), `POST /v1/admin/verification-runs` 를 `routers/admin.py` 에 추가. 정책·ROI·모델 판본이 바뀌면 `invalidated_at` 을 채우는 함수(`services/policy.py`·`reference.py` 저장 시 호출)
- [x] T058 [US5] 프론트 S4 정확도 검증 — `frontend/src/pages/admin/Verification.tsx`: 카메라·프레임 N장(순서 유지)·수작업 CSV(브라우저에서 파싱해 항목으로 전송), 결과 표(순서·잔여·등급·경고·신뢰도·수작업·차이·제외), 정합성 행, 4.7 판정(SC-01·02, 판본, 무효화) + «정책 재조정 S3»·«모델 갱신 S1»·«검증 결과 저장», G4·G2 블록

---

## Phase 8: US6 — API 활용 안내·웹서비스 연동 확인 (P2)

**목표**: 'API활용' 메뉴(카탈로그·가이드라인·매뉴얼·모델 카드)와 서버 연동·시험 호출 화면. G17 계약 대조.
**독립 검증**: `pytest tests/test_guide_contract.py` 통과(openapi.json ↔ api_endpoint), S9 가 준비 중에도 열람되며 시험 호출만 비활성, S1 에서 시험 프레임 → 결과·SC-04 표시.

- [x] T059 [P] [US6] 계약 대조 테스트 — `backend/tests/test_guide_contract.py`: 앱의 `openapi.json` 경로·메서드 집합이 `api_endpoint` 시드의 path·method 와 일치(G17), `GET /v1/api-guide` 가 키 없이 200, `readiness` 포함
- [x] T060 [US6] 안내 콘텐츠 — `backend/cv_api/guide/{guideline.md,manual.md,model_card.md}`: 가이드라인(호출 주체 식별·무차등, 규격 값, 고지 의무, 경고 7종 해석, 비식별·미보관, 성능 기준, 낙인 방지 문구 가이드 OR-03), 매뉴얼(준비 확인 → 프레임 제출 → 결과 해석 → 후속 차량 조회, 요청·응답 예시, 오류·경고 대처, 시연 모드 해석), 모델 카드(FR-18: 목적·한계·면책·검증 결과 — 모델 `MaxTheTechy/yolo` YOLOv8n person 검출, 면적 기반 점유율은 본 서비스 산출임을 명시, 가중치 AGPL-3.0)
- [x] T061 [US6] 안내 서비스·라우터 — `backend/cv_api/services/guide.py`(`api_guide`·`api_endpoint` 시드: 기능 7건 UC1·4·2·10·9·6~12·15 에 path·method 채움, `contract_hash` = openapi.json sha256, 배포 전 대조 함수) + `backend/cv_api/routers/guide.py`(`GET /v1/api-guide`)
- [x] T062 [P] [US6] 연동 서비스·라우터 — `backend/cv_api/services/ops.py` 에 `integration` 등록(P1 1.5)·시험 호출 기록(1.6: `kind='test_call'`, `first_response_ms`, 실패 시 reverted) + `routers/admin.py` 에 `GET /v1/admin/ops-status`·`GET /v1/admin/gate-events`(S1·S0 용) 추가. `POST /v1/admin/integrations`·`POST /v1/admin/integrations/{id}/test` 를 openapi.yaml 에 **추가**(계획 계약 누락 보완)
- [x] T063 [P] [US6] 프론트 S9 API 활용 — `frontend/src/pages/ApiGuide.tsx`: 탭 카탈로그(표 + `/docs` 링크) / 가이드라인 / 매뉴얼 / 모델 카드(마크다운 렌더), 9.4 시험 호출(예시 요청 선택 + 프레임, G0 면 비활성 + 사유), 배포 게이트 한 줄
- [x] T064 [P] [US6] 프론트 S1 서버 준비·연동 — `frontend/src/pages/admin/Server.tsx`: 1.1~1.4 상태 표(`model_package`·`server_instance`), 1.5 연동 등록 폼(G0 전 비활성), 1.6 시험 호출 + SC-04, G15·G16 블록

---

## Phase 9: US7 — 운영 상시·운영 상태 화면 (P3)

**목표**: P0 의 준비 감시·시연 자동 해제·지표 누적과 S0 운영 상태.
**독립 검증**: 시연 종료 예정 시각을 과거로 두고 배치를 돌리면 `demo_on=0` 새 판본, 모델 접근 실패를 흉내 내면 `readiness=unavailable` → `/v1/diagnose` 503.

- [x] T065 [P] [US7] 상시 테스트 — `backend/tests/test_ops.py`: 자동 해제(P0 0.4), 준비 감시 전환(P0 0.5), `quality_metric` 집계(시간대·조도 조건별 편차, test_call 제외 — R15), 보존 배치가 `RETENTION_DAYS=None` 이면 아무것도 지우지 않음(R17), 점검 쿼리 Q1~Q5(SD_03 §13-2) 0건
- [x] T066 [US7] 백그라운드 태스크 — `backend/cv_api/services/ops.py`: lifespan 에서 60초 주기 루프 — 0.4 시연 자동 해제, 0.5 준비 감시(모델 객체·DB 접근 확인 → `server_instance.readiness` 갱신), 0.2 `quality_metric` 시간별 집계, 보존 폐기(값 있을 때만). 만료(0.3)·roi_stale(0.6)은 뷰·진단 시점 처리라 배치 없음
- [x] T067 [P] [US7] 프론트 S0 홈·운영 상태 — `frontend/src/pages/Home.tsx`: 운영 상태 카드 4종(`GET /v1/admin/ops-status` — 준비·시연·roi_stale 카메라·오늘 만료 수, 관리자 키 없으면 준비·시연만), 메뉴 카드(이용자/운영 관리자), G0 준비 중 블록(재확인·요청 보내기)

---

## Phase 10: Polish · 횡단 관심사

- [x] T068 [P] 접근성 — 모든 비활성 버튼 `aria-disabled` + `aria-describedby`(사유), 배지 `aria-label`, 표 `<th scope>`, 레일 `nav aria-current="step"`, 드로어 포커스 트랩. `frontend/src/components/*`
- [x] T069 [P] 반응형 — 640/833/1068 브레이크포인트(style-guide §08): 사이드바 접힘(≤833), 표 가로 스크롤(≤640). `frontend/src/styles/layout.css`
- [x] T070 [P] 오류 규약 — 서버 응답 없음 → 준비 칩 "진단 불가" + S0 블록(마지막 성공 응답 미표시), 2초 초과 "지연 중" 표시. `frontend/src/api/client.ts`, `frontend/src/stores/readiness.ts`
- [x] T071 [P] 프론트 컴포넌트 테스트 — `frontend/tests/GateBlock.test.tsx`(사유·해제 주체·요청 버튼 조건), `ResultCard.test.tsx`(4변형·참고 접두), `Rail.test.tsx`(잠금 단계)
- [x] T072 [P] 집계·감사 — `v_audit_record` 를 `GET /v1/admin/audit`(관리자, 기간 필터, caller_id·created_by 미포함) 로 노출 — openapi.yaml 에 추가. `backend/cv_api/routers/admin.py`
- [X] T073 PostgreSQL 실행 검증 — 로컬 PostgreSQL 15 에 `cv_ddl.postgres.sql` 적용 + `test_ddl.py` 를 `DATABASE_URL=postgresql://…` 로 재실행(부분 인덱스·트리거 동작 확인). 결과를 `design/SD_03_…md` §15-2 에 실측으로 추가 — **2026-09-29 완료**: Docker 권한이 없어 `pgserver`(PostgreSQL 16.2, 유닉스 소켓)로 `tests/test_ddl_postgres.py` 신설(test_ddl.py 는 SQLite 전용). 이식본 결함 3종(`CREATE VIEW IF NOT EXISTS`, 스칼라 `MIN`, boolean 비교식)과 `db.split_sql` 결함 2종(`$$` 본문·주석 `%`) 수정 → 적용·멱등·뷰·위반 28/28 거부 통과. SD_03 §15-2 기록
- [x] T074 [P] 상류 문서 갱신 — plan.md "상류 문서에 되돌릴 갱신" 7건: `design/UC_00`(§8.4 3, §8.3 7·22·23·26·27), `SD_01` §14 G3·§16, `SD_02` S2 2.1 «카메라 등록»·§16, `SD_03` §16, `UC_13` 사후조건, `UC_15` 카탈로그 경로, `spec.md` 는 Clarifications 3차로 이미 반영 — **2026-09-29 완료**: UC_00 §8.2·§8.3(7·22·23·26·27)·§8.4(3·6), SD_01 §5 P2 결과 문단·§14 G3·§16(결정 열 추가), SD_02 S2 2.1 영역·상호작용·상태 전이·§16(결정 열), SD_03 §9 resolver_role 설명·§11 G3·§16(결정 열, DDL 변경 없음), UC_13 사후조건 (1)·A2, UC_15 카탈로그 경로 열. PlantUML 도면(와이어프레임·ERD 주석)은 재렌더하지 않음
- [x] T075 [P] 문서 — `backend/README.md`·`frontend/README.md`(quickstart 요약), `CLAUDE.md`(스택·구조·규칙: 정본 DDL, 게이트→상태, 원본 미보관, 스킬 사용 — Intent-Tasks 의 frontend-design 등) — plan 단계에서 미수행한 agent context 보완
- [x] T076 배포 전 검증 스위트 — `backend/Makefile` 또는 `scripts/preflight.sh`: `pytest`, `bench.py --n 100`, 계약 대조(T059), DDL 회귀(T008), `npm test`, `npm run build`. NFR-07 의 "배포 전 자동 검증" 진입점
- [x] T077 모델 승격 대비 — `backend/cv_api/predict.py` 의 `Detector` 구현을 settings `DETECTOR=yolov8n|yolov8s|<new>` 로 선택하도록 하고, 가중치 교체 절차를 `backend/README.md` 에 기재. 파일럿(US5) 정확도 미달 시 `yolov8s.pt` 로 올리는 태스크를 여기서 파생

---

## Dependencies

```
Phase 1 Setup ─► Phase 2 Foundational ─► US1 (P1, MVP)
                                      ├─► US2 (P1) ── US1 의 시드를 화면 등록으로 대체
                                      └─► US3 (P1) ── US1 의 diagnose 서비스 + US2 의 매핑 서비스에 의존
US3 ─► US4 (P2) 시연 (일괄 실측 + 시연 모드)
US1 ─► US5 (P2) 일괄 검증 (diagnose 반복) ─ US2 의 정책 저장 시 무효화 호출
US1 ─► US6 (P2) 안내·연동 (test_call 은 diagnose)
US2 ─► US7 (P3) 상시 (validity_policy 자동 해제)
전 스토리 ─► Phase 10 Polish
```

- US1 은 Foundational 만 있으면 시드 SQL 로 독립 검증 가능.
- US2 는 US1 과 병렬 착수 가능(다른 파일). 단, US1 체크포인트 "화면 등록만으로 진단"은 US2 완료 후.
- US3 은 T029(diagnose)·T036(매핑 저장)을 쓴다 — 두 태스크 완료 후 착수.
- US4·US5·US6 은 서로 독립, US3/US1 완료 후 병렬.

## Parallel Execution Examples

**Foundational**: T008 · T009 · T010 · T011 · T013 · T014 · T015 를 동시에(각각 다른 파일). T012→T016→T017 순서. 프론트 T018 · T019 · T020 · T021 · T022 는 백엔드와 독립.

**US1**: 테스트 T023 · T024 · T025 동시 작성 → T026 · T027 · T028 동시 → T029 → T030 → T031 · T032 · T033 · T034 동시.

**US2 ∥ US1**: T035 · T036 · T037 은 US1 의 T026~T030 과 파일이 겹치지 않아 동시 진행.

**US3**: T042 · T043 → T044 · T045 · T047 동시 → T046 → T048 · T049 동시.

**US4 ∥ US5 ∥ US6**: 세 스토리를 세 작업자가 동시에(공유 파일은 `routers/admin.py`·`routers/measurements.py`·`routers/diagnose.py` 뿐이라 태스크 단위로 순서만 조정).

## Implementation Strategy

1. **MVP = Phase 1~3 (US1)**: 시드 데이터로 `POST /v1/diagnose` 와 S5 화면이 동작하고 SC-05·SC-06 자동 검증이 통과하면 첫 배포 가능. 모델은 `MaxTheTechy/yolo` 의 YOLOv8n(Q12 확정).
2. **P1 완성 = + US2·US3**: 화면 등록으로 기준 정보를 넣고 후속 차량까지. 이 시점에 시연 시나리오 장면 1~6 의 데이터 흐름이 전부 성립.
3. **발표 준비 = + US4**: `demo_prepare.py` 와 S8. 발표 1주 전 리허설 체크리스트(HG/시연웹 §8).
4. **파일럿 = + US5·US6·US7**: 정확도 판정으로 임계값 재조정, 연계 개발자 안내, 상시 운영.
5. **모델 승격 시**: T077 에서 파생되는 가중치 교체 태스크만 수행 — 어댑터 경계 덕에 서비스·계약·DB 는 변하지 않는다.

## 요약

| 구분 | 태스크 수 |
|---|:--:|
| Setup | 6 |
| Foundational | 16 |
| US1 진단·정직한 실패·규격 거부 | 12 |
| US2 기준 정보·정책 관리 | 7 |
| US3 실측·후속 차량 | 8 |
| US4 시연 | 5 |
| US5 일괄 검증 | 4 |
| US6 안내·연동 | 6 |
| US7 상시·운영 상태 | 3 |
| Polish | 10 |
| **합계** | **77** |

병렬 가능 `[P]` 태스크 50개. 테스트 태스크 13개(T008·T017·T023·T024·T025·T035·T042·T043·T050·T055·T059·T065·T071).


---

## 구현 기록 (2026-09-28, /speckit.implement)

- 완료 73 / 77. 미완료: T054(시연 사진 3장 — 사람이 선정), T073(PostgreSQL 실행 검증 — 로컬 설치 필요), T074(상류 문서 갱신 — 루트 design/ 수정 허락 필요).
- 참고사항 반영: 검출기 백엔드 2종(`yolov8` 프로세스 내 / `ollama_vl` 공유 Ollama `gemma4:e4b` — qwen3-vl 은 사고 모드 미해제로 출력이 비어 배제) + `stub`. 모델 로딩 시간은 `GET /v1/readiness.detector`(적재 초·웜업 시각·최근 추론 ms), S1 화면 표, `POST /v1/admin/detector/preload` 로 관리. Ollama 규칙은 `backend/cv_api/ollama_client.py` 가 강제.
- 검증: backend pytest 58 통과(DDL 위반 29건 거부 포함), frontend tsc·vitest 5·build 통과, `scripts/smoke.py` PASS, `scripts/demo_prepare.py` PASS, `bench.py` 결과는 최종 보고 참조.
- 스키마 추가 컬럼(roi_area_m2, footprint_m2, person_count, detector_kind, load_seconds)은 정본 `cv_ddl.sql` 을 고치지 않고 `db.py` MIGRATIONS 로 적용. `design/cv_ddl.postgres.sql` 이식본 생성(실행 검증 미수행).

## 구현 기록 (2026-09-29, T047)

- 완료 74 / 77. BIS 인증키(data.go.kr 일반 인증키)는 `backend/.env` 에만 둔다(git 제외).
- 실측: 노선 기본정보 `ALLO_INTERVAL(_SAT/_SUN)` → 배차(KST 요일별), 버스 위치 `PLATE_NO` → 운행 차량, 경유 정류소·버스 위치의 `TOTAL_DIST`(기점 누적 m) → 도착 추정(`RUN_DIST_HALF ÷ RUN_TM`, 8~40km/h 로 제한, 없으면 18km/h).
- 노선 식별: `ROUTE_CD`(8자리) 권장. 노선 번호는 유일하지 않아(`1` = 30300001·30300100·30300103) 번호가 겹치면 조회하지 않는다. 정류장은 `BUS_STOP_ID`·`BUS_NODE_ID` 둘 다 허용.
- 캐시: 버스 위치 15초, 노선·정류소 6시간(일일 호출 한도 보호).
- 기본값은 `EXTERNAL_PROVIDER=fixture` 로 둔다(시연 R102/3001). `bis` 로 바꾸려면 `route`·`stop` 기준 정보가 `ROUTE_CD`·`BUS_STOP_ID` 체계로 적재돼 있어야 G11 을 통과한다.
- 검증: pytest 64 통과(58 + BIS 6), 실 API 로 노선 30300001 배차·운행 차량 5대·정류소 2곳 도착 추정 확인.

## 구현 기록 (2026-09-29, T074 잔재 정리 — 사용자 허락 범위 A)

- T074 체크는 앞선 작업에서 이미 되어 있었고, 이번에 남은 불일치를 정리했다. 완료 75 / 77. 남은 것: T054(시연 사진 — 사람), T073(PostgreSQL 실행 검증 → 결과를 SD_03 §15-2 에 기록).
- 잔재: SD_02 G3 "해제 주체 미정" 2곳(와이어프레임 텍스트·게이트 표) → 운영 관리자, UC_15 "자료 없음" 문구 2곳 → R7, spec Assumptions 17 → R13(영문 열·UTF-8 BOM 허용).
- 스키마 정본 동기화: 구현 단계 추가 컬럼 6개를 `cv_ddl.sql`·`cv_ddl.postgres.sql`·SD_03(ERD·엔티티 명세·§15-3 표)에 반영. MIGRATIONS 는 기존 DB 호환용으로 유지.
- 점유 면적 산출(R20): UC_13 2·4단계·A3, BR-CV-02(UC_01·UC_04·UC_13)를 구현 기준으로 주석. spec FR-04 본문은 그대로 — "개별 인원 수가 아닌" 문구 정합은 UC_00 §8.3 28 에 팀 검토 대기로 등록.
- BIS(T047) 결과: research R12 "구현 확인", SD_01 P7 7.3 도착 시각 추정, UC_00 §8.3 29(식별 체계 미결).
- 검증: pytest 69 통과(`test_roles.py` 5건은 다른 세션이 추가), 정본 DDL 만으로 새 DB 에 추가 컬럼 6개 생성 확인. PlantUML 도면은 속성 줄만 추가, 재렌더하지 않음.

## Phase 8: 구현 단계 결정 반영 (2026-09-29, research R21)

- [X] T078 [R21-D1] 한 프로세스 두 포트 — `backend/cv_api/serve.py`(같은 `create_app("all")` 을 9544·9524, lifespan 은 첫 포트), `app.py` 기본 앱 = 전체, `settings.SERVE_PORTS`, `vite.config.ts` 프록시 단일화(/v1 → 9524), `tests/test_serve.py`
- [X] T079 [R21-D8] 열차 차내 카메라 — (정정) 오전 구현 '승강장 실측 허용'을 되돌려 승강장은 거부(G10) 복원, `place_type` 에 `train_in` 추가: `cv_ddl.sql`·`cv_ddl.postgres.sql` CHECK·`trg_cm_in_vehicle_camera`(차내 = bus_in·train_in), 기존 DB 는 `db._widen_place_type`(SQLite writable_schema / PG 제약 교체), `services/measurement.py`, `schemas.py`·openapi, `frontend/src/api/place.ts`(S2·S5·S6 선택지·표시), `cv_ddl_verify.sql` 30건, 테스트
- [X] T080 [R21-D10] S1 '받은 요청' — `GET /v1/admin/gate-events?requested_only=true`, `GateEvent.request_sent_by`, `pages/admin/Server.tsx`, openapi.yaml, 테스트
- [X] T081 [R21-D5] BIS 체계 기준 정보 — `cv_api/tools/fetch_bis_reference.py`(route_id = ROUTE_CD, stop_id = ROUTE_CD:BUS_STOP_ID), `BisProvider` 합성 ID 해석, 테스트. 실 API 2노선 적재·G11·도착 추정 확인(임시 DB)
- [X] T082 [R21-D7] FR-04·BR-CV-02 개정 — spec FR-04, UC_01·UC_04·UC_13 BR-CV-02, UC_00 §8.3 28 해결
- [X] T083 [R21] 설계 문서 상태 갱신 — research R21 신설, UC_00 §8.3(4·5·10·12·18·25·28·29), SD_01 §16(3·9)·§7-3(D11), SD_02 §16(1·6·8·12)·S1·S6, SD_03 §16(2·7·9·10·11·12·13·15·16)·§11 G10·§15, UC_10 A3
- [X] T084 [R21-D1] 실행 문서 — CLAUDE.md, backend/README.md, quickstart.md, guide/manual.md, `.env.example` 2개, preflight·demo_prepare 안내문

## 구현 기록 (2026-09-29, /speckit.implement — R21 반영)

- 완료 83 / 84. 남은 것: T054(시연 사진 — 팀원이 자유 이용 사진 수집, R21-D6).
- 검증: pytest 95 통과(PostgreSQL 2건 포함, `PG_TEST_URL` 설정 시), vitest 5, tsc, build. 백엔드를 `python -m cv_api.serve` 한 프로세스로 재기동 — 9524·9544 동일 응답, 9504 프록시·`/v1/web` 중계 확인.
- 남은 위험: 앱 전체를 PostgreSQL 로 돌린 검증은 없음(TIMESTAMP 가 datetime 으로 읽혀 문자열 비교 코드에 영향 가능). D8 은 권고와 다른 선택 — 승강장 프레임의 여유도 해석은 운영 기관 확인 필요.

## Phase 9: 재생하며 실시간 진단 (2026-09-29, 사용자 요청)

- [X] T085 [US1] S5 영상 재생 중 초 단위 실시간 진단 — `frontend/src/components/LiveVideoDiagnosis.tsx`: 재생 위치가 간격(기본 2초, 선택 1초 등) 칸에 들어설 때마다 장면 1장을 긴 변 1920px 이하 JPEG 로 캡처해 기존 `/v1/web/diagnose` 로 보냄(요청 1건씩, 늦으면 칸 건너뜀, DB 기록 유지 — 사용자 결정). 영상 위 배지(등급 색·잔여 %·"N초 장면 기준"·추이=최근 5칸 중앙값), 칸별 등급 띠(누르면 이동·결과 카드), 현재 ROI 윤곽(운영 키 있을 때). 멈춤 게이트 G0·G1·G3·G4·G5 는 중지 + 차단 블록. 사람 박스·발 위치는 그리지 않음(사용자 결정). 백엔드·계약 변경 없음. `pages/Diagnose.tsx` 에 '재생하며 실시간 진단' 토글, `tests/liveVideo.test.ts`. SD_02 S5 문서 반영은 미정(사용자 확인 필요)
- [X] T086 [US1] 실시간 진단 표시 안정화(사용자 요청 — 판독 불확실 과다·사람 변화 없이 % 흔들림) — `LiveVideoDiagnosis.tsx` `stableSeries`: 표시값 = 최근 5칸 중앙값이 같은 방향으로 2칸 연속 달라질 때만 갱신(1%p 이하 변화 무시), 등급 = 기준값(운영 키로 조회) 있으면 안정값에 서버 `map_level` 과 같은 규칙, 없으면 창 안 최근 확정 등급. 판독 불확실 칸도 값은 쓰되 창의 절반 초과면 "참고"·띠 흐리게(FR-09 유지). 배지에 이번 장면 값·인원 병기. 서버 판정·계약 변경 없음. 근본 원인(검출 conf 0.25·평균 신뢰도 전체 박스 계산)은 실제 영상 실험 후 결정 대기

- [X] T104 (구 T095 — 번호 중복 정리 2026-09-29) [T073 후속] 앱 전체 PostgreSQL 호환 — `tests/conftest.py` 에 `PG_APP_URL`(앱 테스트 전체를 PostgreSQL 로), 시각 비교·파싱 11곳 `db.iso()`, 읽기 경계 `db.q`·`db.q1` ISO 문자열 통일, `db.insert()` RETURNING, 이식본 `BIGSERIAL` 2곳·뷰 `CURRENT_TIMESTAMP AT TIME ZONE 'UTC'` 4곳·`uc_ref` 40, `expired_today` 범위 비교, `repo/ops.py` 자리표시자. 결과 53/91 → 91/91. SD_03 §15-2

## 구현 기록 (2026-09-29 오후 — D8 정정·PostgreSQL 앱 호환)

- D8 정정: 사용자가 "승강장 카메라가 아니라 열차(버스) 안 카메라"라고 확인 → 승강장 실측 거부 복원 + `train_in` 추가(T079 갱신). 운영 cv.db 에 마이그레이션 적용 확인(CHECK 확장, 트리거 복원, integrity ok).
- PostgreSQL: 앱 테스트 91/91 (PG_APP_URL), DDL 테스트 2/2 (PG_TEST_URL), SQLite 95/95, vitest 11.

## Phase 10: 혼잡도 = 인원 ÷ 차량 전체 정원 (2026-09-29 사용자 결정, research R22)

- [X] T087 [R22] 산출 방식 전환 — `predict.compute_occupancy`(인원 세기 기준 이상 · 발 위치 ROI 안 인원 ÷ 정원, 100 상한 + `over_capacity`, 정원 없음 = 산출 불가), `services/diagnosis.py`(평균 신뢰도·겹침은 셈에 든 사람만, `count_conf_min` 은 등급 기준 판본에서, 정원 없음 = 판독 불확실 + unknown/`capacity_missing`), `services/measurement.py` 차량 합산 = 카메라별 인원 합 ÷ 정원(`persons_sum`·`capacity` 기록), 응답 `capacity`·`over_capacity`·`persons_sum`, S3 인원 세기 기준 행 + «1분 뒤», C3 결과 카드 "인원 / 정원명 · 혼잡 %", S5 실시간 배지 = 안정 인원(T086 을 인원 기준으로), S6 합산 인원 표시, S2 입력란 안내. DDL(`threshold_policy.count_conf_min`, `vehicle_measurement.persons_sum`·`capacity`)·`db.py` MIGRATIONS, openapi 1.1.0, spec 4차(FR-04·FR-13e·Out of Scope 2·Assumptions 19), research R22, UC_00·01·02·04·07·08·10·11·13, SD_01·SD_02·SD_03(도면 재생성 — design/ 링크 70개 전부 복호 = 코드블록 확인), model_card·README·CLAUDE.md. 테스트: pytest 95(+2 PG skip), vitest 13
- [X] T088 [R22] ROI 전체 화면 (사용자 요청) — S2 ROI 편집기에 «전체 화면» 버튼(`0,0 4096,0 4096,4096 0,4096` — 진단 API 최대 프레임을 덮음, 백엔드 검증 변경 없음). 운영 DB 의 CAM-DEMO-01~03·CAM-S03 ROI 를 전체 화면 새 판본(#4~#7)으로 등록(이전 판본은 이력). 확인: zidane.jpg 0명 → 2/80명, bus.jpg 3/80명
- [X] T089 [US1] 실시간 현재 인원 (사용자 요청) — S5 영상 배지의 큰 숫자를 안정 인원에서 **현재 인원**(방금 분석한 장면의 서버 값, `currentOf`)으로, 안정 인원(최근 5칸 중앙값 + 2칸 확인)은 보조 한 줄로. 칸별 띠도 현재 값 기준(판독 불확실 장면은 흐리게 "참고"). 진단 간격 기본 2초 → 1초. 확인: 16초 영상에서 1초마다 갱신, 재생 위치 대비 약 0.3초 지연, 요청 14건 모두 200. vitest 18
- [X] T090 [R22] YOLO 입력 크기 640 → 1280 (사용자 요청, 밀집 장면 인원 과소) — `settings.MODEL_IMGSZ`(기본 1280, `.env` 로 조정), `YoloV8Detector.detect` 에 전달. 샘플 4개 1초 간격 비교(신뢰도 ≥0.4): 대합실 5.4→12.8명, 승강장 0.7→2.1명, 교차로 0.1→0.3명(사람 5px 수준, 검출 불가), 열차 차내 0.6→0.3명. 한 장 32→65ms. 서비스 경로 확인: 대합실 장면 4→10명(응답 80ms). 대합실 실제 인원은 약 100명 이상(육안) — 근본 해결은 머리 검출·군중 계수 모델 비교(다음 단계)
- [X] T091 [US1] 노트북 카메라 실시간 진단 (시연, 사용자 요청) — S5 입력 선택 «사진·영상 파일 / 노트북 카메라», `components/WebcamDiagnosis.tsx`(getUserMedia, 간격마다 1장 → `/v1/web/diagnose`, 요청 1건씩, 최근 60칸 흐르는 띠, 장면 미보관). 배지는 영상과 공용 `LiveBadge`. 운영 관리자는 화면에서 «정원 수정»(새 제원 판본, S2 와 같은 API). `CameraStatus.capacity`(현재 정원) 추가, S2 제원 입력란에 현재 정원 채움. 운영 DB 에 `CAM-WEBCAM`(bus_in, 유형 VT_WEBCAM, 정원 25 — 사용자 지정, ROI 전체 화면) 등록. 카메라는 보안 연결에서만 켜진다 → 시연은 https://p4.sumzip.com. 확인: 가짜 카메라(bus.jpg)로 1초마다 요청·배지 갱신, 정원 25→30 수정 즉시 반영 후 25 로 복원
- [X] T096 [R21-D5 변경] 실제 대전 BIS 전환 (사용자 요청 — 102번·충남대학교 시연) — `.env` `EXTERNAL_PROVIDER=bis`(백업 `backend/.logs/cv.db.bak-before-bis-20260929`). `fetch_bis_reference --routes 102` → `data/bis_routes.csv`·`bis_stops.csv`(노선 30300037, 정류소 91) 적재. 카메라 CAM-DEMO-01~03·CAM-WEBCAM 노선 R102 → 30300037, CAM-S03 → 30300037:42620(충남대학교). 가상 차량 매핑(1234·5678·9012) 해제 → CAM-DEMO-01~03 을 운행 중인 102번 대전75자9022·9011·9015 에 매핑(BIS 검증 verified). S7 노선·정류장 목록을 102번(30300037)·충남대학교 양방향(42620 중앙시장 방면 / 42600 수통골 방면)으로, S8 링크·S2 새 카메라 기본 노선도. 확인: 두 정류소 실제 도착 정보, 9022 실측 등록 → S7 "실측 여유 96%". 유효 시간 규칙의 노선 예외는 아직 R102:12(가상 노선) — 102번은 기본 10분 적용

## Phase 11: 차내 머리 검출 학습 (2026-09-29, 사용자 요청 — T090 후속 "머리 검출")

- [X] T092 [R22] 머리 검출 지원 — `predict.resolve_target`(가중치 클래스 이름 head 면 머리 모드, `settings.MODEL_TARGET=auto|person|head`), `anchor_points`(ROI 기준점: 몸 = 발 위치, 머리 = 박스 중심), `compute_occupancy(target=)`, `services/diagnosis.py`·`contract_self_check` 가 검출기의 `target` 전달. COCO 가중치는 동작 그대로. `tests/test_predict.py` 8건, model_card·`.env.example`. 스펙·설계 문서(FR-04 발 위치 문구, UC_13, SD_01) 반영은 사용자 확인 필요
- [X] T093 학습 파이프라인 `scripts/train/` — extract_frames(차내 영상 → 3초 1장), convert_public(CrowdHuman hbox·VOC → YOLO head), autolabel(+CVAT YOLO 1.1 zip), split(출처·카메라·날짜 그룹 단위), train(imgsz 1280·mps·max_det 1000), eval_count(프레임당 인원 MAE·SC-01·인원 세기 기준 추천), README(라벨링 규칙·서비스 반영 절차). `datasets/`·`runs/` gitignore
  - 1차 시험 학습 (2026-09-29): CrowdHuman val 4,370장을 그룹 분할(3,509/432/429) → yolov8n 에서 30 에폭 목표, 28 에폭째 오류 메시지 없이 중단(원인 미확인), best = 26 에폭 mAP50 0.787. `backend/models/head_crowdhuman_n1280.pt`(서비스 미적용).
    시험 429장(평균 22명/장) 프레임당 인원 MAE: 기존 person 7.67명(기준 0.40 이면 9.99, 편향 −9.7) → 머리 4.91명(기준 0.20, 편향 +0.6), SC-01(정원 80 가정) 81.8 → 86.5%.
    반면 차내 샘플 영상 8개(정답 없음)에서는 머리 모델이 비슷하거나 적게 셈 — 뒤통수·근접 큰 머리를 놓침. 차내 데이터 2차 학습 전에는 교체하지 않는다.
  - 수정: `single_cls=True` 가 클래스 이름을 'item' 으로 바꿔 서비스가 머리 모드를 못 알아봄 → 옵션 제거 + 학습 후 `set_class_names` 로 head 기록
- [ ] T094 차내 영상 확보·라벨링(기관 협조) → 2차 학습 → eval_count 로 기존 모델 대비 확인 → `MODEL_WEIGHTS`·`COUNT_CONF_MIN` 교체. CrowdHuman(CC BY-NC 4.0) 가중치의 운영 사용 가부 발주 측 확인
- [X] T097 [R21-D5 변경] 시연 카메라 BIS 차량 자동 재연결 (사용자 요청 — 시연 날 차량 번호 변경) — `POST /v1/admin/demo/bis-remap`(`services/demo_remap.py`, 관리자 키): 정류장 도착 예정 순 앞 N대에 CAM-DEMO-01~03 연결, 이미 그중 한 대면 그대로, 모자라면 변경 없음, 도착 정보 없음·연계 장애면 아무것도 안 바꿈. S8 8.1 에 정류장 선택(충남대학교 양방향) + «102번 운행 차량으로 다시 연결» 버튼 + 결과 표(KST), 8.1 표 차량을 현재 매핑으로 채움, 시연 모드 노선 예외 R102 → 30300037. 명령어 `scripts/demo_bis_remap.py`. `tests/test_demo_remap.py` 4건(유지·교체·멱등·장애 시 무변경·권한). 실 BIS 확인: CAM-DEMO-01 9022 → 9017(13:35 도착), 재실행 시 변경 0

## 구현 기록 (2026-09-29 오후 — 시연 예비 절차·T054 대체, 사용자 결정 ②③④)

- ② CLAUDE.md 를 실제 상태로: 한 프로세스·두 포트(R21-D1), 정본 R1~R22·명세 v1.2, 테스트 수, 해결된 미결(train_in·BIS).
- ③ 실제 BIS 시연 예비 절차: fixture 에 102번(30300037)·충남대학교 두 방면 복제본(`data/fixtures/transit.json`) — 전에는 fixture 로 되돌리면 카메라 노선(30300037)이 fixture 에 없어 S7 차량 없음·G9 거부였다. BIS 실제 호출 수 집계(`external/bis.calls_today`, 로그 `BIS call`, `ops-status.bis_calls_today`). quickstart §6-1 체크리스트·1분 복구 절차. `tests/test_demo_fallback.py`.
- ④ `scripts/demo_prepare.py`: 기본 노선·정류장 = 30300037·충남대학교, 매핑은 `demo/bis-remap`(도착 예정 순), 프레임은 샘플 영상, ROI 화면 전체. 임시 DB·프로세스 안 앱으로 fixture·실제 BIS 두 모드 PASS(BIS 호출 5회).
- 발견: 샘플 영상 최대 16명(대합실) → 정원 80명 차량은 "여유"만 나온다. 혼잡 등급은 S5 현재 프레임 진단에서 정원을 조정해 보여 주기로 함(사용자 결정, 작업 없음).
- 검증: pytest 112 통과(2 건너뜀).
- [X] T098 [R21-D1] 공개 API 산출물 주소 https://p4.sumzip.com/API (사용자 요청) — 웹 서버(9504) 프록시 `^/API(/.*)?$` → 9544, 백엔드 ASGI `PublicPrefix`(`/API` 를 떼고 root_path=/API) → Swagger `/API/docs` 가 `/API/openapi.json`·servers `/API` 를 써서 «Try it out» 도 `/API/v1/...`. `/API` → `/API/docs` 리다이렉트. 9544 직접 접근(`http://192.168.0.19:9544/docs`)은 그대로. `tests/test_public_prefix.py` 2건. 확인: 도메인으로 /API(307→docs)·/API/docs(엔드포인트 39)·/API/openapi.json·/API/v1/readiness·/API/v1/diagnose(키 200 / 무키 401), 브라우저 Try it out 요청 URL = /API/v1/readiness
- [X] T095 [G1] 이용자/관리자 인증 (사용자 요청, UC_00 §4 액터·UC6 E3·UC7 E2·UC8 E2·UC11 E2·UC12 E4) — 이용자(본 웹서비스 이용자·연계 시스템, 호출 키)는 S0·S5·S6·S7·S9 전부, 운영 관리자(관리자 키)는 + S1~S4·S8·변경 버튼. 백엔드: 이용자 조회 경로 `routers/reference_public.py`(`/v1/reference/cameras[/{id}[/roi]]`·`/threshold`·`/ops-status`, 호출 키), `/v1/auth/whoami`(role admin|caller). 프론트: 관리자 키를 빌드에서 제거(`VITE_ADMIN_KEY` 폐지) → 헤더 «관리자 로그인»(`stores/auth.ts`, 서버 확인 후 이 브라우저에만 저장, 서버 거부 시 자동 로그아웃), 운영 관리자 경로는 `AdminGate`(G1 차단 + 로그인 폼), 이용자 화면(S0·S5·S5 관제·S6·영상·웹캠·시연 칩)은 조회 경로로. 키 교체: 개발 기본값(changeme-*) 폐기, `backend/.env` 는 sha256 해시만, 새 관리자·호출 키는 `backend/.logs/ADMIN_KEY.txt`(gitignore, 600), `.env` 백업 `backend/.logs/*.bak-before-t095`. 테스트는 고정 키(conftest), 스크립트는 `CV_ADMIN_KEY`/`CV_API_KEY`. 매뉴얼 예시 키 → 자리표시. 테스트: pytest `test_auth_roles.py` 3, vitest `auth.test.tsx` 3 — 전체 117 / 21. 브라우저(도메인): 이용자 메뉴·S5 카메라 목록·/admin 차단, 옛 키 거부, 새 키 로그인·새로고침 유지·로그아웃, 이용자 화면의 관리자 API 호출 0

## 번호 정리 (2026-09-29, 사용자 요청)

여러 세션이 같은 번호를 따로 붙여 중복이 생겼다. 차내 학습 묶음(T092 머리 검출 · T093 학습 도구 · T094 차내 학습)은 이어진 번호라 그대로 두고, 나머지를 T095 이후로 옮겼다. 코드·문서의 참조도 함께 바꿨다.

| 옛 번호 | 내용 | 새 번호 |
|---|---|---|
| T085 (2번째) | 앱 전체 PostgreSQL 호환 | T095 |
| T092 (Phase 10) | 실제 대전 BIS 전환 | T096 |
| T093 (Phase 11 뒤) | 시연 카메라 BIS 차량 자동 재연결 | T097 |
| T094 (마지막) | 공개 API 주소 `/API` | T098 |

다음 새 태스크는 T099 부터.
- [X] T105 (구 T096 — 번호 중복 정리) [UC15] API 안내 v1.1 (사용자 요청 — 매뉴얼·가이드라인·엔드포인트 점검) — 카탈로그 9 → 19 항목으로 **실제 엔드포인트 45개 전부** 수록(이용자 조회·whoami·게이트 요청·웹 변환·샘플·관리 매핑·검증·운영 상태·모델·시연 재연결), 결과 설명을 R22(인원/정원·over_capacity·persons_sum)로. 가이드라인 v1.1(공개 주소 /API·키·R22 계산·표시 권장·호출 빈도·실제 BIS 식별자·UTC), 매뉴얼 v1.1(p4.sumzip.com/API 기준 curl — 102번·충남대학교, 응답 예시, 웹 변환, G1 대처, 관리자 로그인), 모델 카드(입력 1280·정원 미등록·밀집 과소). `test_guide_contract_g17` 에 역방향(실제 엔드포인트 ⊆ 카탈로그) 추가. 확인: 매뉴얼 예시 5개 공개 주소로 실행, /API/v1/api-guide v1.1 published, pytest 117
- [X] T106 (구 T098 — 번호 중복 정리) [UC15] 매뉴얼 부록 "엔드포인트 전체 목록 (45개)" (사용자 요청 — 이용자가 알아야 할 목록) — A. 연계·이용자(호출 키) 17 / B. 운영 관리자 전용(관리자 키) 28, 번호·방식·주소·하는 일. `test_manual_appendix_lists_every_endpoint`: 부록 표 = 실제 명세(방식+주소) 정확히 일치, 관리자 키 필요 경로는 B 절에만. 실서버 확인: B 13개 호출 키로 401, A 7개 200
- [X] T099 [UC2] 이용자는 카메라 번호·내부 코드 없이 버스 상태를 본다 (사용자 요청) — `GET /v1/reference/routes?q=`(노선 번호 → route_id, route_no), `GET /v1/reference/stops?route_id=&q=`(정류장 이름 검색, 방향 표시 제외 매칭), `GET /v1/vehicles/{vehicle_id}`(버스 번호 → 최신 유효 실측, 없으면 no_measurement), next-vehicle·vehicles 에 `persons_sum`·`capacity`. **대전 BIS 전체 적재**: 노선 141 · 정류장 10,533(받기 6.5초 + 적재 1.6초, API 호출 약 143회), 같은 이름 양방향 정류장은 "(다음 정류장 방면)" — 충남대학교 42620 = (홈플러스유성점 방면), 42600 = (온천교 방면). 백업 `backend/.logs/cv.db.bak-before-full-bis`. S7: 노선(141)·정류장 목록을 API 로(코드 숨김), 이름 찾기·모든 노선에서 찾기, "인원 / 정원" 열, 버스 번호로 조회. 헤더 검색 = 정류장 이름 또는 버스 번호. 매뉴얼 절차를 A 보는 쪽 / B 보내는 쪽으로, 부록 48개, 카탈로그 21. 테스트 `test_user_lookup.py` 2 — pytest 120, vitest 21. 브라우저(도메인) 확인
- [X] T100 [UI] 화면 시각 = 한국 시각 (사용자 요청) — 서버 저장·API 는 UTC 그대로, 화면 표시·입력만 KST. `api/client.ts` `kst`·`fmtTime`(KST)·`hhmm`·`kstDate`·`kstInputToUtc`·`kstNowInput`. S7 도착·실측 시각, 헤더·S0 시연 종료, 요청 보냄 시각, 웹캠·영상 장면 시각, S5·S6 촬영 시각 입력, S2 유효 시작일, S3 적용 시작일·시연 종료·«1분 뒤», S8 종료 예정 입력. S3 노선 예외 기본값 R102 → 30300037. `tests/time.test.ts` 2(날짜 넘김 포함) — vitest 23. 브라우저: 한국 14:33 에 "6분 후 14:39"
- [X] T101 [UI·BIS] 메뉴 재구성 + S7 "안 됨" 원인 조치 (사용자 요청) — 메뉴: 이용자 S0·S5·S7·S9 "API 활용 (개발자)", 운영 관리자 S1·S2·S3·S4·S6·S8 (`/measurements` → `/admin/measurements`, AdminGate). SD_02 §2-1·nav 도면 갱신(재생성). S7 원인 = 공공데이터포털 **429 일일 호출 한도 초과**(대전 BIS 버스 위치). 조치: `BisError("rate_limited")` + 5분 백오프(거부될 호출 안 함), S7 안내 "하루 호출 한도 초과 — 자정 초기화, 운영계정 신청", 오류 문구·httpx 로그의 serviceKey 가림. 버그 수정: rate_limited 가 `arrival_snapshot.source_status` CHECK 에 걸려 500 → DB 에는 unavailable 로 기록. 테스트 +3 — pytest 123, vitest 23
- [X] T102 [R21-D13 변경] S7 수동 조회 (사용자 결정 — BIS 일일 한도 보호) — «조회»·검색 결과 선택·시연 링크(노선·정류장 지정)일 때만 BIS 호출, 열어 두기만 하면 호출 0. 화면 시계로 "마지막 조회 N초 전"·"약 N분 후" 갱신(서버 호출 없음), 3분 지나면 "다시 조회" 권고, 노선·정류장 바꾸면 이전 결과 치움. 선택 «자동 갱신»: 30초 간격·5분 뒤 자동 꺼짐·가려진 탭이면 건너뜀. 서버 `BIS_POS_CACHE_S` 15 → 60초. research R21-D13·SD_02 §16-12 갱신. 브라우저: 35초 방치 0회, 조회 1회, 자동 갱신 +1회/30초, 정류장 변경 시 결과 치움
- [X] T103 [UI] S7 이름 "후속 차량 여유도" → "버스 조회" (사용자 요청) — 메뉴·경로 표시·홈·S5·S6·S8 버튼, 화면 제목(부제에 "후속 차량 여유도, UC2" 유지), 찾는 방법 두 갈래 «정류장으로 찾기»/«버스 번호로 찾기». 주소 `/next-vehicle`·API 이름은 그대로. tsc·vitest 23 통과. 남은 것: 브라우저 확인, SD_02·매뉴얼 화면 이름 반영, 대전 도시철도 API 조사 결과 반영
- [X] T107 [G1·RBAC] 역할 기반 인증 + 회원가입 후 API 키 (사용자 요청·결정 2026-09-29 — 키는 운영 관리자 승인 후 발급 · 웹은 아이디·비밀번호 로그인 · 이용자 화면은 공개 · 스스로 가입은 연계 개발자만) — 역할 = UC_00 액터: 운영 관리자 admin · 관제 담당자 controller · 연계 개발자 developer · 연계 시스템 integration(발급 키) · 본 웹서비스 webservice(설정 호출 키) · 이용자 public. 권한 표 `cv_api/rbac.py`(관제 담당자는 `/v1/admin` 읽기 6경로만). DDL 영역 H `account`·`api_key`·`auth_session`(SQLite·PostgreSQL, 비밀번호 scrypt·키·토큰 sha256 해시만). `/v1/auth/*` 8개(signup·login·logout·me·roles·keys 발급·목록·폐기) + `/v1/admin/accounts`·`api-keys` 5개 → 계약·카탈로그·매뉴얼 부록 64개(가이드 v1.2). 인증 순서 Bearer 세션 → 관리자 키(최초 설정용) → X-API-Key(설정 키·발급 키 `cvk_`). 발급 키 호출의 집계 호출 주체 = `아이디:키이름`. 정지·역할 변경은 세션을 끊고, 정지 계정의 키는 거부. 웹: 헤더 로그인(아이디·비밀번호 / 관리자 키로)·`/signup`·`/my/keys`(원문 한 번만 표시)·`/admin/accounts`(승인·역할·정지·계정 만들기·키 폐기), 역할별 사이드바·`RoleGate`(관제 담당자 → 관제 뷰·카메라 현황). 테스트 `tests/test_rbac.py`(4)·`frontend/tests/auth.test.tsx`(10), 9504 프록시로 가입→승인→로그인→발급→호출→폐기 실측 통과. 도면 반영은 다음 `/sad`
- [X] T108 [G1·RBAC — T107 개정] 로그인 필수 + 가입 = 일반 사용자 + API 키 승인 (사용자 요청 2026-09-29) — 사이트에 들어오면 로그인 화면(`pages/Login.tsx`, 주소 유지 — 로그인하면 그 화면), 로그인해야 기본 기능. 서버도 로그인 토큰·승인된 키·서버 설정 키 없이는 401(공개: 가입·로그인·역할 표·readiness·api-guide). 웹 빌드에서 호출 키(`VITE_API_KEY`) 사용 제거 — 모든 요청에 Bearer. 역할 developer(연계 개발자) → **user(일반 사용자)**, 가입 즉시 active(계정 승인 없음). API 키는 신청 시 `status='pending'`(원문은 신청 응답에서 한 번만) → 운영 관리자 승인 `PATCH /v1/admin/api-keys/{key_id}`(active·rejected) 뒤 사용, 승인 전 403 `KEY_PENDING`·반려 403 `KEY_REJECTED`, 운영 관리자 본인 신청은 즉시 승인. DDL 영역 H: role CHECK user, `api_key.status·approved_at·approved_by`. 기존 DB 는 `db.py` 마이그레이션(`_account_role_user` + MIGRATIONS — 이전 키는 active 로 간주)으로 실DB 계정 3·키 2 보존 확인. 계약·카탈로그·매뉴얼 부록 65개(가이드 v1.3). 화면: 로그인 화면·회원가입(가입 즉시 로그인)·내 API 키(상태 표시)·계정·키 관리(키 승인 대기 → 승인·반려). 테스트 backend 135 통과, frontend 32 통과, 9504·/API 경로로 미로그인 401 → 가입 → 기본 기능 200 → 키 신청 pending → KEY_PENDING → 승인 → 200 실측. 도면 반영은 다음 `/sad`
- [X] T109 [UC2·S7] 버스 조회 — 버스 번호 ↔ 정류장 서로 거르기 (사용자 요청 2026-09-29) — 버스 번호를 누르면 그 노선의 정류장만, 정류장을 누르면 그 정류장에 서는 버스 번호만. 새 조회 `GET /v1/reference/stops/{stop_id}/routes`(BIS `노선ID:정류소ID` 의 정류소 ID 가 같은 정류장 = 같은 방향, 고정 자료는 같은 이름, 노선마다 그 노선의 stop_id, 없으면 404 G3 STOP_NOT_FOUND, 권한 reference_read). S7 «정류장으로 찾기» 는 예전처럼 선택 상자(노선 · 정류장)를 쓰되 서로 거른다(사용자 요청으로 버튼 목록 시안 → 선택 상자) — 노선을 고르면 정류장 상자에 그 노선의 정류장만, 정류장을 먼저 고르면 노선 상자에 그 정류장에 서는 노선만. 노선을 안 골랐으면 정류장 이름 검색 결과를 정류소별로 하나씩(버스 n개), 둘 다 고르면 «조회». 고르면 반대쪽 검색어는 비움, «처음부터». 링크(route_id·stop_id·q)·시연 기본값(102번·충남대학교) 그대로. 계약·카탈로그·매뉴얼 부록 66개(부록 끝 «두 벌인 이유» 번호 정정). 테스트 `test_user_lookup.py::test_routes_at_stop`, `frontend/tests/busLookup.test.tsx`. 실서버: 충남대학교(홈플러스유성점 방면) → 102·106·113·706번
- [X] (도면 반영 SAD 2026-09-29, 첫 전수 대조) — T088~T103 구현을 UC_00·01·02·06·07·08·11·12·13·14·15, SD_01, SD_02, SD_03 에 반영(도면 12개 재생성). 계약 openapi.yaml 은 CLAUDE.md 규칙상 반영 제안만. 이력 `design/SAD_이력.md`, 기준 `.sad/state.json`
- [X] T110 [G1·RBAC] 권한 매트릭스 S10 (사용자 요청 2026-09-29 — 사용자 유형별 기능 활용 여부를 매트릭스로 체크) — `rbac.PERMISSIONS` 는 기본값, 운영 관리자가 바꾼 칸만 `role_permission`(db.py 가 생성) 에 저장 → 유효 권한 = 기본값 + 바꾼 칸. `auth.require_perm`·`require_perm_caller` 로 실제 차단: diagnose(`/v1/diagnose`)·measure(`/v1/measurements`)·next_vehicle(`/v1/next-vehicle`·`/v1/vehicles/*`)·reference_read(`/v1/reference/*` — ops-status·whoami 제외)·own_keys(`/v1/auth/keys`)·control_view(관제 읽기 6경로). 꺼진 칸 → 403 ROLE_FORBIDDEN. 잠금: 운영 관리자 열·admin/accounts 행(422 RBAC_LOCKED), 모르는 권한·역할 422 RBAC_UNKNOWN. `GET/PUT /v1/admin/rbac` → 계약·카탈로그·매뉴얼 부록 68개. 행동 변화: 표에 이미 적힌 대로 일반 사용자의 실측 등록(measure)은 이제 403. 웹 `/admin/rbac`(체크박스 표·열 일괄·저장 전 변경 칸 강조·기본값과 다른 칸 점·기본값으로·되돌리기). 테스트 `tests/test_rbac_matrix.py`(5)·`frontend/tests/rbac.test.tsx`(3) — pytest 140, vitest 35. 남은 것: `role_permission` 을 cv_ddl.sql(·postgres) 영역 H·SD_03 에 반영(승인 필요), 사이드바·RoleGate 를 매트릭스 권한 기준으로(지금은 역할 기준), 브라우저 확인

- [X] T111 [T094 1차] 머리 검출 1차 가중치 운영 적용 (사용자 요청, 2026-09-29 17:20) — `backend/.env` `MODEL_WEIGHTS=models/head_crowdhuman_n1280.pt`(CrowdHuman 26에폭 mAP50 0.787, 클래스 head → `MODEL_TARGET=auto` 로 머리 모드·박스 중심 기준), `COUNT_CONF_MIN=0.2`(평가 최적값). 백업 `backend/.logs/env.bak-before-head-model-20260929-1719`, 되돌리기 = `MODEL_WEIGHTS=models/yolov8n.pt` + `COUNT_CONF_MIN` 줄 삭제 후 재기동. 확인: readiness ready(적재 0.8s), 샘플 대합실 27 → 39명·열차 차내 2 → 2명·승강장 5 → 1명(정답 없는 샘플). 테스트가 운영 .env 기준값을 읽지 않게 `tests/conftest.py` 에 `COUNT_CONF_MIN=0.4` 고정 — pytest 141 통과. 주의: 등급 기준 판본 2·3번(count_conf_min 0.4, 적용 시작 2026-09-30 04:21·04:51 UTC)이 적용되면 인원 세기 기준이 0.4 로 돌아간다. CrowdHuman CC BY-NC 운영 사용 가부 미확인
- [X] (도면 반영 SAD 2026-09-29 17:49, 증분) — T107~T111·카메라 전원 S2b 를 UC_00·01·02·03·06·07·08·10·11·12·13·14·15, SD_01(P2 2.6·P10 신설·G1 개정), SD_02(§13A 신설, 도면 4장 신규), SD_03(영역 H ERD·명세), DDL 정본에 `role_permission` 추가, SD_04 메모에 반영. 도면 10개 재생성·79개 어긋남 0. 이력 `design/SAD_이력.md`

## Phase 14: 2026-09-30 미해결 정리 (사용자 결정 — memory decisions-2026-09-30)

- [X] T112 [UC6·G4] 카메라 전원 관리 S2b (2026-09-29 구현, 번호만 소급 부여) — `services/camera_power.py`: off(기본)면 그 카메라의 진단 요청 거부(G4 `CAMERA_POWER_OFF` 409), on 이면 `poll_interval_s` 마다 `frame_source`(스냅샷 URL 또는 `sample:<파일>`)에서 1장 불러와 P5 와 같은 경로로 자동 진단, 프레임 미저장(FR-11). `GET /v1/admin/camera-power`(호선·차량·칸·운행 상태·정원·현재 인원·밀집도·동작여부), `POST /v1/admin/cameras/{id}/power`. DDL `camera.car_position·powered·frame_source_url·poll_interval_s`. 웹 `/admin/cameras`(Cameras.tsx, 지하철·버스 표). 웹캠 스트림을 App 수준 provider 로. 테스트 `tests/test_camera_power.py`. 도면 반영은 SAD 2026-09-29 17:49
- [X] T113 [UC8·G8] 예약 등급 기준 판본 사고 조치 — 판본 2·3번(count_conf_min 0.4, 09-30 13:21·13:51 KST 적용 예약, 작성 op1)을 취소(DB 백업 `backend/.logs/cv.db.bak-before-cancel-thr-2-3-20260930-0945`, 참조 진단·검증 0건 확인 후 삭제) — 머리 모델 기준 0.2 유지. 원인: S3 적용 시작일 기본값이 "내일 이 시각"(`plusDays(1)`)이라 날짜를 안 고치고 저장하면 하루 뒤로 예약됐고, 인원 세기 기준 입력칸 기본값·"현재" 칸이 0.4 고정 문구였다. 수정: 기본값 "1분 뒤", 새 값 입력칸을 실제 적용값으로 채움, "현재" 칸 = 판본 값 또는 "(설정 기본값)", 예약 판본 경고, 저장 후 "예약됨 — ○○부터 적용" 안내. API: 판본 목록 `is_scheduled`, `/v1/reference/threshold` `count_conf_min_effective`(openapi 반영). 테스트 `test_threshold_scheduled_flag_and_effective_count_conf`
- [X] T114 [SD_03] `role_permission` 이중 정의 정리 — 정본 DDL(cv_ddl.sql·postgres 영역 H)에만 두고 `db.py` 의 CREATE 제거(`init_db` 가 DDL 을 먼저 적용). 메모리 DB 로 표 생성 확인, pytest 143 통과
- [X] T115 [BR-CV-31·FR-18] 모델 판본 기록 결함 수정 + 모델 카드 — 기동 시 `model_package` 를 늘 `models/model_package.json`(yolov8n)에서 읽어, T111 로 머리 모델을 적재한 뒤에도 진단 51건이 판본 1(yolov8n)로 기록됐다. `services/ops._weights_record`: 가중치 옆 설명 파일 `models/<이름>.json` → 없으면 model_package.json(같은 파일일 때만) → 그 밖엔 파일 sha256 으로 판본 구분. `models/head_crowdhuman_n1280.json` 추가(라이선스 AGPL-3.0 + CrowdHuman CC BY-NC). 재기동 뒤 판본 2(head, weights-sha256:d740367868d50137) 로 기록 확인. 테스트 `tests/test_model_package.py`(2). 모델 카드 `guide/model_card.md` 를 운영 모델(머리 검출)·평가·차내 미검증·라이선스로 갱신. 과거 51건 정정은 사용자 결정 대기
- [X] T116 [G1·RBAC] 화면 접근 기준 통일 — 사이드바·화면 게이트는 이미 유효 권한(PermGate, T110 이후) 기준이었음을 확인. 남은 역할 기준 `useAdmin()`(웹캠 «정원 수정»)을 권한 «운영 관리»(`hasPerm("admin")`, 잠긴 행이라 운영 관리자만) 기준으로, 쓰이지 않는 `hasAdmin` 제거. T110 의 "남은 것: 사이드바·RoleGate" 는 해소
- [X] T117 [SD_03 §16 17] 계정 역할·상태 변경 이력 — 표 `account_change`(field role|status, old·new, changed_at, changed_by, 정본 DDL 2벌), 계정 생성·가입(`signup`)·운영 관리자 변경 때 실제로 바뀐 값만 기록, `GET /v1/admin/accounts/{id}/changes`(계약·카탈로그·매뉴얼 부록 69개), 계정 관리 화면 «이력». 보관·파기 기간은 Q4 와 함께(미정). 테스트 `tests/test_account_changes.py`(2)
- [X] (도면 반영 SAD 2026-09-30 10:10, 증분) — T113~T117·UC16~18(R23) 을 SD_01(§1-3·§3 1.1·§6 3.2/3.4·§12A 10.5/10.6/10.8·§15-1), SD_02(§2-1·S0·S3·§13A·sd02_keys·§16 16/17), SD_03(ERD H `account_change`·§9-5/9-6·§15 34 테이블·§16 17·§17-1) 에 반영. 도면 2개 재생성·85개 어긋남 0. 기존 불일치 SD_01 10.6 G8→G2 정정. 이력 `design/SAD_이력.md`
- [X] (도면 반영 SAD 2026-10-01 10:14, 증분) — 2026-09-30 웹 화면 정리(홈 = 버스 조회·SB·진행 레일·S0·S5 관제 뷰·S1 연동·S2 CSV/이력·S3 시연 스위치·S7 버스 번호·S8 일괄·S9 카탈로그/시험 호출 폐지)·S4 사람이 센 인원(BR-CV-36)·API 점검 A3/A9/D5/D6 을 UC_00·02·03·04·10·12·14·15, SD_01(1.5·1.6·3.1·4.1·4.7·8.3·9.4·G0), SD_02(§2·§4~§13A·§14·§16 19~22·§17), SD_03(화면 사상 표), SD_04(메모) 에 반영. 도면 15개 재생성·85개 어긋남 0. 계약 `openapi.yaml` 반영 제안 미처리(specs/ 사용자 확인). 이력 `design/SAD_이력.md`
