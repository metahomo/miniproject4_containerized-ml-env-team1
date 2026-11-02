# Research — 001-crowd-vacancy-api

**작성일**: 2026-09-28 · **단계**: Phase 0 · **입력**: `spec.md`, `Intent-Plan.md`(Docker 미사용, 웹스택 선택지), `Intent-Specify.md`(도구 생태계), `design/`(UC_00~15, SD_01~03, style-guide), 모델 저장소 실물 확인

계획 단계에서 확정해야 했던 미결 항목(SD_01 §16, SD_02 §16, SD_03 §16, UC_00 §8.3)을 항목별로 결정·근거·대안으로 정리했다. 값이 원천에 없던 것은 **운영 설정으로 조정 가능한 기본값**으로 정하고 그 사실을 적었다.

---

## R1. 웹스택 — React + FastAPI, Docker 미사용

- **Decision**: 백엔드 Python 3.11 + FastAPI + Pydantic v2 + Uvicorn. 프론트엔드(본 웹서비스) React 18 + TypeScript + Vite. 컨테이너 없이 파이썬 가상환경(venv)과 npm 으로 실행.
- **Rationale**: Intent-Plan 의 유일한 확정 제약은 "docker 컨테이너를 사용하지 않고 만든다". 네 선택지 중 Intent-Specify 가 이미 FastAPI·Pydantic·Uvicorn·pytest 를 지정했고(핵심 활동 4·5항, 핵심 이네이블러), 추가 원천 3항이 "가상환경(uvicorn)" 을 명시한다. 선택지 설명에서 "머신러닝 모델 서빙"에 적합하다고 적힌 것도 React + FastAPI 뿐이다.
- **Alternatives**: Vue + Node(백엔드가 파이썬이 아니라 YOLOv8 서빙에 부적합), Django(DRF + ORM 이 SD_03 의 DDL 정본과 이중화), Next.js(파이썬 추론을 별도 서비스로 두어야 해 구조가 늘어남).

## R2. 데이터베이스 — SQLite(개발·시연) → PostgreSQL(운영), DDL 정본은 `design/cv_ddl.sql`

- **Decision**: 스키마는 SD_03 의 `cv_ddl.sql` 이 정본이다. 개발·시연은 SQLite 파일 DB(검증 완료된 환경), 운영은 PostgreSQL. ORM 을 쓰지 않고 SQLAlchemy Core(텍스트 SQL + 커넥션 풀)로 접근한다.
- **Rationale**: SD_03 이 29 테이블·14 뷰·4 트리거를 SQLite 에서 3종 검증했다. ORM 모델을 따로 두면 정본이 둘이 된다. Intent-Plan 의 React + FastAPI 선택지가 PostgreSQL 을 권장하고, Docker 없이도 로컬 설치가 가능하다. 시연(HG/시연웹 시나리오)은 노트북 한 대에서 돌려야 하므로 SQLite 가 맞다.
- **Alternatives**: SQLAlchemy ORM(정본 이중화), MariaDB(부분 UNIQUE 인덱스 미지원 — SD_03 §15-2 에서 트리거 대체 필요).
- **이식 작업**: `cv_ddl.sql` 의 SQLite 전용 6종(§15-2)을 PostgreSQL 용 `cv_ddl.postgres.sql` 로 변환하는 태스크를 둔다. 뷰의 `strftime('now')` → `CURRENT_TIMESTAMP`, `julianday` → `EXTRACT(EPOCH)`, `group_concat` → `STRING_AGG`, `RAISE(ABORT)` → `RAISE EXCEPTION`.

## R3. 모델 — 확정 저장소 실물 확인과 어댑터 결정 (Clarifications 3차 Q12)

- **확정**: 사용자 통보(2026-09-28) — `https://github.com/MaxTheTechy/yolo`. 초기 후보였던 `Ananya-Hegde2001/Crowd_Density_Estimator`(3×3 격자 인원수 대시보드, 라이선스 없음)는 쓰지 않는다.
- **확인 사실 (GitHub 열람)**: 교실 재실 모니터링 PoC. Ultralytics `ultralytics` 패키지의 **YOLOv8n(`yolov8n.pt`)** 으로 person 클래스(ID 0)만 검출, RTSP 카메라 입력, 인원수·점유율(인원/정원)을 SQL Server(SQLite 대안)에 기록, Flask 대시보드. 주요 파일 `detector.py`(검출), `occupancy.py`(점유 계산), `tracker.py`(2단계 ByteTrack 예정), `config.py`. 요구: Python 3.11+, ultralytics, opencv-python, flask, sqlalchemy, pyodbc, supervision, pandas. **라이선스 파일 없음.** README 원칙: "Process video locally. Do not store video. Do not store images. Store only occupancy metrics."
- **Decision**: 가져오는 것은 **가중치 `yolov8n.pt` 와 `detector.py` 의 person 검출 접근법(Ultralytics, 클래스 0, 신뢰도 임계)** 이다. 4필드 계약(BR-CV-28)은 본 프로젝트 `predict.py` 가 구현한다 — 계산 방식은 **R20(발 위치 × 표준 발자국 면적)**. `crowding_level` 은 ThresholdPolicy 매핑, `warnings` 는 R5 검사기. `model_package.contract_check_result = 'adapter'`, `model_crowding_level` 은 NULL(모델이 등급을 내지 않음).
- **Rationale**: 저장소의 점유율은 **인원수 / 정원** 기반이라 원천이 배제한 인원 카운트(Out of Scope 2)에 해당하고, 원천 FR-04 는 통합 점유 면적을 요구한다. 접근법(YOLOv8 person 검출)은 그대로 쓰되 면적 계산은 우리가 한다. 저장소의 "이미지 미저장" 원칙이 FR-11·BR-CV-09 와 같아 설계 충돌이 없다. YOLOv8n 은 YOLOv8s 보다 가볍고 빨라 CPU 에서 NFR-01(p95 2초) 여유가 커진다. 정확도가 부족하면 파일럿(P4) 결과로 `yolov8s.pt` 로 올린다(가중치 경로만 settings).
- **라이선스**: 저장소 자체는 없음. 가중치·`ultralytics` 는 AGPL-3.0 — 비영리 공공 과제라 소스 공개 조건과 충돌하지 않으나 운영 기관 배포 전 법무 확인(§16).
- **가져오지 않는 것**: Flask 대시보드, SQL Server/pyodbc, RTSP 스트리밍(Out of Scope 3), 트래커(supervision).
- **Alternatives**: 저장소 코드 통째 import(SQL Server·Flask 결합), 인원수만으로 점유율(FR-04·Out of Scope 2 충돌), 박스 합집합 면적(카메라 각도에 따라 과대 — R20 에서 배제), 세그멘테이션 모델(정확도 상승·지연 증가 — 파일럿 후).

## R4. 요청 규격 값 (SD_01 §16 7, G2)

- **Decision**: 형식 JPEG·PNG · 해상도 최소 320×240, 최대 4096×4096 · 용량 최대 10 MB · 일괄 프레임 수 최대 20장 · 정의되지 않은 항목 포함 시 422(Pydantic `extra="forbid"`). 손상 파일은 OpenCV 디코드 실패로 판정. 값은 `settings.py` 에서 조정 가능.
- **Rationale**: 관제 카메라 프레임(FHD 1920×1080, 1~3 MB)을 여유 있게 수용하면서 p95 2초(NFR-01)를 지키려면 4K 상한이 실용적이다. 20장 상한은 NFR-03(10장 일괄 = 단건 10배 이내)의 2배 여유. 422 는 Intent 핵심 이네이블러 "비정상 요청에 422".
- **Alternatives**: WebP 허용(관제 장비가 내지 않음), 무제한 일괄(응답 시간 예측 불가).

## R5. 판독 기준값 (SD_01 §16 7, G6, BR-CV-06)

- **Decision**: `blur` — 그레이스케일 라플라시안 분산 < 100. `low_light` — 평균 밝기 < 40 (0~255). `backlight` — 밝기 히스토그램의 상위 5%가 250 이상이면서 하위 30%가 30 이하(양극 분포). `low_confidence` — person 박스 평균 신뢰도 < 0.6(원천 값). `occlusion` — 박스 쌍 IoU > 0.5 인 비율이 30% 초과. 모델 추론 제한 시간 5초(초과 시 UC13 E2 → 판독 불확실). 기준값은 설정 가능, 파일럿(P4)에서 재조정.
- **Rationale**: Intent 핵심 이네이블러가 "라플라시안 변측 기반 선명도 검사, 평균 Confidence 0.6" 을 지목했다. 라플라시안 100 은 OpenCV 계열 블러 검출의 관행값이며 SC-06(의도적 블러 프레임 100% 경고)을 P4 로 검증한다.
- **Alternatives**: 딥러닝 품질 평가 모델(지연 증가), 고정 임계 대신 카메라별 캘리브레이션(파일럿 후 검토).

## R6. 호출 인증·권한 (SD_01 §16 2, G1)

- **Decision**: 연계 시스템·본 웹서비스는 `X-API-Key` 헤더의 API 키로 식별한다(키 → `caller_id`). 운영 관리자 기능(`/v1/admin/*`)은 별도 관리자 키(`X-Admin-Key`). 정보 차등은 없다(FR-16) — 키는 식별과 관리 권한 여부만 결정한다. 키 저장은 설정 파일(해시).
- **Rationale**: 가장 단순하고 FR-16 을 만족한다. 사용자 계정·세션이 원천에 없다. SD_03 은 권한 테이블을 두지 않았으므로(§16 2) 설정 파일 방식이 스키마와 맞는다.
- **Alternatives**: OAuth2/JWT(사용자 개념이 없어 과함), IP 허용 목록(웹서비스 배포 위치 미정).

## R7. 엔드포인트 경로·메서드·필드명 (SD_01 §16 11, UC_00 §8.3 26)

- **Decision**: `contracts/openapi.yaml` 에 확정. 접두 `/v1`. 진단 `POST /v1/diagnose`(multipart), 일괄 `POST /v1/diagnose/batch`, 후속 차량 `GET /v1/next-vehicle`, 실측 `POST /v1/measurements`·`/v1/measurements/batch`, 준비 `GET /v1/readiness`, 관리 `/v1/admin/cameras/{id}/roi`·`/v1/admin/vehicle-types/{id}/spec`·`/v1/admin/policies/threshold`·`/v1/admin/policies/validity`·`/v1/admin/mappings`(+`/csv`)·`/v1/admin/verification-runs`, 안내 `GET /v1/api-guide`. 필드명은 SD_03 컬럼명과 같다(`vacant_capacity_ratio`, `crowding_level`, `basis_type` …).
- **게이트 → HTTP 상태**: G0·G5 503, G1 401/403, G2 422, G3·G11 404, G4·G10 409, G8·G9 422(사유 목록), G6·G7·G12·G13 은 **200 + 상태 필드**(출력 차단형 — 오류가 아니다).
- **'API활용' 제공 방식**: FastAPI 자동 문서(`/docs`)를 **카탈로그**로 쓰고, 가이드라인·매뉴얼은 `GET /v1/api-guide` 가 마크다운을 반환하며 웹서비스 S9 가 렌더한다. G17 대조는 배포 전 `pytest` 가 `openapi.json` 과 `api_endpoint` 표를 비교한다.
- **Rationale**: SD_02 §14 사상 규칙 ⑤(출력 차단은 배지, 처리 중단은 블록)를 HTTP 로 옮긴 것. FastAPI 가 계약에서 문서를 생성하므로 BR-CV-30 "계약과 일치"가 구조적으로 보장된다.

## R8. 본 웹서비스의 범위 (UC_00 §8.3 27, SD_02 §16 5)

- **Decision**: 1차 릴리스의 웹서비스는 **운영·시연 화면**이다. SD_02 의 S0~S9 를 React 로 구현하되, 시민 공개 배포는 하지 않는다. S5·S7 은 시민 화면과 같은 값을 보여 주므로(FR-16) 시민 채널이 필요해지면 같은 컴포넌트를 재사용한다.
- **Rationale**: 원천 Out of Scope 4(시민용 화면은 연계 시스템 담당)와 추가 원천 2항(사용자가 웹서비스에 프레임 입력)을 동시에 만족하는 해석이다. 시연 시나리오(`HG/시연웹`)가 요구하는 것도 운영자가 조작하는 화면이다.
- **Alternatives**: 시민 공개 웹(접근 정책·낙인 문구 가이드 OR-03 확정 필요 — 후속 기능).

## R9. 카메라 등록 절차 (SD_01 §16 3, G3)

- **Decision**: `POST /v1/admin/cameras` 를 관리 API 에 추가한다. 운영 관리자가 카메라 식별자·설치 장소 유형·소속 노선/정류장·차량 유형을 등록한다. SD_02 S2 2.1 에 «카메라 등록» 버튼이 추가되고 G3 의 해제 주체가 운영 관리자로 확정된다.
- **Rationale**: UC6·7·12 사전조건이 모두 "카메라가 등록되어 있다"를 가정하는데 등록 경로가 없으면 G3 이 영구 벽이다. 새 UC 를 만들지 않고 UC6 의 앞 단계(A0)로 둔다 — 산출물이 `camera` 행 하나라 독립 목표라 보기 어렵다.
- **상류 갱신 필요**: UC_00 §8.4 3번 결정 기록, SD_03 `gate_event.resolver_role` 의 G3 'undefined' → 'operator'.

## R10. 정책 변경 시 보관 실측 재계산 (SD_01 §16 4, SD_03 §16 4)

- **Decision**: **재계산하지 않는다.** `camera_measurement.expires_at` 은 등록 시점의 규칙으로 고정. 새 규칙은 이후 등록되는 실측부터 적용.
- **Rationale**: H5 계약이 "적용된 유효 시간"을 응답에 포함하므로 등록 시점 값이 곧 계약이다. 재계산하면 이미 나간 응답과 저장값이 어긋난다(NFR-06). UC11 사후조건 (5)의 "판정 시점 계산" 해석과 다르지만, 시연 모드가 별도로 만료를 통과시키므로(BR-CV-26) 운영상 문제가 없다.
- **정책 이력**: 판본 테이블로 보관(SD_03 D4 채택).

## R11. 운행 정보 연계 장애 시 처리 (SD_01 §16 5)

- **Decision**: 매핑 저장은 `verify_status='unverified'` 로 **허용**하되 S2 에 "미검증" 배지를 붙이고, 연계 복구 후 배치가 재검증한다. 배차 간격은 마지막 값(`stale`)을 24시간까지 사용, 이후 기본 10분.
- **Rationale**: 시연·파일럿에서 BIS 장애가 준비 자체를 막으면 안 된다(HG/시연웹 §10-4). SD_03 이 이미 상태값으로 수용했다.

## R12. 노선·정류장 기준 정보와 외부 API (SD_01 §16 9, HG/시연웹 §10-3)

- **Decision**: 기준 정보(`route`·`stop`)는 TAGO 공공데이터포털에서 받은 CSV 를 관리 배치가 적재한다. 갱신 주체는 운영 관리자. 버스 도착·배차는 대전광역시 열린데이터 BIS API(인증키 필요), 도시철도는 대전교통공사 배차표 CSV 파일. 연계 모듈은 `external/` 패키지로 격리하고 인터페이스(`ArrivalProvider`, `HeadwayProvider`, `FleetProvider`)에 **고정 데이터 구현(`FixtureProvider`)** 을 함께 두어 시연·테스트에 쓴다.
- **Rationale**: NFR-08(외부 장애가 진단에 영향 없음)을 모듈 경계로 보장한다. 시연은 발표 시각의 실제 운행에 의존하지 않아야 한다.
- **구현 확인 (T047, 2026-09-29 인증키 발급 후 실측)**: 공공데이터포털 `apis.data.go.kr/6300000` 의 노선정보조회(`busRouteInfo` — getRouteInfo·getRouteInfoAll·getStaionByRoute, XML), 버스위치정보(`busposinfo/getBusPosByRtid`, XML), 버스정류소조회(`GetStatListService/getStatList`, JSON·XML — 기준 정보용). **도착 정보 API 는 없다.**
  - 배차 간격: `ALLO_INTERVAL`(평일)·`_SAT`·`_SUN` 분 — 한국 시간 요일로 고른다.
  - 차량 목록(G9 검증·자동완성): 위치 정보에 잡힌 운행 중 차량의 `PLATE_NO`(예: `대전75자1013`). 운행하지 않는 차량은 목록에 없으므로 운행 시간 밖 매핑은 `unverified` 가 될 수 있다(R11 로 허용).
  - 예상 도착 시각: 정류소·버스의 `TOTAL_DIST`(기점부터 누적 m) 차 ÷ 노선 평균 속도(`RUN_DIST_HALF` ÷ `RUN_TM`, 8~40 km/h 로 제한) — **추정값**이며 교통 상황을 반영하지 않는다.
  - 식별자: 노선은 `ROUTE_CD`(8자리). `ROUTE_NO` 는 유일하지 않다(`1` = 30300001·30300100·30300103) — 번호가 겹치면 조회하지 않는다. 정류장은 `BUS_STOP_ID`·`BUS_NODE_ID` 둘 다 허용. 기준 정보는 BIS 체계로 적재한다(R21-D5): `python -m cv_api.tools.fetch_bis_reference` → `bis_routes.csv`(route_id = `ROUTE_CD`)·`bis_stops.csv`(stop_id = `ROUTE_CD:BUS_STOP_ID` — `stop` 이 노선 하나에 속하는 구조라 합성) → `load_reference`. 공급자는 `:` 뒤를 `BUS_STOP_ID` 로 읽는다. 2노선 실측: 정류장 195개 적재, G11 통과, 도착 추정 반환.
  - 호출 한도 보호: 위치 15초, 노선·정류소 6시간 캐시. 인증키는 `backend/.env` 만(저장소 제외). 기본 공급자는 `fixture` 유지.

## R13. CSV 양식 (Assumptions 17)

- **Decision**: UTF-8(BOM 허용), 첫 행 열 이름 영문 `camera_id, vehicle_id, vehicle_type`(선택). 열 순서 무관. 행별 격리.
- **Rationale**: SD_03 컬럼명과 일치시켜 변환 없이 적재.

## R14. 일괄 검증 부분 반려·프레임별 카메라 (SD_01 §16 6)

- **Decision**: 한 묶음은 카메라 하나. 규격 위반 프레임은 그 프레임만 반려(`status='rejected'`)하고 나머지는 진단한다. 20장 초과는 묶음 전체 거부(422).
- **Rationale**: UC10 A4 "개별 실패 격리"와 일관.

## R15. 시험 호출 표식 (SD_01 §16 8)

- **Decision**: `diagnosis_request.kind='test_call'` 로 구분. 집계 뷰에 포함하되 운영 지표(P0 0.2)에서는 제외.

## R16. 응답 시간 계측 구간 (SD_01 §16 12)

- **Decision**: NFR-01 p95 2초는 `POST /v1/diagnose` 요청 수신부터 응답 완료까지(5.2~5.9). 준비 확인(5.1)·외부 조회(7.3)는 별도 엔드포인트라 제외. `bench.py` 가 100회 호출로 p95 를 낸다. `GET /v1/next-vehicle` 목표는 외부 API 지연을 제외한 서비스 처리 1초로 둔다 `[제안]`.

## R17. 보존 기간 (Q4)

- **Decision**: 정하지 않는다. `settings.RETENTION_DAYS` 를 NULL(무기한)로 두고 폐기 배치는 값이 있을 때만 동작한다.

## R18. 관제 판단 저장 여부 (SD_02 §16 14)

- **Decision**: 저장하지 않는다(화면 내 표시). 상류에 저장 단계가 없다.

## R19. 열차 차내 카메라 (SD_02 §16 8)

- **Decision**: 1차 릴리스는 `place_type` 두 값(platform, bus_in) 유지. 파일럿이 지하철로 확정되면 `train_in` 추가(CHECK·트리거 동시 수정).
- **갱신 (2026-09-29, R21-D8)**: 사용자 확인 — 실측 카메라는 버스·열차 차량 안에 있다. `train_in` 을 지금 추가했다(CHECK·트리거 `trg_cm_in_vehicle_camera`·`db.py` 마이그레이션·화면 선택지).

## R20. 혼잡도 계산 방식 — 발 위치 × 표준 발자국 면적, 인원수 병기 (2026-09-28 사용자 채택)

- **Decision**: 검출된 각 박스의 아래 중앙점을 발 위치로 보고, 발 위치가 ROI 다각형 안인 사람만 센다(FR-03). `occupied_area = count × footprint_m2`(기본 0.30 ㎡, 카메라·ROI 별 보정값 우선), `occupied_area_ratio = occupied_area / roi_area_m2 × 100`(상한 100), `vacant = 100 − occupied`. 응답에 `person_count` 를 함께 넣어 정원 대비 인원수도 제공한다. ROI 등록 시 실제 바닥 면적 `roi_area_m2` 와 선택 보정값 `footprint_m2` 를 입력한다.
- **Rationale**: 박스 합집합은 박스가 몸 전체를 감싸 카메라 각도에 따라 과대 계산되고, 인원수만 쓰면 원천 Out of Scope 2(인원 카운트)와 FR-04(통합 점유 면적)에 어긋난다. 발 위치는 각도와 무관하게 바닥에 있고, 발자국 합은 겹치지 않으므로 FR-04 의 "통합 점유 영역"을 만족한다. 두 기준을 같은 계산에서 얻어 파일럿(S4)에서 어느 쪽이 SC-01·02 를 먼저 맞추는지 비교할 수 있다. 상세 비교는 `x_pym/모델선정.md`.
- **한계와 승격 경로**: 완전히 가려진 사람은 어느 방식이든 누락된다(만원 구간 과소). `occlusion` 경고와 "판독 불확실"이 이를 표시하고, 파일럿에서 혼잡 구간 정확도가 부족하면 밀도 지도 모델(CSRNet 류)로 `Detector` 를 교체한다.
- **Alternatives**: 박스 합집합 면적(배제), 인원수 / 정원(단독 사용 배제, 병기로 수용), 세그멘테이션 마스크 면적(정확하나 지연 증가).
- **미결**: `footprint_m2` 초기값(0.25~0.35)과 카메라별 보정 절차 — 파일럿 데이터로 정한다(§16).

---

## R21. 구현 단계 결정 (2026-09-29 사용자, 미해결 항목 일괄 검토)

구현 중 남은 미해결 항목을 사용자가 하나씩 정했다. 문서의 상태 칸은 "R21-Dn" 으로 인용한다.

| # | 항목 | 결정 | 반영 |
|---|---|---|---|
| D1 | 배정 포트 9544 의 역할 | **외부 연계용 공개 API.** 한 프로세스가 같은 전체 앱을 9544·9524 두 포트로 연다(모델 적재·운영 루프 1회). 9524 는 웹 프론트(9504) 프록시 대상. 관리 API 도 두 포트에 같게 있고 관리자 키로 보호 | `cv_api/serve.py`, `vite.config.ts` |
| D2 | PostgreSQL 검증 방법 | 127.0.0.1 임시 포트의 Docker 를 허용했으나 이 계정은 Docker 권한이 없어 **포트 없이 유닉스 소켓으로 도는 `pgserver`(PostgreSQL 16.2)** 로 대체 | `tests/test_ddl_postgres.py`, SD_03 §15-2 |
| D5 | BIS 실연동·식별 체계 | **2026-09-29 변경(T096): 실제 BIS 로 전환, 시연은 102번(30300037)·충남대학교.** 처음 결정은 "시연은 fixture 유지". BIS 체계 기준 정보 적재 도구 준비 — `route_id = ROUTE_CD`, `stop_id = "ROUTE_CD:BUS_STOP_ID"`(정류장 하나가 노선 하나에 속하는 `stop` 스키마를 바꾸지 않으려는 합성 키) | `cv_api/tools/fetch_bis_reference.py`, R12 |
| D6 | 시연 사진 | 팀원이 자유 이용 사진을 모아 `backend/samples/` 에 넣는다 | T054 |
| D7 | FR-04 문구와 R20 | **FR-04·BR-CV-02 개정** — "겹치지 않는 표준 발자국 면적의 합으로 통합 점유 면적을 계산한다" | spec FR-04, UC_01·04·13 |
| D8 | 승강장 카메라 프레임 + 차량 번호 실측 (UC10 A3) | 처음에는 "허용"으로 받아 승강장 실측을 열었으나(커밋 2e7ec7f), 같은 날 사용자가 **"승강장 카메라가 아니라 열차(버스) 안의 카메라"** 라고 정정 → **승강장 실측은 거부(G10) 복원 + 열차 차내 유형 `train_in` 추가.** 실측은 차내(`bus_in`·`train_in`) 카메라만 | DDL CHECK·트리거, `db.py` 마이그레이션, `services/measurement.py`, 화면 선택지(`api/place.ts`), R19 |
| D9 | 이미 만료된 촬영 시각의 실측 | 현재대로 저장 + `already_expired` 표시(후속 차량 조회에는 만료라 쓰이지 않음) | 변경 없음 |
| D10 | C7 «요청 보내기» 전달 경로 | S1 에 '받은 요청' 목록 — `GET /v1/admin/gate-events?requested_only=true`(미해제·요청됨). 새 테이블 없음 | S1, `repo/ops.py` |
| D11 | 수작업 측정값 저장 | 저장 유지(SD_03·구현) → SD_01 §7-3 을 맞춤 | SD_01 |
| D12 | 버스·열차 식별자 충돌 | 열차 도입 때 (mode, id) 키로. BIS 번호는 `대전75자1013` 형식이라 1차는 충돌 가능성 낮음 | 보류 |
| D13 | S7 갱신 주기 | ~~30초 (BIS 위치 캐시 15초와 균형)~~ → **2026-09-29 변경(T102): 수동 조회**(«조회»를 누를 때만), 선택 «자동 갱신»은 30초 간격·5분 뒤 자동 꺼짐·다른 탭이면 멈춤. BIS 위치 캐시 60초. 사유: 화면을 열어 두기만 해도 30초마다 호출해 공공데이터포털 일일 한도(429) 초과 | `pages/NextVehicle.tsx`, `settings.BIS_POS_CACHE_S` |
| D14 | 신뢰 구간(BR-CV-20)·렌즈 오염 경고 | 파일럿 데이터로 결정 | 보류 |

## R22. 혼잡도 = 인원 ÷ 차량 전체 정원 (2026-09-29 사용자 결정, 시연 중 정확도 문제)

- **문제**: 실시간 영상 진단(T085)에서 사람이 그대로인데 혼잡도가 장면마다 바뀌고, 최근 하루 진단 194건 중 73건(38%)이 판독 불확실이었다(저신뢰 58·흐림 15·어두움 7). 저신뢰 건의 평균 신뢰도는 0.45~0.6 — 기준 0.6 바로 아래.
- **원인**: (1) 검출기는 신뢰도 0.25 이상을 모두 사람으로 내고, 평균 신뢰도를 ROI 밖·애매한 박스까지 넣어 계산했다. (2) 신뢰도 0.25 근처의 사람은 장면마다 잡혔다 빠졌다 하며, R20 에서는 1명이 약 4.6%p(0.30㎡ ÷ 6.5㎡)라 값이 크게 흔들렸다.
- **Decision**:
  - **인원** = 검출 신뢰도 ≥ 인원 세기 기준(`threshold_policy.count_conf_min`, 기본 0.4) 이고 발 위치가 ROI 안인 사람 수. 기준은 등급 기준 판본에 딸려 S3 에서 조정한다(진단마다 `threshold_policy_id` 로 재현 가능).
  - **점유율(occupied_area_ratio)** = 인원 ÷ 차량 전체 정원(`vehicle_spec.capacity`) × 100, 100 상한. 인원 > 정원이면 `over_capacity` 로 "정원 초과" 표시. 잔여 = 100 − 점유율, 잔여 인원 = 정원 − 인원(하한 0) — 뷰 `v_assessment` 식 그대로 성립.
  - **평균 신뢰도(FR-09)** = 셈에 든 사람만으로. 배경·창밖의 애매한 박스가 판독 불확실을 만들지 않는다. 기준 0.6 은 그대로.
  - **정원 없음(G7)**: 인원만 산출, 등급 "판독 불확실" + `unknown`(raw `capacity_missing`) 경고. 컬럼 NOT NULL 을 지키려고 점유율은 0 으로 저장한다(판독 불확실이라 확정값으로 쓰이지 않음).
  - **차량 합산(FR-13e, BR-CV-27)**: 시각 창 안·유효한 카메라별 최신 실측 인원의 합 ÷ 차량 전체 정원. `vehicle_measurement.persons_sum`·`capacity` 기록. 커버리지·부분 합산 표시는 그대로.
  - **영상 화면**: 최근 5칸 인원 중앙값이 같은 방향으로 2칸 연속 달라질 때만 표시 인원을 바꾼다(T086 을 인원 기준으로 전환).
  - 컬럼 이름 `occupied_area_ratio` 는 계약·뷰 호환을 위해 그대로 두고 의미만 바꾼다. `roi.roi_area_m2`·`footprint_m2` 는 기록용으로 남기고 계산에 쓰지 않는다.
- **Rationale**: 운영 관리자가 이미 입력하는 정원을 그대로 쓰므로 보정 추정값(발자국 면적·실제 바닥 면적)이 사라지고, "30 / 45명" 은 누구나 읽을 수 있다. 1명당 변동 폭도 정원 45명 기준 약 2.2%p 로 작아진다.
- **한계**: (1) 흔들림의 근본은 인원 세기 자체이므로 인원 세기 기준과 영상 중앙값이 함께 있어야 한다. (2) 만원일수록 겹침으로 적게 센다 — 가장 중요한 순간에 덜 혼잡하게 보이는 방향이라 `occlusion` 경고를 유지한다. (3) 카메라가 차량 일부만 보면 합산 인원이 모자라 여유롭게 보인다 — 커버리지 표시로 드러낸다. (4) Out of Scope 2(인원 카운트) 문구를 개정했다 — 원천 Intent 와 달라지므로 발주 측 확인 필요.
- **검출 입력 크기 (2026-09-29 사용자 결정, T090)**: YOLO 입력 640 → 1280(`MODEL_IMGSZ`). 밀집 샘플(역 대합실, 실제 약 100명 이상)에서 평균 5.4 → 12.8명으로 늘었으나 여전히 크게 과소. 머리 검출 모델·군중 계수(밀도 지도) 모델 비교는 **보류** — 사용자가 1280 으로 당분간 진행하기로 함. 만원 장면 과소 계수는 알려진 한계로 남는다.
- **Alternatives**: 카메라별 구역 정원(사용자가 차량 전체 정원 + 합산을 선택), 정원 초과 그대로 표시(111% — 사용자가 100% 상한 선택), R20 유지 + 화면 평활만(T086 — 흔들림은 줄었으나 판독 불확실 과다가 남음).
- **반영**: spec 4차(FR-04·FR-13e·Out of Scope 2·Assumptions 19), `predict.compute_occupancy`, `services/diagnosis.py`·`measurement.py`, DDL(`threshold_policy.count_conf_min`, `vehicle_measurement.persons_sum`·`capacity`)·`db.py` MIGRATIONS, 응답 `capacity`·`over_capacity`·`persons_sum`, S3·S5·S6·C3 화면, T087.

## R23. 2026-09-30 결정 (사용자, 미해결 정리)

| # | 항목 | 결정 | 반영 |
|---|---|---|---|
| E1 | 예약된 등급 기준 판본 2·3번(인원 세기 기준 0.4, 09-30 13:21·13:51 KST) | **취소** — 머리 모델 기준 0.2 유지. 원인이던 S3 기본값("내일 이 시각")·0.4 고정 문구를 고침 | T113 |
| E2 | 사이드바·화면 접근 기준 | 권한 매트릭스(유효 권한) 하나로 — 역할 기준 잔재(`useAdmin`) 정리 | T116 |
| E3 | 새 유스케이스 | **UC16 계정·API 키 관리, UC17 역할·권한 관리, UC18 카메라 가동 관리** 신설 — 흩어진 사전조건·예외(UC_00 §8.3 30)를 모은다 | UC_16~18, UC_00 |
| E4 | 계정 정보 보관·파기 (SD_03 §16 17) | 역할·상태 **변경 이력은 지금 기록**(`account_change`), 보관·파기 **기간은 운영 기관 정책(Q4)과 함께** 확정 | T117 |
| E5 | 대전 도시철도 후속 열차 조회 | **1차 범위 제외**(spec Out of Scope 9). 공개 API 에 실시간 위치·편성 정보가 없어 실측 연결 불가. 기관 협약 시 2차. 열차 차내 프레임의 현재 진단은 지원 | spec |
| E6 | 커밋 | 사용자가 요청할 때 | — |

함께 고친 결함: 모델 판본 기록이 적재한 가중치를 따르지 않던 문제(T115), `role_permission` 이중 정의(T114).

## 확인된 환경

| 항목 | 값 |
|---|---|
| 로컬 Python | 3.9.6 (계획은 3.11 권장 — Ultralytics 8.x 는 3.8+ 지원하므로 3.9 로도 동작. venv 생성 시 3.11 이 있으면 사용) |
| fastapi·ultralytics·torch·cv2 | 미설치 (quickstart 에서 설치) |
| SQLite | 3.51.0 — `cv_ddl.sql` 검증 완료 |
| Node | 프론트엔드용 Node 20 LTS 필요 (확인 필요) |
| 모델 저장소 | `MaxTheTechy/yolo` 접근 가능. 라이선스 파일 없음. `yolov8n.pt`(Ultralytics) 사용 |
