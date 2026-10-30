# 매뉴얼 — 절차와 예시

> 판본 v1.3 (2026-09-29). 주소 `https://p4.sumzip.com/API`, API 키는 로그인 후 신청 → 운영 관리자 승인.

## 로그인과 API 키 받기
웹 화면과 API 는 **로그인(또는 승인된 API 키) 없이 쓸 수 없다**. 키 없이 되는 것은 회원가입·로그인·역할 표·준비 상태·API 안내뿐이다.
1. **회원가입** — 웹 첫 화면 «회원가입» 또는 `POST /v1/auth/signup` (아이디·이름·비밀번호 8자 이상·소속). 가입하면 바로 **일반 사용자**다.
2. **로그인** — 웹 첫 화면 또는 `POST /v1/auth/login` → 토큰(12시간). 일반 사용자는 홈·현재 프레임 진단·버스 조회·API 활용을 쓴다.
3. **키 신청** — 웹 «내 API 키» 또는 `POST /v1/auth/keys` (`{"name": "정류장 전광판"}`) → `cvk_…` 원문이 **이때 한 번만** 나온다. 연계 시스템마다 따로 신청하고 안전한 곳에 보관한다.
4. **운영 관리자 승인** — 운영 관리자가 «계정·키 관리»에서 승인한다. 승인 전에 부르면 `403 KEY_PENDING`, 반려되면 `403 KEY_REJECTED`.
5. **호출** — 연계 시스템은 모든 요청에 `X-API-Key: cvk_…` 를 보낸다. 잃어버렸거나 샜으면 폐기하고 새로 신청한다.

역할(유스케이스 액터): 일반 사용자(가입 — 본 웹서비스 이용자·연계 개발자) · 연계 시스템(승인된 키) · 관제 담당자·운영 관리자(운영 관리자가 부여). 권한 표는 `GET /v1/auth/roles`.

## 절차
누가 쓰느냐에 따라 필요한 것이 다르다. **버스가 얼마나 붐비는지 보기만 하는 쪽은 카메라 번호를 몰라도 된다.**

### A. 보는 쪽 — 버스 상태 조회 (시민 안내 앱·전광판·이용자)
1. **노선 찾기** `GET /v1/reference/routes?q=102` → `route_id`(102번 = `30300037`).
2. **정류장 찾기** `GET /v1/reference/stops?route_id=30300037&q=충남대` → `stop_id`. 같은 이름이 양방향에 있으면 "충남대학교 (홈플러스유성점 방면)"처럼 다음 정류장으로 구분된다. 거꾸로 정류장에서 시작하면 `GET /v1/reference/stops/{stop_id}/routes` 가 그 정류장에 서는 버스 번호만 준다(노선마다 그 노선의 `stop_id`).
3. **다가오는 버스 조회** `GET /v1/next-vehicle?route_id=&stop_id=&limit=` → 차량별 도착 예정 시각과, 실측이 있으면(`basis_type: measured`) **`persons_sum` / `capacity` 명·혼잡 등급·여유 %**.
4. **(선택) 버스 번호로 바로 조회** `GET /v1/vehicles/대전75자9022` → 그 버스의 최신 유효 실측. 실측이 없거나 만료면 `no_measurement`("정보 없음"으로 표시).

### B. 보내는 쪽 — 사진 제출 (카메라가 달린 버스·관제 시스템, 운영 관리자)
1. **준비 확인** `GET /v1/readiness` → `ready`(키 없이도 된다). `preparing` 이면 `detector.note` 를 보고 잠시 후 재확인.
2. **카메라 확인** `GET /v1/reference/cameras` → 내 카메라의 `camera_id` 와 `capacity`(차량 전체 정원). 정원이 `null` 이면 인원만 나온다.
3. **프레임 제출** `POST /v1/diagnose` (multipart: `camera_id`, `frame`, `captured_at` 선택). 영상·실시간이면 1초에 1장, 한 번에 1건.
4. **결과 해석** `person_count` / `capacity` 명, `occupied_area_ratio`(혼잡 %), `over_capacity`, `vacant_capacity_ratio`(여유 %), `crowding_level`, `warnings`, `notice`. `uncertain` 이면 참고용.
5. **차량 실측** 버스 안 카메라의 프레임을 `POST /v1/measurements`(`vehicle_id` = BIS 차량 번호, `camera_id` = 그 버스에 연결된 카메라)로 보내면 A 의 3·4번 조회에 `measured` 로 나온다.

## 예시
```bash
BASE=https://p4.sumzip.com/API          # 내부망이면 http://<서버>:9544
K="X-API-Key: <발급받은 호출 키>"

# A. 보는 쪽 — 102번이 충남대학교에 언제, 얼마나 붐벼서 오나
curl -s -G -H "$K" "$BASE/v1/reference/routes" --data-urlencode "q=102"
curl -s -G -H "$K" "$BASE/v1/reference/stops" -d route_id=30300037 --data-urlencode "q=충남대"
curl -s -H "$K" "$BASE/v1/next-vehicle?route_id=30300037&stop_id=30300037:42620&limit=4"   # 충남대학교 (홈플러스유성점 방면)
curl -s -H "$K" "$BASE/v1/vehicles/%EB%8C%80%EC%A0%8475%EC%9E%909022"                       # 대전75자9022 (URL 인코딩)

# B. 보내는 쪽 — 카메라 사진 진단
curl -s "$BASE/v1/readiness"
curl -s -H "$K" "$BASE/v1/reference/cameras"
curl -s -H "$K" -F camera_id=CAM-DEMO-01 -F frame=@bus.jpg "$BASE/v1/diagnose"
```

진단 응답(요약):
```json
{"camera_id": "CAM-DEMO-01", "person_count": 3, "capacity": 80, "occupied_area_ratio": 3.75, "over_capacity": false,
 "vacant_capacity_ratio": 96.25, "crowding_level": "free", "is_reference_only": false, "remaining_persons": 77,
 "mean_confidence": 0.85, "warnings": [], "notice": "이 수치는 통계적 추정치입니다", "response_ms": 91}
```
→ 화면 표시 예: **"3 / 80명 · 혼잡 4%"**, 보조 "여유 96%". `over_capacity: true` 면 "혼잡 100% · 정원 초과".

후속 차량 응답(요약, 시각은 UTC) → 화면 표시 예: "대전75자9022 · 3분 후 · 3 / 80명 · 여유(착석 가능)", "대전75자9011 · 6분 후 · 정보 없음":
```json
{"route_id": "30300037", "stop_id": "30300037:42620", "vehicles": [
  {"vehicle_id": "대전75자9022", "expected_arrival_at": "2026-09-29T04:14:00", "basis_type": "measured", "persons_sum": 3, "capacity": 80, "vacant_ratio": 96.25, "crowding_level": "free"},
  {"vehicle_id": "대전75자9011", "expected_arrival_at": "2026-09-29T04:17:24", "basis_type": "no_measurement", "vacant_ratio": null}]}
```

규격 밖 사진(HEIC·큰 사진)이나 영상은 웹 화면용 변환 경로를 쓴다 — 응답에 `normalization`(무엇을 바꿨는지)이 붙는다.
```bash
curl -s -H "$K" -F camera_id=CAM-DEMO-01 -F file=@IMG_0001.HEIC "$BASE/v1/web/diagnose"
curl -s -H "$K" -F camera_id=CAM-DEMO-01 -F file=@clip.mp4 -F interval_s=2 "$BASE/v1/web/diagnose-video"
```

## 오류·경고 대처
| 상태 | 뜻 | 대처 |
|---|---|---|
| 401 / 403 G1 | 키 없음 / 키 틀림, 또는 호출 키로 관리 API 호출 | 호출 키 확인. 관리 기능은 운영 관리자만 |
| 503 G0/G5 | 준비 중·모델 불가 | 대기 후 재시도. 운영 관리자에게 요청(`gate_event_id` 로 `POST /v1/gate-events/{id}/request`) |
| 422 G2 | 규격 외 | `allowed_spec` 대로 수정하거나 `/v1/web/diagnose` 사용 |
| 404 G3/G11 | 카메라·노선·정류장 없음 | 이름으로 다시 찾기(`/v1/reference/routes`·`/stops`·`/cameras`), 운영 관리자에게 등록 요청 |
| 409 G4/G10 | ROI·매핑 없음 | 운영 관리자에게 요청 보내기 |
| 200 + uncertain | 판독 불확실 또는 정원 미등록 | `warnings` 확인 — 화질이면 재촬영, 정원 미등록이면 인원만 표시 |
| 200 + unavailable (next-vehicle) | BIS 연계 지연 | "운행 정보 연결 지연"으로 표시, 잠시 후 재조회 |

## 시연 모드 해석
- `demo_mode: true` 응답은 사전 촬영 프레임을 등록 시각 기준으로 유효 처리한 것이다. 실운영 값이 아니다.
- 시연용 카메라(CAM-DEMO-01~03)는 운영 관리자가 S8 «102번 운행 차량으로 다시 연결»로 곧 도착할 실제 버스에 연결한다.

## 운영 관리자 (참고)
- 웹 화면 오른쪽 위 **«관리자 로그인»**에 관리자 키를 넣으면 운영 관리자 메뉴(S1~S4·S8)가 열린다. 키는 그 브라우저에만 저장된다.
- 검출기: `GET /v1/admin/detector` 로 상태, `POST /v1/admin/detector/preload` 로 재적재. YOLOv8n(프로세스 내, 입력 1280px)은 수 초, Ollama 비전 모델은 10~30초.
- 호출 키 발급·교체는 서버 설정(`API_KEYS`, 연계처별 `이름:sha256:<hex>`)에서 한다 — `backend/README.md` "인증".

## 부록. 엔드포인트 전체 목록 (69개)
주소 앞에 `https://p4.sumzip.com/API`(내부망은 `http://<서버>:9544`)를 붙인다. 입력·출력 형식과 시험 호출은 `/API/docs`(Swagger). 이 표는 실제 서버 명세와 자동 대조된다.

### A. 연계 시스템·일반 사용자 — 승인된 API 키 `X-API-Key` 또는 로그인 토큰 (21개)
| # | 방식 | 주소 | 하는 일 |
|---|---|---|---|
| 1 | GET | `/v1/reference/routes` | 노선 찾기 — "102" → 102번(`30300037`) |
| 2 | GET | `/v1/reference/stops` | 정류장 찾기 — 노선의 정류장, 또는 "충남대" 이름 검색 |
| 3 | GET | `/v1/reference/stops/{stop_id}/routes` | 그 정류장에 서는 버스 번호만 — 노선마다 그 노선의 `stop_id` (같은 정류소 ID) |
| 4 | GET | `/v1/next-vehicle` | 정류장에 다가오는 버스들과 실측 인원 / 정원·여유도 (실제 BIS) |
| 5 | GET | `/v1/vehicles/{vehicle_id}` | 버스 번호로 그 버스의 최신 상태 (인원 / 정원·혼잡) |
| 6 | GET | `/v1/readiness` | 서버 준비 상태 확인 (키 없이도 된다) |
| 7 | POST | `/v1/diagnose` | 사진 1장 → 인원 / 정원, 혼잡 %, 등급, 경고 (보내는 쪽) |
| 8 | POST | `/v1/measurements` | 버스 안 카메라 사진으로 실측 등록 → 3·4번에 "실측"으로 나온다 (보내는 쪽) |
| 9 | GET | `/v1/api-guide` | API 안내 (카탈로그·가이드라인·매뉴얼·모델 카드) |
| 10 | GET | `/v1/reference/cameras` | 카메라 목록과 현재 정원 (보내는 쪽) |
| 11 | GET | `/v1/reference/cameras/{camera_id}` | 카메라 1대 현황 |
| 12 | GET | `/v1/reference/cameras/{camera_id}/roi` | 현재 관심영역(ROI) 다각형 — 화면 윤곽 표시용 |
| 13 | GET | `/v1/reference/threshold` | 현재 등급 기준(여유·혼잡 경계)과 인원 세기 기준 |
| 14 | GET | `/v1/reference/ops-status` | 운영 상태 요약 (시연 모드, ROI 검증 필요 카메라, 오늘 만료 실측) |
| 15 | POST | `/v1/gate-events/{event_id}/request` | 차단됐을 때 운영 관리자에게 해제 요청 보내기 (`gate_event_id`) |
| 16 | GET | `/v1/auth/whoami` | 이 키가 이용자(caller)인지 관리자(admin)인지 확인 |
| 17 | POST | `/v1/web/diagnose` | 규격 밖 사진(HEIC·큰 사진)을 규격으로 바꿔 진단 |
| 18 | POST | `/v1/web/diagnose-video` | 영상에서 간격마다 장면을 뽑아 진단 + 추이 |
| 19 | POST | `/v1/web/measurements` | 규격 밖 사진을 바꿔 실측 등록 |
| 20 | GET | `/v1/web/samples` | 시연용 샘플 사진·영상 목록 |
| 21 | GET | `/v1/web/samples/{file}` | 샘플 파일 내려받기 |

### A2. 계정·API 키 — 회원가입·로그인 (8개)
키 없이 가입·로그인하고, 로그인 토큰(`Authorization: Bearer …`)으로 내 키를 신청·관리한다.

| # | 방식 | 주소 | 하는 일 |
|---|---|---|---|
| 22 | POST | `/v1/auth/signup` | 회원가입 — 바로 일반 사용자 |
| 23 | POST | `/v1/auth/login` | 로그인 → 토큰(12시간). 정지된 계정이면 403 ACCOUNT_DISABLED |
| 24 | GET | `/v1/auth/roles` | 역할·권한 표 (유스케이스 액터 기준, 키 없이) |
| 25 | POST | `/v1/auth/logout` | 로그아웃 (토큰 폐기) |
| 26 | GET | `/v1/auth/me` | 내 계정·역할·권한 |
| 27 | GET | `/v1/auth/keys` | 내 API 키 목록 (앞자리·상태 승인 대기/사용/반려·마지막 사용 — 원문 없음) |
| 28 | POST | `/v1/auth/keys` | API 키 신청 — 연계 시스템마다 하나, **원문은 이때 한 번만** 보인다. 운영 관리자 승인 뒤 쓸 수 있다 |
| 29 | DELETE | `/v1/auth/keys/{key_id}` | 내 API 키 폐기 — 즉시 거부된다 |

### B. 운영 관리자 전용 — 운영 관리자 로그인(또는 최초 관리자 키 `X-Admin-Key`) 필요 (40개)
호출 키로 부르면 401, 다른 역할로 로그인했으면 403(G1). 관제 담당자는 운영 상태·차단 이벤트·운영 지표·카메라 현황·카메라 전원 표를 **읽기만** 할 수 있다.

| # | 방식 | 주소 | 하는 일 |
|---|---|---|---|
| 30 | GET | `/v1/admin/cameras` | 카메라 목록·현황 |
| 31 | POST | `/v1/admin/cameras` | 카메라 등록 |
| 32 | GET | `/v1/admin/cameras/{camera_id}` | 카메라 1대 현황 |
| 33 | GET | `/v1/admin/cameras/{camera_id}/roi` | ROI 판본 목록 (이력 포함) |
| 34 | POST | `/v1/admin/cameras/{camera_id}/roi` | ROI 등록·수정 (UC6) |
| 35 | POST | `/v1/admin/vehicle-types/{vehicle_type_id}/spec` | 차량 전체 정원 등록·수정 (UC7) |
| 36 | GET | `/v1/admin/fleet` | 지금 운행 중인 BIS 차량 목록 (매핑 자동완성) |
| 37 | GET | `/v1/admin/mappings` | 카메라↔버스 연결 목록 |
| 38 | POST | `/v1/admin/mappings` | 카메라를 버스 번호에 연결 (UC12) |
| 39 | DELETE | `/v1/admin/mappings/{map_id}` | 연결 해제 |
| 40 | POST | `/v1/admin/mappings/csv` | CSV 로 한꺼번에 연결 |
| 41 | GET | `/v1/admin/policies/threshold` | 등급 기준 현재·이력 |
| 42 | POST | `/v1/admin/policies/threshold` | 등급 기준·인원 세기 기준 변경 (UC8) |
| 43 | GET | `/v1/admin/policies/validity` | 실측 유효 시간 규칙·시연 모드·노선별 미리보기 |
| 44 | POST | `/v1/admin/policies/validity` | 유효 시간 규칙·시연 모드 설정 (UC11) |
| 45 | POST | `/v1/diagnose/batch` | 사전 녹화 사진 여러 장 일괄 진단 (UC4) |
| 46 | POST | `/v1/admin/verification-runs` | 사람이 센 값과 비교해 정확도 판정 (SC-01·02) |
| 47 | POST | `/v1/measurements/batch` | 시연용 사전 촬영 사진 일괄 실측 등록 |
| 48 | GET | `/v1/admin/ops-status` | 운영 상태 (S0) |
| 49 | GET | `/v1/admin/gate-events` | 열린 차단 목록, 받은 요청 |
| 50 | GET | `/v1/admin/audit` | 집계 기록 (누가 언제 진단했나 — 개인 정보 없음) |
| 51 | GET | `/v1/admin/quality-metrics` | 시간대·조도별 신뢰도 지표 |
| 52 | GET | `/v1/admin/detector` | 검출 모델 적재 상태 |
| 53 | POST | `/v1/admin/detector/preload` | 검출 모델 다시 올리기 |
| 54 | GET | `/v1/admin/integrations` | 웹서비스 연동 목록 |
| 55 | POST | `/v1/admin/integrations` | 웹서비스 연동 등록 |
| 56 | POST | `/v1/admin/integrations/{integration_id}/test` | 연동 시험 호출 |
| 57 | POST | `/v1/admin/demo/bis-remap` | 시연 카메라를 곧 도착할 102번 버스로 다시 연결 (S8) |
| 58 | GET | `/v1/admin/camera-power` | 카메라 전원 관리 표 — 호선·차량번호·칸·운행 상태·정원·현재 인원·밀집도·동작여부 |
| 59 | POST | `/v1/admin/cameras/{camera_id}/power` | 카메라 켜기·끄기. 꺼진 카메라는 진단 요청을 409(`CAMERA_POWER_OFF`)로 거부, 켜면 주기마다 자동 진단 |
| 60 | PATCH | `/v1/admin/cameras/{camera_id}/operation` | 칸 위치·프레임 소스(스냅샷 URL 또는 `sample:<파일>`)·진단 주기(초) 설정 |
| 61 | GET | `/v1/admin/accounts` | 계정 목록 (`status` 로 거르기) |
| 62 | POST | `/v1/admin/accounts` | 계정 만들기 (관제 담당자·운영 관리자 등 — 바로 사용) |
| 63 | PATCH | `/v1/admin/accounts/{account_id}` | 정지(`status=disabled`)·해제(`active`)·역할 변경 |
| 64 | GET | `/v1/admin/accounts/{account_id}/changes` | 역할·상태 변경 이력 — 누가 언제 무엇을 바꿨는지 (최신 순) |
| 65 | GET | `/v1/admin/api-keys` | API 키 전체 (앞자리·소유자·상태·마지막 사용). `status=pending` 이면 승인 대기 |
| 66 | PATCH | `/v1/admin/api-keys/{key_id}` | API 키 승인(`status=active`)·반려(`rejected`) |
| 67 | DELETE | `/v1/admin/api-keys/{key_id}` | API 키 폐기 |
| 68 | GET | `/v1/admin/rbac` | 권한 매트릭스 — 역할×기능 유효 권한·기본값·잠긴 칸 (S10) |
| 69 | PUT | `/v1/admin/rbac` | 권한 매트릭스 저장 — 권한마다 허용 역할. 잠긴 칸(운영 관리자 열·계정/관리 행)은 422 |

- 비슷한 것이 두 벌인 이유: 10~14번(이용자)은 **현재 값 보기 전용**, 30·32·33·41·43번(관리자)은 **이력까지 보고 바꾸기**다.
