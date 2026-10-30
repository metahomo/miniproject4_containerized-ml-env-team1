-- =====================================================================
-- cv_ddl.postgres.sql — PostgreSQL 15 이식본 (T009). 정본은 cv_ddl.sql (SQLite 검증본).
-- 치환: VARCHAR(19)→TIMESTAMP(UTC 저장 — 현재 시각은 CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 세션 시간대와 무관하게), 비교식 컬럼→CAST(… AS INTEGER)(SQLite 0/1 과 같게), MIN(a,b)→LEAST, CREATE VIEW IF NOT EXISTS→CREATE OR REPLACE VIEW, INTEGER PK→BIGSERIAL, strftime→CURRENT_TIMESTAMP, julianday→EXTRACT(EPOCH),
--       group_concat→STRING_AGG, RAISE(ABORT)→plpgsql 함수 + 트리거. 부분 UNIQUE 인덱스는 PostgreSQL 이 지원.
--       구현 단계 추가 컬럼 9개(roi_area_m2, footprint_m2, person_count, detector_kind ×2, load_seconds, R22 count_conf_min·persons_sum·capacity) 포함 — 정본과 같음.
-- 실행 검증: T073 통과(2026-09-29, PostgreSQL 16.2 — tests/test_ddl_postgres.py, PG_TEST_URL). 상세 SD_03 §15-2
--       비교식 컬럼 CAST 는 partial_coverage·demo_flag·excluded 만 — 나머지 비교식 열은 boolean (SD_03 §15-2)
-- =====================================================================
-- =====================================================================
-- cv_ddl.sql — 대전 대중교통 비식별 군중 밀집도·잔여 공간 진단 서비스
-- SD_03 데이터베이스 설계서 DDL 전문 (2026-09-28)
--
-- 규약
--  · 표준 SQL 로 쓴다. DBMS 전용 구문은 그 자리에 [DBMS 주석]으로 이유를 남긴다.
--  · 생성 순서는 FK 의존 위상 정렬 (참조되는 테이블이 먼저).
--  · 멱등: CREATE ... IF NOT EXISTS. 재실행해도 실패하지 않는다.
--  · 업무규칙 제약에는 BR-CV-nn 주석을 단다. CHECK 로 못 쓰는 규칙은 트리거 또는 [앱 책임] 주석.
--  · 시각 컬럼은 ISO-8601 문자열(UTC, 'YYYY-MM-DDTHH:MM:SS')로 둔다.
--    [DBMS 주석] 검증 DBMS 가 SQLite(3.51)라 TIMESTAMP 타입이 없다. PostgreSQL 등에서는 TIMESTAMP 로 바꾼다.
--  · 원본 프레임·개인 정보 컬럼은 어디에도 없다 (FR-11, NFR-04, BR-CV-09).
--  · 임계값·보존기간은 원천에 있는 값(신뢰도 0.6, 기본 10분, 시각 창 1분, 시연 2시간, SC 85%)만 쓰고
--    나머지(규격 값, 판독 기준값, 보관 기간)는 컬럼만 두고 상수를 비운다.
--
-- 검증 실측 (2026-09-28, SQLite 3.51.0):
--  ① 무오류 실행  ② 재실행(멱등)  ③ 위반 시도 거부 — cv_ddl_verify.sql 의 29건 전부 거부됨
-- =====================================================================

-- (PostgreSQL) FK 는 기본 활성 — PRAGMA 불필요

-- ---------------------------------------------------------------------
-- 영역 A. 기준 정보  (쓰기: 운영 관리자 / 생애주기: 온보딩 시 1회 + 판본 갱신)
-- ---------------------------------------------------------------------

-- 노선 · 정류장 기준 정보 (TAGO 참조, G11 판정 근거)
CREATE TABLE IF NOT EXISTS route (
  route_id      VARCHAR(40)  NOT NULL PRIMARY KEY,
  mode          VARCHAR(8)   NOT NULL CHECK (mode IN ('bus','rail')),
  route_name    VARCHAR(100),
  source        VARCHAR(20)  NOT NULL DEFAULT 'TAGO'
);

CREATE TABLE IF NOT EXISTS stop (
  stop_id       VARCHAR(40)  NOT NULL PRIMARY KEY,
  route_id      VARCHAR(40)  NOT NULL REFERENCES route(route_id),
  stop_name     VARCHAR(100),
  place_kind    VARCHAR(16)  NOT NULL CHECK (place_kind IN ('bus_stop','rail_platform'))
);

CREATE TABLE IF NOT EXISTS vehicle_type (
  vehicle_type_id VARCHAR(40) NOT NULL PRIMARY KEY,
  type_name       VARCHAR(100) NOT NULL
);

-- 카메라 (Key Entities Camera). place_type: 승강장 / 버스 차내 / 열차 차내(train_in — 2026-09-29 R21-D8 정정으로 추가. 실측 카메라는 모두 차량 안에 있다)
CREATE TABLE IF NOT EXISTS camera (
  camera_id       VARCHAR(40) NOT NULL PRIMARY KEY,
  place_type      VARCHAR(12) NOT NULL CHECK (place_type IN ('platform','bus_in','train_in')),
  route_id        VARCHAR(40) REFERENCES route(route_id),
  stop_id         VARCHAR(40) REFERENCES stop(stop_id),
  vehicle_type_id VARCHAR(40) REFERENCES vehicle_type(vehicle_type_id),
  roi_stale       INTEGER     NOT NULL DEFAULT 0 CHECK (roi_stale IN (0,1)),   -- BR-CV-17 ROI 검증 필요 표시 (P0 0.6)
  registered_at   TIMESTAMP NOT NULL,
  registered_by   VARCHAR(40),
  -- 카메라 전원 관리(S2b, 2026-09-29 사용자 결정): off(기본)면 진단 요청을 거부(G4 CAMERA_POWER_OFF), on 이면 서버가 주기마다 프레임 소스에서
  -- 1장을 불러와 진단한다. car_position = 열차 차내 카메라의 위치 칸(1부터). frame_source = 스냅샷 URL(JPEG/PNG) 또는 sample:<샘플 파일>
  car_position    INTEGER     CHECK (car_position IS NULL OR car_position >= 1),
  powered         INTEGER     NOT NULL DEFAULT 0 CHECK (powered IN (0,1)),
  powered_at      TIMESTAMP,
  frame_source    VARCHAR(500),
  poll_interval_s REAL        NOT NULL DEFAULT 10 CHECK (poll_interval_s >= 1)
);

-- ROI 판본 (Key Entities ROI). 이전 판본은 superseded_at 으로 이력 보관 (BR-CV-16, FR-15)
CREATE TABLE IF NOT EXISTS roi (
  roi_id         BIGSERIAL   PRIMARY KEY,
  camera_id      VARCHAR(40) NOT NULL REFERENCES camera(camera_id),
  polygon        VARCHAR(2000) NOT NULL,          -- "x,y x,y ..." 꼭짓점 목록
  vertex_count   INTEGER     NOT NULL,
  roi_area_m2    REAL,                            -- R20 실제 바닥 면적 (㎡)
  footprint_m2   REAL,                            -- R20 카메라별 발자국 보정
  area           REAL        NOT NULL,            -- <<derived 고정>> 다각형 면적. 합산 가중치(BR-CV-27)로 실측에 고정 참조되므로 저장
  effective_from TIMESTAMP NOT NULL,
  superseded_at  TIMESTAMP,
  created_at     TIMESTAMP NOT NULL,
  created_by     VARCHAR(40) NOT NULL,
  -- G8 (UC6 E1): 다각형 유효 — 꼭짓점 3개 이상, 면적 양수. 변 교차·프레임 범위는 [앱 책임] (좌표 기하 검사)
  CONSTRAINT chk_roi_polygon CHECK (vertex_count >= 3 AND area > 0),
  CONSTRAINT uq_roi_camera_from UNIQUE (camera_id, effective_from)
);

-- 차량 제원 판본 (Key Entities VehicleSpec). BR-CV-05·16
CREATE TABLE IF NOT EXISTS vehicle_spec (
  spec_id         BIGSERIAL   PRIMARY KEY,
  vehicle_type_id VARCHAR(40) NOT NULL REFERENCES vehicle_type(vehicle_type_id),
  capacity        INTEGER     NOT NULL,
  seat_count      INTEGER,
  source          VARCHAR(200) NOT NULL,          -- BR-CV-16 "차량 제원은 출처를 가진다"
  effective_from  TIMESTAMP NOT NULL,
  superseded_at   TIMESTAMP,
  created_at      TIMESTAMP NOT NULL,
  created_by      VARCHAR(40) NOT NULL,
  -- G8 (UC7 E1·E3): 정원 양의 정수, 좌석 <= 정원
  CONSTRAINT chk_spec_capacity CHECK (capacity > 0),
  CONSTRAINT chk_spec_seat CHECK (seat_count IS NULL OR (seat_count >= 0 AND seat_count <= capacity)),
  CONSTRAINT uq_spec_type_from UNIQUE (vehicle_type_id, effective_from)
);

-- 카메라 ↔ 차량 식별자 매핑 판본 (FR-13c, BR-CV-25). 한 카메라는 활성 매핑 1개 (E2)
CREATE TABLE IF NOT EXISTS camera_vehicle_map (
  map_id          BIGSERIAL   PRIMARY KEY,
  camera_id       VARCHAR(40) NOT NULL REFERENCES camera(camera_id),
  vehicle_id      VARCHAR(40) NOT NULL,            -- BIS 차량 번호 / 도시철도 편성 번호 표기 그대로
  vehicle_type_id VARCHAR(40) REFERENCES vehicle_type(vehicle_type_id),
  verify_status   VARCHAR(12) NOT NULL CHECK (verify_status IN ('verified','unverified','released')),
  verified_at     TIMESTAMP,
  effective_from  TIMESTAMP NOT NULL,
  released_at     TIMESTAMP,
  created_at      TIMESTAMP NOT NULL,
  created_by      VARCHAR(40) NOT NULL,
  input_method    VARCHAR(8)  NOT NULL CHECK (input_method IN ('select','csv')),   -- UC12 목록 선택 / CSV 일괄
  -- G9: 검증됨이면 검증 시각 필수. 미검증 저장 허용 여부는 미결(§16) — 상태값으로 수용
  CONSTRAINT chk_map_verified CHECK (verify_status <> 'verified' OR verified_at IS NOT NULL),
  CONSTRAINT chk_map_released CHECK ((verify_status = 'released') = (released_at IS NOT NULL))
);
-- BR-CV-25 / UC12 E2: 같은 카메라의 활성 매핑은 하나
-- [DBMS 주석] 부분 UNIQUE 인덱스(WHERE)는 SQL 표준이 아니다. SQLite·PostgreSQL 지원. MySQL 은 트리거로 대체.
CREATE UNIQUE INDEX IF NOT EXISTS uq_map_active_camera ON camera_vehicle_map(camera_id) WHERE released_at IS NULL;

-- ---------------------------------------------------------------------
-- 영역 B. 정책  (쓰기: 운영 관리자 / 생애주기: 드물게, 판본)
-- ---------------------------------------------------------------------

-- ThresholdPolicy (Key Entities). BR-CV-04. 적용 시작일부터 새 정책이 대체
CREATE TABLE IF NOT EXISTS threshold_policy (
  policy_id          BIGSERIAL   PRIMARY KEY,
  free_min_ratio     REAL        NOT NULL,        -- 여유 하한 (잔여 %)
  crowded_max_ratio  REAL        NOT NULL,        -- 혼잡 상한 (잔여 %)
  count_conf_min     REAL,                        -- R22 인원 세기 기준 (검출 신뢰도 하한, 0.05~0.95). NULL = 설정 기본값 0.4
  effective_from     TIMESTAMP NOT NULL,
  created_at         TIMESTAMP NOT NULL,
  created_by         VARCHAR(40) NOT NULL,
  -- G8 (UC8 E1·E4): 0~100%, 혼잡 상한 < 여유 하한. "적용 시작일 과거 아님"은 시점 의존 → 트리거 trg_threshold_future
  CONSTRAINT chk_threshold_range CHECK (free_min_ratio BETWEEN 0 AND 100 AND crowded_max_ratio BETWEEN 0 AND 100),
  CONSTRAINT chk_threshold_order CHECK (crowded_max_ratio < free_min_ratio),
  CONSTRAINT uq_threshold_from UNIQUE (effective_from)
);
-- G8: 적용 시작일은 저장 시점 이후여야 한다 (UC8 E4). 시점 의존 규칙이라 CHECK 가 아닌 트리거.
CREATE OR REPLACE FUNCTION fn_trg_threshold_future() RETURNS trigger AS $$
BEGIN
  IF NEW.effective_from < NEW.created_at THEN RAISE EXCEPTION 'G8: threshold_policy.effective_from must not be in the past'; END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_threshold_future ON threshold_policy;
CREATE TRIGGER trg_threshold_future BEFORE INSERT ON threshold_policy FOR EACH ROW EXECUTE FUNCTION fn_trg_threshold_future();

-- ValidityPolicy (Key Entities). BR-CV-24·26·27. 즉시 적용, 판본
CREATE TABLE IF NOT EXISTS validity_policy (
  policy_id        BIGSERIAL   PRIMARY KEY,
  basis            VARCHAR(12) NOT NULL DEFAULT 'headway' CHECK (basis = 'headway'),  -- 기준 = 노선별 배차 간격 (FR-13b)
  factor           REAL        NOT NULL DEFAULT 1.0,
  cap_minutes      INTEGER     NOT NULL,
  default_minutes  INTEGER     NOT NULL DEFAULT 10,   -- 배차 간격 자료 없는 노선 10분 (Assumptions 8)
  window_minutes   INTEGER     NOT NULL DEFAULT 1,    -- 합산 시각 창 기본 1분 (FR-13e)
  demo_on          INTEGER     NOT NULL DEFAULT 0 CHECK (demo_on IN (0,1)),
  demo_end_at      TIMESTAMP,
  effective_from   TIMESTAMP NOT NULL,
  superseded_at    TIMESTAMP,
  created_at       TIMESTAMP NOT NULL,
  created_by       VARCHAR(40) NOT NULL,
  -- G8 (UC11 E1): 양수, 상한 >= 기본값
  CONSTRAINT chk_validity_positive CHECK (factor > 0 AND cap_minutes > 0 AND default_minutes > 0 AND window_minutes > 0),
  CONSTRAINT chk_validity_cap CHECK (cap_minutes >= default_minutes),
  -- BR-CV-26 / G8: 시연 모드 켜짐이면 종료 예정 시각 필수 (SD_01 §6-3)
  CONSTRAINT chk_demo_end CHECK (demo_on = 0 OR demo_end_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS validity_route_exception (
  policy_id  INTEGER     NOT NULL REFERENCES validity_policy(policy_id),
  route_id   VARCHAR(40) NOT NULL REFERENCES route(route_id),   -- G8: 예외 노선은 기준 정보에 존재 (FK)
  minutes    INTEGER     NOT NULL CHECK (minutes > 0),
  PRIMARY KEY (policy_id, route_id)
);

-- ---------------------------------------------------------------------
-- 영역 F. 외부 운행 정보 스냅샷  (쓰기: 시스템 — BIS·배차 조회 시 / 생애주기: 조회마다)
-- ---------------------------------------------------------------------

-- 노선별 배차 간격 (BR-CV-24). source_status 가 S3 미리보기의 "출처" 열 (G12)
CREATE TABLE IF NOT EXISTS route_headway (
  route_id        VARCHAR(40) NOT NULL REFERENCES route(route_id),
  fetched_at      TIMESTAMP NOT NULL,
  headway_minutes INTEGER,
  source_status   VARCHAR(10) NOT NULL CHECK (source_status IN ('bis','timetable','none','stale')),
  PRIMARY KEY (route_id, fetched_at),
  CONSTRAINT chk_headway_value CHECK ((source_status IN ('bis','timetable','stale')) = (headway_minutes IS NOT NULL))
);

-- 운행 정보 차량 목록 (G9 존재 검증 원천, UC12 2단계)
CREATE TABLE IF NOT EXISTS fleet_vehicle (
  vehicle_id      VARCHAR(40) NOT NULL PRIMARY KEY,
  route_id        VARCHAR(40) NOT NULL REFERENCES route(route_id),
  vehicle_type_id VARCHAR(40) REFERENCES vehicle_type(vehicle_type_id),
  fetched_at      TIMESTAMP NOT NULL
);

-- 다음 차량 도착 스냅샷 (Key Entities Trip/Arrival, P7 7.3). source_status 가 G12 판정값
CREATE TABLE IF NOT EXISTS arrival_snapshot (
  snapshot_id         BIGSERIAL   PRIMARY KEY,
  route_id            VARCHAR(40) NOT NULL REFERENCES route(route_id),
  stop_id             VARCHAR(40) NOT NULL REFERENCES stop(stop_id),
  vehicle_id          VARCHAR(40),
  expected_arrival_at TIMESTAMP,
  vehicle_type_id     VARCHAR(40) REFERENCES vehicle_type(vehicle_type_id),
  fetched_at          TIMESTAMP NOT NULL,
  source_status       VARCHAR(12) NOT NULL CHECK (source_status IN ('ok','unavailable','timeout','no_vehicle')),
  -- G12: ok 일 때만 차량·도착 시각이 있다 (UC2 E1·E3·E4)
  CONSTRAINT chk_arrival_ok CHECK ((source_status = 'ok') = (vehicle_id IS NOT NULL AND expected_arrival_at IS NOT NULL))
);

-- ---------------------------------------------------------------------
-- 영역 E. 운영  (쓰기: 운영 관리자·시스템 / 생애주기: 배포·기동 단위)
-- ---------------------------------------------------------------------

-- 모델 패키지 (H10, BR-CV-31). 라이선스·요구 버전은 확인 전까지 NULL
CREATE TABLE IF NOT EXISTS model_package (
  model_package_id      BIGSERIAL    PRIMARY KEY,                -- T073 후속: 이식 때 빠졌던 자동 증가
  repo_url              VARCHAR(200) NOT NULL,
  commit_hash           VARCHAR(64)  NOT NULL,
  weights_file          VARCHAR(200) NOT NULL,
  license               VARCHAR(100),
  required_versions     VARCHAR(500),
  contract_check_result VARCHAR(20) CHECK (contract_check_result IN ('ok','mismatch','adapter')),  -- BR-CV-28 4필드 계약
  fetched_at            TIMESTAMP  NOT NULL,
  fetched_by            VARCHAR(40)  NOT NULL,
  detector_kind         VARCHAR(16),                          -- 검출기 종류 yolov8 | ollama_vl | stub (구현 단계 추가)
  CONSTRAINT uq_model_commit UNIQUE (commit_hash, weights_file)
);

-- 진단 API 서버 인스턴스 (H1, BR-CV-19·29). readiness 가 G0 판정값 (단일 지점은 v_readiness)
CREATE TABLE IF NOT EXISTS server_instance (
  instance_id          BIGSERIAL    PRIMARY KEY,               -- T073 후속: 이식 때 빠졌던 자동 증가
  model_package_id     INTEGER      NOT NULL REFERENCES model_package(model_package_id),
  endpoint_url         VARCHAR(200) NOT NULL,
  port                 INTEGER,
  auth_method          VARCHAR(40),              -- 확인 필요 (SD_01 §16 2)
  started_at           TIMESTAMP  NOT NULL,
  warmup_done_at       TIMESTAMP,
  contract_ok          INTEGER CHECK (contract_ok IN (0,1)),
  readiness            VARCHAR(12)  NOT NULL CHECK (readiness IN ('ready','preparing','unavailable')),
  readiness_updated_at TIMESTAMP  NOT NULL,
  detector_kind        VARCHAR(16),              -- 이 인스턴스가 적재한 검출기 (구현 단계 추가)
  load_seconds         REAL,                     -- 검출기 적재 소요 초 (구현 단계 추가)
  -- BR-CV-19 / G0·G5: "진단 가능"은 웜업 완료 + 계약 확인 후에만
  CONSTRAINT chk_ready_requires_warmup CHECK (readiness <> 'ready' OR (warmup_done_at IS NOT NULL AND contract_ok = 1))
);

-- ---------------------------------------------------------------------
-- 영역 C. 진단  (쓰기: 연계 시스템·본 웹서비스·운영 관리자 / 생애주기: 요청마다)
-- ---------------------------------------------------------------------

-- 일괄 묶음 (UC4 정확도 검증, UC10 A4 시연 사전 등록)
CREATE TABLE IF NOT EXISTS batch (
  batch_id     BIGSERIAL   PRIMARY KEY,
  camera_id    VARCHAR(40) NOT NULL REFERENCES camera(camera_id),
  purpose      VARCHAR(16) NOT NULL CHECK (purpose IN ('verification','demo_preload')),
  submitted_by VARCHAR(40) NOT NULL,
  submitted_at TIMESTAMP NOT NULL,
  frame_count  INTEGER     NOT NULL CHECK (frame_count > 0)   -- 한도 값은 미결 (G2, §16)
);

-- 진단 요청 (Key Entities Frame — 진단 후 폐기되므로 메타만). 원본 이미지 컬럼 없음 (BR-CV-09)
CREATE TABLE IF NOT EXISTS diagnosis_request (
  request_id    BIGSERIAL   PRIMARY KEY,
  kind          VARCHAR(12) NOT NULL CHECK (kind IN ('single','batch_item','measurement','test_call')),
  caller_id     VARCHAR(40) NOT NULL,            -- FR-16 호출 주체 식별 (정보 차등 없음 — 값 분기 컬럼 없음)
  camera_id     VARCHAR(40) NOT NULL REFERENCES camera(camera_id),   -- G3
  batch_id      INTEGER     REFERENCES batch(batch_id),
  batch_seq     INTEGER,                         -- BR-CV-12 제출 순서
  captured_at   TIMESTAMP,
  image_format  VARCHAR(8),
  width         INTEGER,
  height        INTEGER,
  size_bytes    INTEGER,
  received_at   TIMESTAMP NOT NULL,
  responded_at  TIMESTAMP,
  status        VARCHAR(10) NOT NULL CHECK (status IN ('accepted','rejected')),
  reject_reason VARCHAR(200),
  -- G2 / BR-CV-11: 반려면 사유 필수, 수락이면 사유 없음. 규격 값(형식·해상도·용량)은 미결이라 CHECK 로 두지 않는다 (§16)
  CONSTRAINT chk_reject_reason CHECK ((status = 'rejected') = (reject_reason IS NOT NULL)),
  CONSTRAINT chk_batch_seq CHECK ((batch_id IS NULL) = (batch_seq IS NULL)),
  CONSTRAINT uq_batch_seq UNIQUE (batch_id, batch_seq)
);

-- 진단 결과 (Key Entities Assessment, H4). 판본 참조(roi·spec·threshold·model)로 NFR-06 재현성 확보
CREATE TABLE IF NOT EXISTS assessment (
  assessment_id        BIGSERIAL PRIMARY KEY,
  request_id           INTEGER NOT NULL UNIQUE REFERENCES diagnosis_request(request_id),
  roi_id               INTEGER NOT NULL REFERENCES roi(roi_id),                     -- G4
  spec_id              INTEGER REFERENCES vehicle_spec(spec_id),                    -- G7: NULL 이면 "산출 불가"
  threshold_policy_id  INTEGER NOT NULL REFERENCES threshold_policy(policy_id),
  model_package_id     INTEGER NOT NULL REFERENCES model_package(model_package_id), -- G5
  occupied_area_ratio  REAL    NOT NULL,                                            -- 모델 출력 (%, 단위 미결 §16)
  vacant_capacity_ratio REAL   GENERATED ALWAYS AS (100.0 - occupied_area_ratio) STORED,  -- BR-CV-03 유도 (GENERATED)
  model_crowding_level VARCHAR(12),                                                 -- 모델 원출력 (재매핑 여부 미결 §8.3 23)
  crowding_level       VARCHAR(12) NOT NULL CHECK (crowding_level IN ('free','normal','crowded','uncertain')),
  mean_confidence      REAL    NOT NULL,
  person_count         INTEGER,                                                     -- R22 셈에 든 인원 (인원 세기 기준 이상 · 발 위치 ROI 안)
  processed_at         TIMESTAMP NOT NULL,
  -- BR-CV-03: 0~100%
  CONSTRAINT chk_occupied_range CHECK (occupied_area_ratio BETWEEN 0 AND 100),
  CONSTRAINT chk_confidence_range CHECK (mean_confidence BETWEEN 0 AND 1),
  -- BR-CV-07 / G6: 신뢰도 0.6 미만이면 확정 등급 금지 (품질 경고에 의한 판독 불확실은 트리거 trg_warning_uncertain)
  CONSTRAINT chk_low_confidence_uncertain CHECK (mean_confidence >= 0.6 OR crowding_level = 'uncertain')
);
-- [DBMS 주석] GENERATED ALWAYS AS ... STORED 는 SQL:2003 표준. SQLite 3.31+ 지원. MySQL/PostgreSQL 12+ 동일.

-- 경고 (Key Entities Warning). 7종 + 모델이 내는 미정의 값은 'unknown' + raw_code (§16)
CREATE TABLE IF NOT EXISTS assessment_warning (
  assessment_id INTEGER     NOT NULL REFERENCES assessment(assessment_id),
  warning_code  VARCHAR(20) NOT NULL CHECK (warning_code IN ('blur','low_light','backlight','low_confidence','occlusion','roi_stale','partial_coverage','unknown')),
  raw_code      VARCHAR(40),
  detail        VARCHAR(200),
  PRIMARY KEY (assessment_id, warning_code),
  CONSTRAINT chk_unknown_raw CHECK (warning_code <> 'unknown' OR raw_code IS NOT NULL)
);
-- BR-CV-06 / G6: 품질 경고(blur·low_light·backlight)가 붙은 결과는 확정 등급을 가질 수 없다.
-- 다중 행 조건(경고 행 ↔ 결과 행)이라 CHECK 불가 → 트리거. 경고 삽입 시 결과 등급을 검사한다.
CREATE OR REPLACE FUNCTION fn_trg_warning_uncertain() RETURNS trigger AS $$
BEGIN
  IF NEW.warning_code IN ('blur','low_light','backlight','low_confidence') AND (SELECT crowding_level FROM assessment WHERE assessment_id = NEW.assessment_id) <> 'uncertain' THEN RAISE EXCEPTION 'BR-CV-06/07 (G6): quality warning requires crowding_level = uncertain'; END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_warning_uncertain ON assessment_warning;
CREATE TRIGGER trg_warning_uncertain BEFORE INSERT ON assessment_warning FOR EACH ROW EXECUTE FUNCTION fn_trg_warning_uncertain();
-- BR-CV-07: 신뢰도 0.6 미만 결과에는 low_confidence 경고가 반드시 붙는다 — 결과 행 삽입 후 경고 행 삽입 순서 때문에
-- 삽입 트리거로 강제할 수 없다. [앱 책임] 진단 모듈이 한 트랜잭션에서 두 행을 쓴다. 점검 쿼리: §N+4 chk_q2.

-- 정확도 검증 실행 (H8). 정책·ROI·모델 판본을 고정 참조 — 바뀌면 invalidated (H8 만료 조건)
CREATE TABLE IF NOT EXISTS verification_run (
  run_id              BIGSERIAL PRIMARY KEY,
  batch_id            INTEGER NOT NULL REFERENCES batch(batch_id),
  threshold_policy_id INTEGER NOT NULL REFERENCES threshold_policy(policy_id),
  roi_id              INTEGER NOT NULL REFERENCES roi(roi_id),
  model_package_id    INTEGER NOT NULL REFERENCES model_package(model_package_id),
  ratio_match_rate    REAL    NOT NULL CHECK (ratio_match_rate BETWEEN 0 AND 100),   -- <<derived 고정>> SC-01 ±10%p 일치율
  level_match_rate    REAL    NOT NULL CHECK (level_match_rate BETWEEN 0 AND 100),   -- <<derived 고정>> SC-02 등급 일치율
  verdict             VARCHAR(8) NOT NULL CHECK (verdict IN ('pass','fail')),        -- <<derived 고정>> SC-01·02 85% 판정
  created_at          TIMESTAMP NOT NULL,
  invalidated_at      TIMESTAMP,
  invalidated_reason  VARCHAR(100),
  -- SC-01·SC-02: 85% 는 원천 성공기준의 값. 판정과 일치율의 정합
  CONSTRAINT chk_verdict CHECK ((verdict = 'pass') = (ratio_match_rate >= 85 AND level_match_rate >= 85)),
  CONSTRAINT chk_invalidated CHECK ((invalidated_at IS NULL) = (invalidated_reason IS NULL))
);

-- 검증 항목: 프레임별 수작업 측정값 (운영 관리자 보관 자료 — 판정 근거로 run 에 한해 저장, SD_01 §7-3)
CREATE TABLE IF NOT EXISTS verification_item (
  run_id       INTEGER NOT NULL REFERENCES verification_run(run_id),
  request_id   INTEGER NOT NULL REFERENCES diagnosis_request(request_id),
  manual_ratio REAL CHECK (manual_ratio IS NULL OR manual_ratio BETWEEN 0 AND 100),
  manual_level VARCHAR(12) CHECK (manual_level IS NULL OR manual_level IN ('free','normal','crowded')),
  PRIMARY KEY (run_id, request_id)
);

-- 운영 지표 (P0 0.2, BR-CV-20). 신뢰 구간 정의가 미결이라 out_of_band 는 NULL 허용
CREATE TABLE IF NOT EXISTS quality_metric (
  metric_id       BIGSERIAL   PRIMARY KEY,
  hour_of_day     INTEGER     NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
  light_condition VARCHAR(12) NOT NULL CHECK (light_condition IN ('normal','low_light','backlight')),
  sample_count    INTEGER     NOT NULL CHECK (sample_count >= 0),
  confidence_dev  REAL        NOT NULL,
  out_of_band     INTEGER CHECK (out_of_band IN (0,1)),
  computed_at     TIMESTAMP NOT NULL,
  CONSTRAINT uq_metric_slot UNIQUE (hour_of_day, light_condition, computed_at)
);

-- ---------------------------------------------------------------------
-- 영역 D. 실측  (쓰기: 연계 시스템·본 웹서비스·운영 관리자(시연) / 생애주기: 차내 프레임마다, 최신만 유효)
-- ---------------------------------------------------------------------

-- 카메라 최신 실측 (UC10 4단계). 이전 실측은 superseded_at 으로 대체 이력 (BR-CV-23)
CREATE TABLE IF NOT EXISTS camera_measurement (
  cm_id              BIGSERIAL PRIMARY KEY,
  assessment_id      INTEGER NOT NULL UNIQUE REFERENCES assessment(assessment_id),
  map_id             INTEGER NOT NULL REFERENCES camera_vehicle_map(map_id),     -- G10 매핑 키 (BR-CV-25)
  validity_policy_id INTEGER NOT NULL REFERENCES validity_policy(policy_id),
  measured_at        TIMESTAMP NOT NULL,   -- <<derived 고정>> = captured_at, 시연 모드면 registered_at (BR-CV-26)
  registered_at      TIMESTAMP NOT NULL,
  is_demo            INTEGER NOT NULL CHECK (is_demo IN (0,1)),
  validity_minutes   INTEGER NOT NULL CHECK (validity_minutes > 0),   -- <<derived 고정>> H5 "적용된 유효 시간"
  expires_at         TIMESTAMP NOT NULL,   -- <<derived 고정>> measured_at + validity_minutes (BR-CV-23·24). 재계산 여부 미결 §16
  superseded_at      TIMESTAMP,
  -- BR-CV-26: 시연 모드 실측은 실측 시각 = 등록 시각
  CONSTRAINT chk_demo_measured CHECK (is_demo = 0 OR measured_at = registered_at),
  CONSTRAINT chk_expires_after CHECK (expires_at > measured_at)
);
-- BR-CV-23: 카메라별 최신 실측 하나 — 활성(superseded_at IS NULL) 행은 카메라(매핑)당 1개
CREATE UNIQUE INDEX IF NOT EXISTS uq_cm_active_map ON camera_measurement(map_id) WHERE superseded_at IS NULL;
-- G10: 실측 등록 카메라는 차내 유형(버스·열차)이어야 한다 (UC10 A3 — 승강장 카메라 실측 거부, R21-D8 정정). 다른 테이블 조회가 필요하므로 트리거.
CREATE OR REPLACE FUNCTION fn_trg_cm_in_vehicle_camera() RETURNS trigger AS $$
BEGIN
  IF (SELECT c.place_type FROM camera_vehicle_map m JOIN camera c ON c.camera_id = m.camera_id WHERE m.map_id = NEW.map_id) NOT IN ('bus_in','train_in') THEN RAISE EXCEPTION 'G10: measurement camera must be in-vehicle type'; END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_cm_in_vehicle_camera ON camera_measurement;
CREATE TRIGGER trg_cm_in_vehicle_camera BEFORE INSERT ON camera_measurement FOR EACH ROW EXECUTE FUNCTION fn_trg_cm_in_vehicle_camera();
-- G10: 매핑은 활성(released_at IS NULL)이어야 한다
CREATE OR REPLACE FUNCTION fn_trg_cm_active_map() RETURNS trigger AS $$
BEGIN
  IF (SELECT released_at FROM camera_vehicle_map WHERE map_id = NEW.map_id) IS NOT NULL THEN RAISE EXCEPTION 'G10: mapping is released'; END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_cm_active_map ON camera_measurement;
CREATE TRIGGER trg_cm_active_map BEFORE INSERT ON camera_measurement FOR EACH ROW EXECUTE FUNCTION fn_trg_cm_active_map();

-- 차량 합산 실측 (Key Entities VehicleMeasurement, H5). 유도값이나 H5 계약으로 응답 시점 값을 고정 저장
CREATE TABLE IF NOT EXISTS vehicle_measurement (
  vm_id               BIGSERIAL PRIMARY KEY,
  vehicle_id          VARCHAR(40) NOT NULL,
  validity_policy_id  INTEGER NOT NULL REFERENCES validity_policy(policy_id),
  aggregated_at       TIMESTAMP NOT NULL,
  window_minutes      INTEGER NOT NULL CHECK (window_minutes > 0),   -- 적용된 합산 시각 창 (BR-CV-27)
  measured_at         TIMESTAMP NOT NULL,   -- 합산에 든 실측 중 최신 실측 시각
  vacant_ratio_agg    REAL NOT NULL CHECK (vacant_ratio_agg BETWEEN 0 AND 100),     -- <<derived 고정>> R22: 100 − 합산 인원/정원×100 (이전: 면적 가중 합산)
  crowding_level_agg  VARCHAR(12) NOT NULL CHECK (crowding_level_agg IN ('free','normal','crowded','uncertain')),
  coverage_num        INTEGER NOT NULL CHECK (coverage_num >= 1),    -- <<derived 고정>> 합산 카메라 수 (BR-CV-27: 0이면 실측 없음 → 행 없음)
  coverage_den        INTEGER NOT NULL CHECK (coverage_den >= 1),    -- <<derived 고정>> 매핑 카메라 수
  persons_sum         INTEGER CHECK (persons_sum IS NULL OR persons_sum >= 0),   -- R22 합산 인원 (카메라별 최신 유효 실측 인원 합)
  capacity            INTEGER CHECK (capacity IS NULL OR capacity > 0),          -- R22 합산 당시 차량 전체 정원 (vacant_ratio_agg = 100 − 인원/정원×100, 하한 0)
  expires_at          TIMESTAMP NOT NULL,   -- <<derived 고정>> 구성 실측 중 가장 이른 만료 [추론]
  is_demo             INTEGER NOT NULL CHECK (is_demo IN (0,1)),
  superseded_at       TIMESTAMP,
  CONSTRAINT chk_coverage CHECK (coverage_num <= coverage_den)
);
-- BR-CV-23: 차량별 최신 합산 하나
CREATE UNIQUE INDEX IF NOT EXISTS uq_vm_active_vehicle ON vehicle_measurement(vehicle_id) WHERE superseded_at IS NULL;

-- 합산 구성 (어느 카메라 실측이 어떤 가중치로 들어갔는가 — 역추적 경로 2)
CREATE TABLE IF NOT EXISTS vehicle_measurement_component (
  vm_id       INTEGER NOT NULL REFERENCES vehicle_measurement(vm_id),
  cm_id       INTEGER NOT NULL REFERENCES camera_measurement(cm_id),
  weight_area REAL    NOT NULL CHECK (weight_area > 0),   -- = roi.area 고정 사본 (합산 당시 가중치)
  PRIMARY KEY (vm_id, cm_id)
);

-- ---------------------------------------------------------------------
-- 영역 E (계속). 연동 · 게이트 이벤트 · 영역 G 안내
-- ---------------------------------------------------------------------

-- 웹서비스 연동 (P1 1.5~1.6, G16)
CREATE TABLE IF NOT EXISTS integration (
  integration_id    BIGSERIAL PRIMARY KEY,
  instance_id       INTEGER NOT NULL REFERENCES server_instance(instance_id),
  registered_at     TIMESTAMP NOT NULL,
  registered_by     VARCHAR(40) NOT NULL,
  test_request_id   INTEGER REFERENCES diagnosis_request(request_id),
  first_response_ms INTEGER,                    -- SC-04 계측치
  status            VARCHAR(12) NOT NULL CHECK (status IN ('registered','confirmed','reverted')),
  reverted_reason   VARCHAR(200),
  -- G16: 확인됨은 시험 호출이 있어야, 되돌림은 사유가 있어야
  CONSTRAINT chk_integration_confirmed CHECK (status <> 'confirmed' OR test_request_id IS NOT NULL),
  CONSTRAINT chk_integration_reverted CHECK ((status = 'reverted') = (reverted_reason IS NOT NULL))
);

-- 게이트 이벤트 (1급 엔티티). SD_01 §14 G0~G17 발생·요청·해제 이력. subject 는 다형 참조 (FK 없음 — 점검 쿼리 §N+4)
CREATE TABLE IF NOT EXISTS gate_event (
  event_id        BIGSERIAL   PRIMARY KEY,
  gate_code       VARCHAR(4)  NOT NULL CHECK (gate_code IN ('G0','G1','G2','G3','G4','G5','G6','G7','G8','G9','G10','G11','G12','G13','G14','G15','G16','G17')),
  screen_code     VARCHAR(4)  NOT NULL CHECK (screen_code IN ('S0','S1','S2','S3','S4','S5','S6','S7','S8','S9')),
  subject_kind    VARCHAR(12) NOT NULL CHECK (subject_kind IN ('request','camera','vehicle','policy','mapping','instance','run','guide','route_stop')),
  subject_id      VARCHAR(40) NOT NULL,
  occurred_at     TIMESTAMP NOT NULL,
  reason_code     VARCHAR(40) NOT NULL,
  reason_text     VARCHAR(300),
  resolver_role   VARCHAR(10) NOT NULL CHECK (resolver_role IN ('self','operator','external','undefined')),
  request_sent_at TIMESTAMP,
  request_sent_by VARCHAR(40),
  resolved_at     TIMESTAMP,
  resolved_by     VARCHAR(40),
  resolution_ref  VARCHAR(80),
  -- U5 (SD_02): 해제 주체가 본인이면 «요청 보내기»가 없다
  CONSTRAINT chk_gate_request CHECK (resolver_role <> 'self' OR request_sent_at IS NULL),
  CONSTRAINT chk_gate_request_by CHECK ((request_sent_at IS NULL) = (request_sent_by IS NULL)),
  -- G3: 해제 주체 미정 게이트는 해제 기록을 가질 수 없다 (SD_01 §16 3) — 절차 확정 전까지
  CONSTRAINT chk_gate_undefined CHECK (resolver_role <> 'undefined' OR resolved_at IS NULL)
);

-- API 활용 안내 (H9, BR-CV-30). G17: published 는 verified 후에만
CREATE TABLE IF NOT EXISTS api_guide (
  guide_id      BIGSERIAL   PRIMARY KEY,
  version       VARCHAR(20) NOT NULL UNIQUE,
  status        VARCHAR(12) NOT NULL CHECK (status IN ('draft','verified','published','mismatch')),
  contract_hash VARCHAR(64),
  verified_at   TIMESTAMP,
  verified_by   VARCHAR(40),
  published_at  TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL,
  CONSTRAINT chk_guide_published CHECK (status <> 'published' OR (verified_at IS NOT NULL AND published_at IS NOT NULL)),
  CONSTRAINT chk_guide_verified CHECK (status NOT IN ('verified','published') OR verified_at IS NOT NULL)
);

-- 엔드포인트 카탈로그 (UC15 표). path·method 는 계획 단계 확정 전 NULL
CREATE TABLE IF NOT EXISTS api_endpoint (
  guide_id      INTEGER      NOT NULL REFERENCES api_guide(guide_id),
  feature_code  VARCHAR(30)  NOT NULL,
  uc_ref        VARCHAR(40)  NOT NULL,   -- 20 → 40: 'UC6 UC7 UC12 (+카메라 등록)' 22자 (T073 후속 — SQLite 는 길이를 강제하지 않아 드러나지 않았다)
  input_desc    VARCHAR(500) NOT NULL,
  output_desc   VARCHAR(500) NOT NULL,
  error_reasons VARCHAR(500),
  warning_types VARCHAR(300),
  path          VARCHAR(200),
  method        VARCHAR(8) CHECK (method IS NULL OR method IN ('GET','POST','PUT','DELETE')),
  PRIMARY KEY (guide_id, feature_code)
);

-- ---------------------------------------------------------------------
-- 인덱스 (조회 경로: S7 최신 실측, S0 운영 상태, 역추적)
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_request_camera_time ON diagnosis_request(camera_id, received_at);
CREATE INDEX IF NOT EXISTS ix_assessment_processed ON assessment(processed_at);
CREATE INDEX IF NOT EXISTS ix_cm_expires ON camera_measurement(expires_at);
CREATE INDEX IF NOT EXISTS ix_vm_vehicle_expires ON vehicle_measurement(vehicle_id, expires_at);
CREATE INDEX IF NOT EXISTS ix_arrival_lookup ON arrival_snapshot(route_id, stop_id, fetched_at);
CREATE INDEX IF NOT EXISTS ix_gate_open ON gate_event(gate_code, resolved_at);
CREATE INDEX IF NOT EXISTS ix_map_vehicle ON camera_vehicle_map(vehicle_id, released_at);

-- ---------------------------------------------------------------------
-- 뷰 — 유도 속성과 게이트 판정의 단일 지점
-- ---------------------------------------------------------------------

-- 현재 판본 3종
CREATE OR REPLACE VIEW v_current_roi AS
  SELECT * FROM roi WHERE superseded_at IS NULL;
CREATE OR REPLACE VIEW v_current_spec AS
  SELECT * FROM vehicle_spec WHERE superseded_at IS NULL;
CREATE OR REPLACE VIEW v_active_mapping AS
  SELECT * FROM camera_vehicle_map WHERE released_at IS NULL;

-- 현재 정책 (ThresholdPolicy 는 적용 시작일이 지난 것 중 최신, ValidityPolicy 는 활성 판본)
CREATE OR REPLACE VIEW v_current_threshold AS
  SELECT * FROM threshold_policy
  WHERE effective_from <= (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
  ORDER BY effective_from DESC LIMIT 1;
-- [DBMS 주석] strftime('now') 는 SQLite. 표준은 CURRENT_TIMESTAMP.
CREATE OR REPLACE VIEW v_current_validity AS
  SELECT * FROM validity_policy WHERE superseded_at IS NULL;

-- BR-CV-24 노선별 유효 시간 — 단일 산출 지점 (S3 미리보기·P6 6.4·P7 7.4 모두 여기서 읽는다)
CREATE OR REPLACE VIEW v_route_validity_minutes AS
  SELECT r.route_id,
         h.headway_minutes,
         h.source_status,
         CASE
           WHEN e.minutes IS NOT NULL THEN e.minutes
           WHEN h.headway_minutes IS NULL THEN p.default_minutes
           ELSE LEAST(CAST(h.headway_minutes * p.factor AS INTEGER), p.cap_minutes)   -- SQLite 스칼라 MIN(a,b) = PostgreSQL LEAST (T073)
         END AS validity_minutes,
         CASE WHEN e.minutes IS NOT NULL THEN 'exception'
              WHEN h.headway_minutes IS NULL THEN 'default'
              ELSE h.source_status END AS validity_source
  FROM route r
  CROSS JOIN v_current_validity p
  LEFT JOIN (SELECT route_id, headway_minutes, source_status
             FROM route_headway rh
             WHERE fetched_at = (SELECT MAX(fetched_at) FROM route_headway WHERE route_id = rh.route_id)) h
         ON h.route_id = r.route_id
  LEFT JOIN validity_route_exception e ON e.policy_id = p.policy_id AND e.route_id = r.route_id;

-- G0 준비 상태 — 단일 판정 지점 (가장 최근 인스턴스)
CREATE OR REPLACE VIEW v_readiness AS
  SELECT instance_id, readiness, readiness_updated_at, endpoint_url,
         (readiness = 'ready') AS gate_g0_open
  FROM server_instance ORDER BY readiness_updated_at DESC LIMIT 1;

-- G3·G4·G7·G10 카메라 준비도 — 단일 판정 지점 (S2 2.1 현황, S5·S6 차단 사유의 원천)
CREATE OR REPLACE VIEW v_camera_readiness AS
  SELECT c.camera_id, c.place_type, c.roi_stale,
         (r.roi_id IS NOT NULL)  AS has_roi,        -- G4
         (s.spec_id IS NOT NULL) AS has_capacity,   -- G7
         (m.map_id IS NOT NULL)  AS has_mapping,    -- G10
         r.roi_id, s.spec_id, m.map_id, m.vehicle_id
  FROM camera c
  LEFT JOIN v_current_roi r ON r.camera_id = c.camera_id
  LEFT JOIN v_current_spec s ON s.vehicle_type_id = c.vehicle_type_id
  LEFT JOIN v_active_mapping m ON m.camera_id = c.camera_id;

-- 진단 결과 전체 (유도 속성: 추정 잔여 인원, 응답 시간, 참고 표시)
CREATE OR REPLACE VIEW v_assessment AS
  SELECT a.assessment_id, a.request_id, q.camera_id, q.caller_id, q.kind, q.captured_at,
         a.occupied_area_ratio, a.vacant_capacity_ratio, a.crowding_level, a.mean_confidence,
         CASE WHEN a.spec_id IS NULL THEN NULL
              ELSE CAST(ROUND(s.capacity * a.vacant_capacity_ratio / 100.0) AS INTEGER) END AS remaining_persons,   -- BR-CV-05
         (a.spec_id IS NULL) AS remaining_not_computable,                                                             -- G7 "산출 불가"
         (a.crowding_level = 'uncertain') AS is_reference_only,                                                       -- BR-CV-07 "참고용"
         CAST(EXTRACT(EPOCH FROM (q.responded_at - q.received_at)) * 1000 AS INTEGER) AS response_ms,          -- FR-17 응답 시간
         a.processed_at, a.roi_id, a.spec_id, a.threshold_policy_id, a.model_package_id,
         (SELECT STRING_AGG(warning_code, ',') FROM assessment_warning w WHERE w.assessment_id = a.assessment_id) AS warnings
  FROM assessment a
  JOIN diagnosis_request q ON q.request_id = a.request_id
  LEFT JOIN vehicle_spec s ON s.spec_id = a.spec_id;
-- [DBMS 주석] julianday·group_concat 은 SQLite. 표준은 EXTRACT/EPOCH, LISTAGG(STRING_AGG).

-- FR-17 집계 기록 (H7 AuditRecord) — 별도 테이블이 아니라 뷰: 같은 값을 두 곳에 저장하지 않는다. 영상·개인 정보 없음
CREATE OR REPLACE VIEW v_audit_record AS
  SELECT a.processed_at AS at, a.camera_id, a.crowding_level, a.warnings, a.mean_confidence, a.response_ms, a.kind
  FROM v_assessment a;

-- G13 차량 실측 상태 — 단일 판정 지점 (P7 7.4, P0 0.3). 시연 모드면 만료 통과 (BR-CV-26)
CREATE OR REPLACE VIEW v_vehicle_measurement_status AS
  SELECT vm.*,
         CAST(vm.coverage_num AS REAL) / vm.coverage_den AS coverage_ratio,
         CAST((vm.coverage_num < vm.coverage_den) AS INTEGER) AS partial_coverage,
         CASE WHEN vm.is_demo = 1 AND p.demo_on = 1 AND p.demo_end_at > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') THEN 1
              WHEN vm.expires_at > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') THEN 1
              ELSE 0 END AS is_valid,
         CAST((vm.is_demo = 1 AND p.demo_on = 1 AND p.demo_end_at > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')) AS INTEGER) AS demo_flag
  FROM vehicle_measurement vm
  CROSS JOIN v_current_validity p
  WHERE vm.superseded_at IS NULL;

-- S7 후속 차량 여유도 (H6 NextVehicleEstimate) — 근거 유형 3값 (BR-CV-13)
CREATE OR REPLACE VIEW v_next_vehicle AS
  SELECT ar.route_id, ar.stop_id, ar.vehicle_id, ar.expected_arrival_at, ar.fetched_at,
         CASE WHEN ar.source_status <> 'ok' THEN 'unavailable'
              WHEN st.vm_id IS NOT NULL AND st.is_valid = 1 THEN 'measured'
              ELSE 'no_measurement' END AS basis_type,
         CASE WHEN st.is_valid = 1 THEN st.vacant_ratio_agg END AS vacant_ratio,
         CASE WHEN st.is_valid = 1 THEN st.crowding_level_agg END AS crowding_level,
         CASE WHEN st.is_valid = 1 THEN st.measured_at END AS measured_at,
         CASE WHEN st.is_valid = 1 THEN st.coverage_num END AS coverage_num,
         CASE WHEN st.is_valid = 1 THEN st.coverage_den END AS coverage_den,
         rv.validity_minutes AS applied_validity_minutes,
         COALESCE(st.demo_flag, 0) AS demo_mode
  FROM arrival_snapshot ar
  LEFT JOIN v_vehicle_measurement_status st ON st.vehicle_id = ar.vehicle_id
  LEFT JOIN v_route_validity_minutes rv ON rv.route_id = ar.route_id;

-- S4 검증 항목 (유도: 차이, 제외 여부)
CREATE OR REPLACE VIEW v_verification_item AS
  SELECT i.run_id, i.request_id, q.batch_seq, a.vacant_capacity_ratio, a.crowding_level, a.mean_confidence, a.warnings,
         i.manual_ratio, i.manual_level,
         a.vacant_capacity_ratio - i.manual_ratio AS ratio_diff,
         CAST((q.status = 'rejected' OR a.crowding_level = 'uncertain' OR a.assessment_id IS NULL) AS INTEGER) AS excluded,
         (ABS(a.vacant_capacity_ratio - i.manual_ratio) <= 10) AS ratio_match,      -- SC-01 ±10%p
         (a.crowding_level = i.manual_level) AS level_match                          -- SC-02
  FROM verification_item i
  JOIN diagnosis_request q ON q.request_id = i.request_id
  LEFT JOIN v_assessment a ON a.request_id = i.request_id;

-- 열린 게이트 (해제되지 않은 이벤트) — S0·C2 표시
CREATE OR REPLACE VIEW v_gate_open AS
  SELECT * FROM gate_event WHERE resolved_at IS NULL;

-- ---------------------------------------------------------------------
-- 영역 H. 계정·역할·API 키 (RBAC — 2026-09-29 T107, UC_00 §4 액터 → 역할)
--   역할: admin = 운영 관리자, controller = 관제 담당자, user = 일반 사용자(본 웹서비스 이용자·연계 개발자).
--   사이트는 로그인해야 쓴다. 회원가입하면 바로 일반 사용자(active)로 로그인한다.
--   API 키는 일반 사용자가 신청(api_key.status 'pending') → 운영 관리자 승인('active') 뒤에야 호출에 쓰인다.
--   연계 시스템은 승인된 api_key 로 호출한다. (2026-09-29 개정 — 이전: developer 역할, 계정 승인 후 키 즉시 발급, 이용자 공개)
--   비밀번호·키·세션 토큰은 해시만 저장한다(원문은 발급 순간 한 번만 보인다).
--   권한 매트릭스(S10, T110): 역할별 기능 허용의 기본값은 코드(rbac.PERMISSIONS), 운영 관리자가 바꾼 칸만 role_permission 에 둔다.
--   (2026-09-29 SAD — db.py _ROLE_PERMISSION_DDL 과 같은 정의를 정본으로 옮김)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS account (
  account_id     BIGSERIAL    PRIMARY KEY,
  login_id       VARCHAR(40)  NOT NULL UNIQUE,
  name           VARCHAR(60)  NOT NULL,
  org            VARCHAR(80),
  email          VARCHAR(120),
  password_hash  VARCHAR(200) NOT NULL,                 -- scrypt$n$r$p$salt$hash
  role           VARCHAR(12)  NOT NULL CHECK (role IN ('admin','controller','user')),
  status         VARCHAR(10)  NOT NULL CHECK (status IN ('pending','active','disabled')),
  created_at     TIMESTAMP    NOT NULL,
  approved_at    TIMESTAMP,
  approved_by    VARCHAR(40),
  last_login_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_key (
  key_id        BIGSERIAL    PRIMARY KEY,
  account_id    BIGINT       NOT NULL REFERENCES account(account_id),
  name          VARCHAR(40)  NOT NULL,                  -- 연계 시스템 이름 (예: 정류장 전광판)
  key_prefix    VARCHAR(12)  NOT NULL,                  -- 화면 표시용 앞자리 (예: cvk_ab12…)
  key_hash      VARCHAR(64)  NOT NULL UNIQUE,           -- sha256
  created_at    TIMESTAMP    NOT NULL,
  last_used_at  TIMESTAMP,
  revoked_at    TIMESTAMP,
  revoked_by    VARCHAR(40),
  status        VARCHAR(10)  NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','rejected')),  -- 운영 관리자 승인
  approved_at   TIMESTAMP,
  approved_by   VARCHAR(40)
);
CREATE INDEX IF NOT EXISTS ix_api_key_account ON api_key(account_id);

CREATE TABLE IF NOT EXISTS auth_session (
  session_id    BIGSERIAL    PRIMARY KEY,
  account_id    BIGINT       NOT NULL REFERENCES account(account_id),
  token_hash    VARCHAR(64)  NOT NULL UNIQUE,           -- sha256(Bearer 토큰)
  created_at    TIMESTAMP    NOT NULL,
  expires_at    TIMESTAMP    NOT NULL,
  revoked_at    TIMESTAMP
);

-- 계정 변경 이력 (2026-09-30 사용자 결정, SD_03 §16 17) — 운영 관리자의 역할 부여·승인·정지를 누가 언제 했는지.
-- account 는 현재 값만 덮어쓰므로 이력은 여기에만 남는다. 보관·파기 기간은 기관 정책(Q4)과 함께 정한다.
CREATE TABLE IF NOT EXISTS account_change (
  change_id   BIGSERIAL    PRIMARY KEY,
  account_id  INTEGER      NOT NULL REFERENCES account(account_id),
  field       VARCHAR(10)  NOT NULL CHECK (field IN ('role','status')),
  old_value   VARCHAR(12),                               -- 가입·생성 때는 NULL
  new_value   VARCHAR(12)  NOT NULL,
  changed_at  TIMESTAMP    NOT NULL,
  changed_by  VARCHAR(40)  NOT NULL                      -- 운영 관리자 식별자 또는 signup(가입)·system
);
CREATE INDEX IF NOT EXISTS ix_account_change_account ON account_change(account_id, changed_at);

-- 권한 매트릭스 (S10) — 유효 권한 = rbac.PERMISSIONS(기본값) + 이 표의 바꾼 칸. 운영 관리자 열·admin/accounts 행은 잠금(앱 422 RBAC_LOCKED).
CREATE TABLE IF NOT EXISTS role_permission (
  permission  VARCHAR(24) NOT NULL,                      -- diagnose·measure·next_vehicle·reference_read·api_guide·own_keys·control_view·admin·accounts
  role        VARCHAR(12) NOT NULL,                      -- user·controller·admin·integration·webservice
  allowed     INTEGER     NOT NULL CHECK (allowed IN (0,1)),
  updated_at  TIMESTAMP   NOT NULL,
  updated_by  VARCHAR(40) NOT NULL,
  PRIMARY KEY (permission, role)
);

-- 끝.
