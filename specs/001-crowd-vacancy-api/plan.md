# Implementation Plan: 대전 대중교통 비식별 군중 밀집도·잔여 공간 진단 API

**Branch**: `001-crowd-vacancy-api` · **Date**: 2026-09-28 · **Spec**: `/Users/pioneer4/project2610/specs/001-crowd-vacancy-api/spec.md` (v1.0 + Clarifications 1·2차 + 개요 §0 추가 원천)
**Input**: `Intent-Plan.md`(Docker 미사용, 웹스택 선택지), `Intent-Specify.md`(도구 생태계), `design/`(UC_00~15, SD_01 프로세스, SD_02 UI/UX, SD_03 DB + cv_ddl.sql, style-guide)

## Summary

관제 영상 프레임 1장을 받아 YOLOv8n 으로 사람 객체를 비식별 검출하고, ROI 다각형 안에 발을 딛고 선 사람 수를 차량 전체 정원으로 나눠(research R22 — 2026-09-29 개정, 이전: × 표준 발자국 면적) 잔여 탑승 가능 비율(%)·혼잡 등급·인원수를 산출하는 FastAPI 서버와, 그 결과를 운영·시연 화면(S0~S9)으로 보여 주는 React 웹서비스를 Docker 없이 구성한다. 판독 기준 미달 시 확정값 대신 `warnings` + `uncertain` 을 내고, BIS·배차 정보와 연계해 후속 차량 여유도를 "실측 / 실측 없음 / 조회 불가"로 안내한다. 스키마는 SD_03 의 `cv_ddl.sql`, 게이트 18개는 SD_02 사상표를 HTTP 상태와 뷰 판정으로 옮긴다.

## Technical Context

| 항목 | 값 | 근거 |
|---|---|---|
| Language/Version | Python 3.11 (3.9.6 호환) · TypeScript 5 / Node 20 LTS | research R1 |
| Backend | FastAPI 0.115+, Pydantic v2 (`extra="forbid"`), Uvicorn, lifespan 웜업 | Intent-Specify 핵심 이네이블러 |
| Vision | Ultralytics YOLOv8n (`yolov8n.pt` — `github.com/MaxTheTechy/yolo` 의 person 검출 접근법, Clarifications Q12 확정), torch, opencv-python-headless, numpy, shapely(발 위치 ∈ ROI 판정) — 계산은 인원 ÷ 차량 전체 정원(research R22, 이전 R20 발자국 면적) | research R3·R20·R22 |
| Frontend | React 18 + TypeScript + Vite, 스타일은 `design/style-guide.html` 토큰(나눔바른고딕) | Intent-Plan 선택지, SD_02 |
| Storage | SQLite(개발·시연) / PostgreSQL 15(운영), SQLAlchemy Core, DDL 정본 `design/cv_ddl.sql` | research R2, SD_03 |
| External | 대전 BIS API(인증키), 대전교통공사 배차표 CSV, TAGO 기준 정보 CSV — `external/` 인터페이스 + `FixtureProvider` | research R12 |
| Testing | pytest + httpx TestClient, `bench.py`(p95), 계약-안내 대조 테스트(G17) | NFR-07, SC-03~06 |
| Target Platform | Linux/macOS 서버, 가상환경 실행. Docker 미사용 | Intent-Plan |
| Project Type | web (backend + frontend) | — |
| Performance Goals | `POST /v1/diagnose` p95 ≤ 2초(NFR-01), 기동 직후 첫 요청 ≤ 중앙값 1.5배(SC-04), 10장 일괄 ≤ 단건 10배(NFR-03) | spec |
| Constraints | 원본 프레임·개인 정보 미보관(FR-11), 판독 미달 시 확정값 금지(NFR-05), 외부 장애가 진단에 영향 없음(NFR-08), 정보 무차등(FR-16) | spec |
| Scale/Scope | 파일럿: 카메라 수십 대, 초당 수 건. 화면 10개, 경로 21개, 테이블 29 | SD_02·SD_03 |
| 미결 → 결정 | 요청 규격·판독 기준값·인증·엔드포인트·웹 범위·카메라 등록·재계산·연계 장애·CSV·보존 기간 등 19건 | research R3~R19 (NEEDS CLARIFICATION 0건 잔여) |

## Constitution Check

`.specify/memory/constitution.md` 가 **존재하지 않는다**. 헌법 대신 원천 명세의 비기능 요구(NFR-01~09)와 Intent 의 이네이블러를 게이트로 삼는다.

| 게이트 | 판정 | 근거 |
|---|---|---|
| 비식별·원본 미보관 (NFR-04, FR-11) | PASS | 스키마에 이미지·개인 정보 컬럼 없음(SD_03 D2). 진단 후 메모리 버퍼 즉시 해제, 모델 입력 사본 포함(BR-CV-09) |
| 정직한 실패 (NFR-05) | PASS | G6 을 CHECK + 트리거로 강제, 응답은 `uncertain` + `is_reference_only` |
| 재현성 (NFR-06) | PASS | 결과가 ROI·정원·경계·모델 판본 FK 를 가진다. 일괄은 단건 모듈 반복 호출(SD_01 §7-3) |
| 검증 가능성 (NFR-07) | PASS | pytest 가 규격 반려·경고 동봉·일괄 정합·G17 대조를 배포 전 확인 |
| 가용성 격리 (NFR-08) | PASS | `external/` 모듈 경계, 장애 시 `basis_type: unavailable` 로 200 |
| 투명성 (NFR-09) | PASS | 모든 응답에 `notice`, `/v1/api-guide` 에 모델 카드 |
| 단순성 | PASS (조건부) | ORM 미사용, 프로젝트 2개(backend/frontend). 웹서비스가 범위 미결(R8)이라 화면 10개 중 시연에 필요한 S0·S2·S3·S5·S6·S7·S8·S9 를 1차, S1·S4 는 2차 |
| Docker 미사용 | PASS | venv + npm. PostgreSQL 은 로컬 설치 |

**Post-design 재평가**: Phase 1 산출물(data-model, contracts, quickstart) 작성 후 위 판정에 변화 없음. 위반 0건.

## Project Structure

### Documentation (this feature)

```
specs/001-crowd-vacancy-api/
├── spec.md
├── plan.md              # 이 문서
├── research.md          # Phase 0 — 미결 19건 결정
├── data-model.md        # Phase 1 — SD_03 요약 + 계획 결정 반영
├── quickstart.md        # Phase 1 — 로컬 기동·시연 준비 절차
├── contracts/
│   └── openapi.yaml     # Phase 1 — 엔드포인트 20개
└── tasks.md             # /speckit.tasks 가 생성 (이 명령의 범위 밖)
```

### Source Code (repository root)

```
backend/
├── pyproject.toml
├── .env.example
├── bench.py                      # p95 계측 (NFR-01, SC-04)
├── cv_api/
│   ├── app.py                    # FastAPI 앱, lifespan(DDL 적용 → 가중치 적재 → 웜업 → 계약 확인 → readiness=ready)
│   ├── settings.py               # 규격·판독 기준값·키·외부 공급자 (research R4~R6)
│   ├── schemas.py                # Pydantic 계약 (extra=forbid) — openapi.yaml 과 1:1
│   ├── predict.py                # YOLOv8n person 검출 + 인원 ÷ 정원 계산 → 4필드 + 인원수 (BR-CV-28 어댑터, R22)
│   ├── quality.py                # 라플라시안·밝기·역광·occlusion 검사 → warnings (BR-CV-06·07·21)
│   ├── gates.py                  # G0~G17 판정 → HTTP 상태 + gate_event 기록 (SD_02 §14)
│   ├── db.py                     # SQLAlchemy Core, cv_ddl.sql 멱등 적용, SQLite/PostgreSQL
│   ├── repo/                     # 영역별 접근 (reference, policy, external, diagnosis, measurement, ops, guide)
│   ├── services/
│   │   ├── diagnosis.py          # P5 5.2~5.9 (P4·P6 이 재사용)
│   │   ├── measurement.py        # P6 6.2~6.6 합산 (BR-CV-27)
│   │   ├── next_vehicle.py       # P7
│   │   ├── policy.py             # P3, v_route_validity_minutes
│   │   ├── reference.py          # P2 (+ 카메라 등록 R9)
│   │   ├── verification.py       # P4 4.7
│   │   └── ops.py                # P0 0.2 지표, 0.4 시연 자동 해제, 0.5 준비 감시 (백그라운드 태스크)
│   ├── external/                 # ArrivalProvider / HeadwayProvider / FleetProvider + BisProvider, TimetableProvider, FixtureProvider
│   ├── routers/                  # readiness, diagnose, measurements, next_vehicle, admin, guide
│   └── tools/                    # fetch_model.py, load_reference.py
├── models/                       # yolov8n.pt, model_package.json (git 제외)
├── data/                         # routes.csv, stops.csv, timetable_line1.csv, fixtures/
├── samples/                      # 시연·테스트 프레임 (인터넷 자유 이용 자료, 출처 기재)
└── tests/
    ├── test_schemas.py           # G2 422, extra 필드 거부 (SC-05)
    ├── test_quality.py           # 블러·저조도 프레임 100% 경고 (SC-06)
    ├── test_diagnose.py          # G0~G7 상태코드, 판독 불확실, 산출 불가
    ├── test_batch.py             # 순서·단건 동일 (NFR-06, BR-CV-12)
    ├── test_measurement.py       # G10, 합산·커버리지, 시연 모드
    ├── test_next_vehicle.py      # basis_type 3값, 장애 격리 (NFR-08)
    ├── test_admin.py             # G8·G9, 판본·이력
    ├── test_guide_contract.py    # openapi.json ↔ api_endpoint 대조 (G17)
    └── test_ddl.py               # cv_ddl.sql 위반 29건 거부 (SD_03 검증 재실행)

frontend/
├── package.json, vite.config.ts, .env.example
├── src/
│   ├── api/                      # openapi.yaml 에서 생성한 타입 + 클라이언트
│   ├── styles/tokens.css         # design/style-guide.html :root 복사
│   ├── components/               # C1 Rail, C2 GateBlock, C3 ResultCard, C4 StatusBadge, C5 Readiness, C6 SourceDrawer, C7 RequestButton, C8 WarningChips, C9 HistoryPanel
│   ├── pages/                    # S0 Home, S1 Server, S2 Onboarding, S3 Policy, S4 Verification, S5 Diagnose(+Control view), S6 Measurement, S7 NextVehicle, S8 Demo, S9 ApiGuide
│   └── stores/                   # readiness·demo 폴링 (U6)
└── tests/                        # 컴포넌트 게이트 표현 (비활성 + 사유)

scripts/
└── demo_prepare.py               # 시연 준비 P1~P6 자동화 (HG/시연웹 §3)

design/cv_ddl.sql                 # 스키마 정본 (변경은 SD_03 갱신과 함께)
design/cv_ddl.postgres.sql        # 이식본 (신규 태스크)
```

**Structure Decision**: 웹 애플리케이션 구조(backend + frontend). Intent-Specify 가 지목한 `predict.py / schemas.py / app.py` 계층 분리를 `cv_api/` 최상위에 그대로 두고, SD_01 프로세스 P0~P9 를 `services/`, SD_03 영역 A~G 를 `repo/`, SD_02 컴포넌트 C1~C9·화면 S0~S9 를 `frontend/src/` 에 1:1 로 사상했다.

## Phase 0: Research — 완료

`research.md` 에 미결 19건을 결정했다. 핵심 발견 세 가지:

1. **모델은 `MaxTheTechy/yolo`(YOLOv8n person 검출 PoC)로 확정됐고, 4필드 계약은 내지 않는다.** 가중치와 검출 접근법만 가져오고 계약은 `predict.py` 어댑터가 구현한다(R3). 저장소 라이선스 없음·가중치 AGPL-3.0 은 배포 전 법무 확인.
2. **웹스택은 React + FastAPI, Docker 미사용**(R1). DB 는 SQLite → PostgreSQL, DDL 정본은 `cv_ddl.sql`(R2).
3. **게이트 → HTTP 상태 대응 확정**(R7). 출력 차단형(G6·G7·G12·G13)은 200 + 상태 필드, 처리 중단형은 4xx/503.

## Phase 1: Design & Contracts — 완료

| 산출물 | 경로 | 내용 |
|---|---|---|
| data-model.md | `specs/001-crowd-vacancy-api/data-model.md` | 29 테이블·14 뷰 요약, Key Entities 사상, 검증 규칙, 상태 전이 8종, 계획 단계에서 정본과 달라진 것 6건 |
| openapi.yaml | `specs/001-crowd-vacancy-api/contracts/openapi.yaml` | 경로 21개·오퍼레이션 25개(진단 4, 요청 보내기 1, 조회 1, 준비 1, 관리 17, 안내 1), 스키마 33개, 게이트 오류 응답 공통형 `GateError` |
| quickstart.md | `specs/001-crowd-vacancy-api/quickstart.md` | venv 기동 → 준비 상태 → 기준 정보·정책 → 진단·실측·조회 → 웹서비스 → 테스트·벤치 → 시연 리허설 |
| agent context | — | `.specify/scripts/bash/update-agent-context.sh` 가 저장소에 없다. 저장소에 `CLAUDE.md` 도 없어 이 단계는 **수행하지 않았다**. `/speckit.tasks` 전에 스캐폴드를 보완하거나 수동으로 만든다 |

### 상류 문서에 되돌릴 갱신 (계획 결정으로 생긴 것)

| 문서 | 갱신 내용 | 근거 |
|---|---|---|
| UC_00 §8.4 3, §8.3 7 | 카메라 등록 절차 결정 — UC6 앞 단계 A0 + `POST /v1/admin/cameras` | R9 |
| SD_01 §14 G3 | 해제 주체 '미정' → 운영 관리자 | R9 |
| SD_02 S2 2.1 | «카메라 등록» 버튼 추가. §16 3 해소 | R9 |
| SD_03 §16 1·3·4·5·8 | 모델 단위 %·경고 값 목록, G3, 재계산 안 함, 미검증 허용, 규격 값 | R3·R4·R9·R10·R11 |
| UC_13 §사후조건 (1) | 단위 % 확정, `crowding_level` 은 서비스가 산출(모델 원출력 없음) | R3 |
| UC_15 카탈로그 | 경로·메서드 채움 | R7 |
| spec.md Assumptions | 17(CSV 영문 열·UTF-8) 확정, 규격·판독 기준값 추가 | R4·R5·R13 |

## Phase 2: 이 명령의 범위 밖

`/speckit.tasks` 가 `tasks.md` 를 만든다. 권고 순서: ① `cv_ddl.sql` 적용·`test_ddl.py` → ② `schemas.py`·`quality.py`·`predict.py` + 단위 테스트 → ③ `services/diagnosis.py` + `/v1/diagnose`·`/v1/readiness` → ④ 관리 API(카메라·ROI·정원·매핑·정책) → ⑤ 실측·후속 차량 + `external/FixtureProvider` → ⑥ 프론트 S0·S5·S7·S8·S9 → ⑦ `demo_prepare.py`·`bench.py` → ⑧ S2·S3·S6 → ⑨ BIS 실연동·PostgreSQL 이식 → ⑩ S1·S4.

## Complexity Tracking

| 항목 | 이유 | 대안을 택하지 않은 이유 |
|---|---|---|
| 프로젝트 2개(backend/frontend) | Intent-Plan 이 프론트/백 분리 스택을 제시, 추가 원천 3항이 API 서버와 웹서비스를 구분 | 단일 서버 렌더링은 SD_02 의 상호작용(폴링·드로어·역할 뷰)을 구현하기 어렵고 선택지에 없다 |
| 뷰 14개를 DB 에 둠 | 게이트 판정·유도값의 단일 지점(SD_03 D3·D5) | 앱에서 계산하면 두 곳 계산 위험 |
| 외부 공급자 인터페이스 3개 | NFR-08 격리, 시연의 실시간 의존 제거 | 직접 호출은 시연이 발표 시각 운행에 묶인다 |
