# Specification Quality Checklist: 대전 대중교통 비식별 군중 밀집도·잔여 공간 진단 서비스

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-23
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

**Iteration 1 (2026-09-23)** — `Intent-Specify.md`를 원천으로 초안 작성. Intent가 구현 수단(모델·서빙 프레임워크·스키마 라이브러리·계층 파일명)을 상세히 지정했으나, 명세에는 그 수단이 보장해야 할 **행동**(첫 요청 지연 없음, 규격 외 반려, 재현성, 자동 검증)만 기술하고 수단 자체는 Assumptions 9번에 계획 단계로 이관했다.

합리적 기본값으로 해소한 항목: 입력 단위(정지 프레임), 혼잡 등급 경계값(50%/20%), 신뢰도 기준(0.6), p95 응답 목표(2초), ROI 등록 주체(운영 관리자), 정확도 목표(±10%p·85%).

**미통과 2건** — 모두 `[NEEDS CLARIFICATION]` 2개에 기인하며, 사용자 응답 대기 중:

- Q1 (FR-13) 후속 차량 예상 혼잡 등급의 산출 근거 — 범위와 데이터 연계 깊이가 달라짐
- Q2 (FR-16) 접근 정책 — Intent가 명시한 오용 리스크(사설 유상운송 악용)에 대한 대응 수준이 달라짐

FR-13, FR-16이 확정되면 "All functional requirements have clear acceptance criteria" 항목도 통과한다.

**Iteration 2 (2026-09-23)** — 사용자가 Open Questions Q1~Q4에 응답하여 전 항목 통과. 응답 내용은 spec의 `Clarifications › Session 2026-09-23`에 기록.

- Q1 → 실측 프레임 한정. FR-13 재작성, FR-13a(후속 차량 프레임 제출·실측 유효 시간) 신설, S2·AS2 수정, AS2-b(실측 없음) 추가, Assumptions 8 갱신, NextVehicleEstimate 엔티티 근거 유형을 실측/실측 없음/조회 불가로 변경
- Q2 → 시민·기관 모두 수치(%)까지 제공. FR-16을 "호출 주체 식별은 하되 정보 차등 없음"으로 확정, Assumptions 12 추가
- Q3 → 팀이 촬영 가능한 장소. Assumptions 11 추가, 구체 지점은 계획 단계 이후
- Q4 → 운영 시 기관 정책 준수. Assumptions 6 갱신

**잔여 리스크 (차단 요인 아님)** — Q2 결정으로 정보 차등이 사라져 Intent가 지적한 오용(사설 유상운송의 승객 선점) 리스크를 접근 정책으로 막지 않는다. 대응은 추정치 고지(FR-10)와 낙인 방지 문구 가이드(OR-03)뿐이므로, OR-03을 계획 단계에서 필수로 승격할지 검토가 필요하다. Q1 결정으로 후속 차량 등급은 해당 차량의 프레임이 실제로 제출될 때만 제공되므로, 파일럿 촬영 계획(Q3)에 "연속 두 차량 촬영"이 포함되어야 AS2를 검증할 수 있다.

**Iteration 3 (2026-09-23)** — 유스케이스 설계(design/)에서 제기된 미해결 4건에 사용자가 응답. `Clarifications › Session 2026-09-23 (2차)`에 기록하고 전 항목 재검증 통과.

- 판독 불확실 실측 인정 → FR-13a 보강, AS2-c 추가, Assumptions 13
- 차량 식별자 직접 등록(목록 선택·CSV·검증) → FR-13c 신설, Camera 엔티티 보강, Assumptions 14
- 유효 시간 = 노선별 배차 간격 기반 → FR-13b 신설, ValidityPolicy 엔티티 추가, Assumptions 8 갱신
- 시연 전 사전 제공 프레임 → FR-13d 신설, S7·AS2-d 추가, Assumptions 15. 시연 모드는 응답에 표시되어 실운영 실측과 구분됨
- 차량당 카메라 다수(가변·고장 가능) → FR-13e 신설(제공 카메라만 ROI 면적 가중 합산, 커버리지·`partial_coverage`), FR-13c 다대일 매핑 허용, AS2-e·E13 추가, VehicleMeasurement 엔티티, Assumptions 16(시각 창 1분 기본값)
- CSV 열 구성(첫 행 열 이름, 필수 카메라·차량 식별자, 선택 차량 유형, 이름으로 식별)과 시연 모드 자동 해제(기본 2시간) → FR-13c·FR-13d 보강, Assumptions 17·18, Q10·Q11

**상태**: `/speckit.plan` 진행 가능.
