# Quickstart — 001-crowd-vacancy-api

**목적**: 개발자가 로컬(Docker 없음)에서 진단 API 서버와 웹서비스를 띄우고, 시연 시나리오(`HG/시연웹/01-시연-시나리오.md`) 준비 단계 P1~P6 를 한 번에 재현한다.

## 0. 전제

| 항목 | 값 |
|---|---|
| OS | macOS / Linux (Windows 는 venv 활성화 명령만 다름) |
| Python | 3.11 권장 (3.9.6 도 동작 — research.md 확인된 환경) |
| Node | 20 LTS (웹서비스) |
| DB | SQLite 파일(기본). 운영은 PostgreSQL 15 (`DATABASE_URL` 로 전환) |
| GPU | 선택. CPU 로도 YOLOv8n 단건 추론 ~0.1~0.4초 |
| 외부 키 | 대전 BIS(공공데이터포털) 인증키 — 없으면 `EXTERNAL_PROVIDER=fixture` 로 고정 데이터 사용 |

## 1. 백엔드 (한 프로세스, 포트 9544·9524) — P1 1.1~1.4

배정 포트: 웹 프론트 **9504** · 백엔드 **9544**(외부 연계용 공개 API)·**9524**(웹 프론트의 프록시 대상). 백엔드는 한 프로세스가 같은 전체 앱을 두 포트로 연다(research R21-D1) — 아래 명령의 9524·9544 는 서로 바꿔 써도 된다.

```bash
cd /Users/pioneer4/project2610
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e "backend[dev]"          # fastapi, uvicorn, pydantic, ultralytics, torch, opencv-python-headless, shapely, sqlalchemy, httpx, pytest

# 1.1 모델 가져오기 — 가중치와 커밋을 기록한다 (BR-CV-31). 라이선스 파일이 없으므로 record 에 'none' 으로 남는다
python -m cv_api.tools.fetch_model --repo https://github.com/MaxTheTechy/yolo --weights yolov8n.pt
# → models/yolov8n.pt, models/model_package.json (commit, weights, license=none, contract_check=adapter)

# 1.2 설정
cp backend/.env.example backend/.env
#   DATABASE_URL=sqlite:///./cv.db
#   MODEL_WEIGHTS=models/yolov8n.pt
#   API_KEYS=web:changeme-web            # caller_id:key — 아래 2·3절 예시가 이 키를 쓴다
#   ADMIN_KEYS=op1:changeme-admin
#   ALLOW_INSECURE_KEYS=1                # 위 changeme 키는 공개된 연습용이라 이 줄이 없으면 cv_api.serve 가 시작을 거부한다 (BE-1).
#                                        #   로컬 개발에서만. 공유·공개 서버는 이 줄을 빼고 새 키를 sha256: 형식으로 (backend/.env.example)
#   EXTERNAL_PROVIDER=fixture            # bis|fixture
#   BIS_API_KEY=
#   IMAGE_MAX_BYTES=10485760  IMAGE_MAX_SIDE=4096  BATCH_MAX_FRAMES=20
#   BLUR_LAPLACIAN_MIN=100  LOW_LIGHT_MEAN_MAX=40  CONFIDENCE_MIN=0.6  INFER_TIMEOUT_S=5
#   COUNT_CONF_MIN=0.4                   # 인원 세기 기준 기본값 (R22) — 운영 중 조정은 S3

# 1.3 기동 — lifespan 에서 DDL 적용(멱등) → 가중치 적재 → 더미 프레임 웜업 → 4필드 계약 확인. 두 포트를 한 번에
python -m cv_api.serve   # 한 프로세스가 같은 앱을 9544(외부 공개 API)·9524(웹 프록시 대상)로 연다 — 모델 적재 1회 (D1)
```

```bash
# 1.4 준비 상태 (G0)
curl -s localhost:9544/v1/readiness
# {"readiness":"ready","updated_at":"...","model_commit":"a1b2c3d"}
```

## 2. 기준 정보·정책 준비 — P2·P3 (시연 P1~P5)

`scripts/demo_prepare.py` 가 아래를 순서대로 호출한다. 수동으로 하려면:

```bash
A="-H X-Admin-Key:changeme-admin -H Content-Type:application/json"

# 기준 정보 적재 (TAGO CSV → route/stop). fixture 는 노선 102, 정류장 3001 을 포함
python -m cv_api.tools.load_reference --routes data/routes.csv --stops data/stops.csv

# 카메라 등록 (research R9)
curl -s $A -X POST localhost:9524/v1/admin/cameras -d '{"camera_id":"CAM-DEMO-01","place_type":"bus_in","route_id":"R102","vehicle_type_id":"VT_LOW"}'

# ROI (UC6)
curl -s $A -X POST localhost:9524/v1/admin/cameras/CAM-DEMO-01/roi -d '{"polygon":[[120,340],[480,335],[470,600],[110,610]],"roi_area_m2":6.5,"effective_from":"2026-09-29T00:00:00Z"}'   # roi_area_m2 = 실제 바닥 면적 (R20)

# 정원 (UC7)
curl -s $A -X POST localhost:9524/v1/admin/vehicle-types/VT_LOW/spec -d '{"capacity":80,"seat_count":30,"source":"제조사 제원표","effective_from":"2026-09-29T00:00:00Z"}'

# 매핑 (UC12, G9 — fixture 차량 목록에 1234 가 있어야 검증 통과)
curl -s $A -X POST localhost:9524/v1/admin/mappings -d '{"camera_id":"CAM-DEMO-01","vehicle_id":"1234","vehicle_type_id":"VT_LOW"}'

# 시연 모드 켜기 (UC11 A2, G14) — 종료 예정 시각 생략 시 +2시간
curl -s $A -X POST localhost:9524/v1/admin/policies/validity -d '{"factor":1.0,"cap_minutes":30,"demo_on":true}'
```

## 3. 진단·실측·조회 — P5·P6·P7 (시연 P6, 장면 1~6)

```bash
K="-H X-API-Key:changeme-web"

# 현재 프레임 진단 (UC1)
curl -s $K -F camera_id=CAM-DEMO-01 -F frame=@samples/bus_full.jpg localhost:9544/v1/diagnose
# {"vacant_capacity_ratio":15.2,"crowding_level":"crowded","person_count":18,"remaining_persons":12,"warnings":[],"notice":"...","versions":{...}}

# 흐린 프레임 → 판독 불확실 (UC3, G6)
curl -s $K -F camera_id=CAM-DEMO-01 -F frame=@samples/bus_blur.jpg localhost:9544/v1/diagnose
# {"crowding_level":"uncertain","is_reference_only":true,"warnings":[{"code":"blur"},{"code":"low_confidence"}], ...}

# 규격 외 → 422 진단 없이 반려 (UC5, G2)
curl -s $K -F camera_id=CAM-DEMO-01 -F frame=@samples/huge.bmp -F note=x localhost:9544/v1/diagnose

# 시연용 사전 촬영 프레임 일괄 등록 (UC10 A4)
curl -s $A -F 'items=...' localhost:9544/v1/measurements/batch   # scripts/demo_prepare.py 가 multipart 를 조립한다

# 후속 차량 여유도 (UC2)
curl -s $K "localhost:9544/v1/next-vehicle?route_id=R102&stop_id=3001&limit=4"
# {"vehicles":[{"vehicle_id":"1234","basis_type":"measured","vacant_ratio":17,"crowding_level":"crowded","coverage_num":2,"coverage_den":3},
#              {"vehicle_id":"3456","basis_type":"no_measurement"}], "demo_mode":true, "applied_validity_minutes":12, ...}
```

## 4. 웹서비스 (본 웹서비스, S0~S9) — P1 1.5~1.6

```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_BASE 는 비워 둔다 → vite 프록시가 /v1 을 9524 로 보낸다. VITE_API_KEY=changeme-web
npm run dev               # http://<서버IP>:9504
```

- S0 홈에서 준비 칩이 "진단 가능"인지 확인 → S5 에서 시험 프레임 제출(1.6 연동 확인) → S7 정류장 3001 조회.
- 'API활용'(S9)은 `GET /v1/api-guide` 와 `/docs` 를 렌더한다.

## 5. 테스트·벤치 — NFR-07·SC-03~06

```bash
pytest backend/tests -q                 # 규격 반려(SC-05), 블러 경고(SC-06), 일괄 정합성(NFR-06), 게이트 상태코드, 계약-안내 대조(G17)
python backend/bench.py --n 100         # POST /v1/diagnose p95 (NFR-01 2초), 기동 직후 첫 요청 비율 (SC-04 1.5배)
```

## 6. 시연 리허설 한 번에

```bash
python scripts/demo_prepare.py            # P1~P6 → 장면 1. 기본 = 실제 BIS 102번(30300037)·충남대학교 중앙시장 방면(30300037:42620)
python scripts/demo_prepare.py --reset    # DB 를 비우고 처음부터 할 때의 안내만 출력
python scripts/demo_prepare.py --route R102 --stop 3001   # 옛 고정 시연 (EXTERNAL_PROVIDER=fixture 일 때)
```

카메라 매핑은 그 시각에 **도착 예정인 차량 순**으로 다시 연결한다(S8 8.1 «102번 운행 차량으로 다시 연결» 과 같다). 프레임은 샘플 영상에서 뽑는다(T054 대체 — 대합실 45% 지점 16명, 차내 55% 지점, 대합실 + 블러). 실패한 게이트가 있으면 G 번호와 사유를 출력하고 멈춘다.

### 6-1. 시연 당일 — 실제 BIS 체크리스트와 예비 절차 (2026-09-29 사용자 결정 ③)

**전날·당일 아침**
1. 공공데이터포털 마이페이지 → 활용신청 3건(노선정보·버스위치정보·정류소)의 **일일 트래픽 한도** 확인. 실측 추정: 리허설 1회 ≈ 5회, S7 화면을 켜 두면 ≈ 시간당 120회(30초 조회 · 위치 캐시 15초) → 10시간 ≈ 1,200회. 한도가 1,000 이면 S7 을 켜 둔 채 두지 않거나 `.env` 에 `BIS_POS_CACHE_S=30`.
2. 오늘 사용량: `curl -s -H "X-Admin-Key: $ADMIN" localhost:9524/v1/admin/ops-status | jq .bis_calls_today` (이 프로세스가 오늘 보낸 실제 호출 수, 재기동하면 0부터).

**시연 30분 전**
3. `python scripts/demo_prepare.py` → `PASS` 와 `운행 정보 ok` 확인. 도착 예정 차량이 3대보다 적으면(첫차 전·막차 후·배차 간격 큼) G12 로 멈춘다 → 4번.
4. 직전(5분 전)에 S8 8.1 «102번 운행 차량으로 다시 연결» 을 한 번 더 누른다 — 곧 도착할 차량으로 표가 맞춰진다.

**BIS 장애·차량 없음 → 1분 복구 (fixture 예비)**
```bash
sed -i '' 's/^EXTERNAL_PROVIDER=bis/EXTERNAL_PROVIDER=fixture/' backend/.env
kill $(lsof -nP -iTCP:9544 -sTCP:LISTEN -t); cd backend && nohup python -m cv_api.serve --host 0.0.0.0 > .logs/serve.log 2>&1 &
python scripts/demo_prepare.py            # 같은 노선·정류장(30300037)의 예비 데이터로 다시 연결·등록
```
fixture 에는 102번(30300037)과 충남대학교 두 방면이 들어 있다(`backend/data/fixtures/transit.json`, 차량 번호는 2026-09-29 실제 운행 차량). 화면의 노선·정류장 주소는 그대로다. 시연이 끝나면 `EXTERNAL_PROVIDER=bis` 로 되돌리고 재기동한다.

**알려진 한계**: 샘플 영상은 밀집 장면을 적게 센다(대합실 실제 100명 이상 → 16명). 정원 80명 차량에서는 "혼잡"이 나오지 않는다 — 혼잡 등급은 S5 현재 프레임 진단에서 정원을 조정해 보여 준다(사용자 결정, 별도 작업 없음).

## 7. 종료·정리

```bash
curl -s $A -X POST localhost:9524/v1/admin/policies/validity -d '{"factor":1.0,"cap_minutes":30,"demo_on":false}'   # 시연 모드 끄기 (8.5)
deactivate
```

## 흔한 문제

| 증상 | 원인 | 대응 |
|---|---|---|
| 웹 화면 전체 오류(502·연결 거부) | 백엔드 미기동 | `cd backend && python -m cv_api.serve` (로그 `backend/.logs/serve.log`) |
| 외부 연계만 오류 | 9544 차단(방화벽) | 같은 앱이 9524 에도 있으니 9524 로 확인 후 네트워크 점검 |
| `/v1/readiness` 가 `preparing` 에서 멈춤 | 가중치 경로 오류 또는 웜업 실패(G5·G15) | 서버 로그의 `model_package` 계약 확인 결과를 본다. `fetch_model` 재실행 |
| `/v1/diagnose` 409 `ROI_MISSING` | ROI 미등록(G4) | §2 ROI 등록 |
| 매핑 저장 422 `VEHICLE_NOT_IN_FLEET` | fixture/BIS 차량 목록에 없는 번호(G9) | `GET /v1/admin/fleet?route_id=R102` 로 목록 확인 |
| next-vehicle 이 전부 `no_measurement` | 시연 모드 꺼짐(G14) 또는 실측 만료(G13) | `GET /v1/admin/policies/validity` 로 demo_on 확인 |
| next-vehicle `source_status: unavailable` | BIS 키 없음·장애(G12) | `EXTERNAL_PROVIDER=fixture` |
