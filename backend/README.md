# cv-api — 진단 API 서버

대전 대중교통 비식별 군중 밀집도·잔여 공간 진단 서비스의 백엔드. 계획·계약·절차는 `specs/001-crowd-vacancy-api/` 를 따른다.

## 빠른 시작 (Docker 미사용)

```bash
cd /Users/pioneer4/project2610
/opt/homebrew/bin/python3.11 -m venv .venv && source .venv/bin/activate
pip install -e "backend[dev]"            # 서비스 + 테스트 (stub 검출기로 동작)
pip install -e "backend[vision]"         # ultralytics + torch (YOLOv8n 프로세스 내 적재)
cp backend/.env.example backend/.env
python -m cv_api.tools.fetch_model       # yolov8n.pt 를 backend/models/ 에 (cd backend 에서)
cd backend
python -m cv_api.serve   # 한 프로세스가 같은 앱을 9544(외부 공개 API)·9524(웹 프록시 대상)로 연다 — 모델 적재 1회 (D1)
curl localhost:9544/v1/readiness
```

## 운영 인계 — 실행 설명서 (API 점검·개선 2026-09-30)

1. **무엇을 하는 서비스인가** — 관제 영상 프레임 1장 → 사람(머리) 검출 → 인원 ÷ 차량 정원 → 혼잡도·잔여 비율·등급(`free`·`normal`·`crowded`, 판단보류 `uncertain`)·경고. 모든 수치는 통계적 추정치. 웹 백엔드와 모델 API 가 한 프로세스(통합).
2. **어떻게 띄우나** — `cd backend && ../.venv/bin/python -m cv_api.serve --host 0.0.0.0` (9544·9524 같은 앱, 모델 적재는 기동 시 1회). 설정은 `backend/.env` 하나(권한 600, git 추적 제외) — 이름은 `.env.example`(값 없음, 빈 값은 코드 기본값). 모델 API 주소 `DIAGNOSIS_API_URL` = 지정 게이트웨이 `https://p4.sumzip.com/model-api`. 끌 때는 `kill -TERM <PID>`(정상 종료). 의존성 고정: `pip install -r backend/requirements.lock.txt`(pip freeze, 71개 `==`).
3. **어떻게 확인하나** — 상태 `curl -s localhost:9544/v1/readiness` → `"readiness":"ready"` (적재 중 `preparing`, 진단은 503). 외부 `https://p4.sumzip.com/model-api/v1/readiness`·`/API/v1/readiness` 200 JSON, Swagger `…/model-api/docs`. 예시 요청: `samples/bench_frame.jpg` + `camera_id=CAM-DEMO-01` → 200. 응답 헤더 `X-Request-ID` 로 로그 한 줄(`cv_api.access req_id=…`)을 찾는다 — 로그에 입력 원문·IP 없음.
4. **기준선 숫자** — `python backend/bench.py [--concurrent]` (키는 환경변수 `CV_API_KEY`/`CV_ADMIN_KEY` 또는 키 파일 — 명령행 인자로 받지 않음). 2026-09-30 11:07 (부하 평균 약 5): 안 127.0.0.1:9544 p50 71.2 ms · **p95 76.5 ms**, 밖 /API p50 82.9 · **p95 90.2 ms**, 동시 10 실패 0. 부하가 높을 때(11:40, 부하 약 12) p95 344 ms 까지 흔들린다 — 잴 때 `uptime` 을 함께 적는다. 약속(NFR-01)은 p95 ≤ 2000 ms.

점검·개선 기록: 루트 `API점검결과_4팀_20260930.md`, `API개선결과_4팀_20260930.md`.

## 서버 구성 (배정 포트)

| 포트 | 용도 | 진입점 | 경로 |
|---|---|---|---|
| **9544** | 외부 연계용 공개 API | `python -m cv_api.serve` (한 프로세스) | `/v1/*` 전체 + `/docs` — 진단·실측·후속 차량·준비 상태·안내·관리(관리자 키)·웹 변환. **공개 주소 `https://p4.sumzip.com/API`**(Swagger `/API/docs`) — 웹 서버 프록시가 9544 로 넘긴다 (T098) |
| **9524** | 웹 프론트의 프록시 대상 | 〃 (같은 앱) | 9544 와 같다 |
| **9504** | 웹 프론트 | `frontend/` vite | `/v1`·`/docs`·`/openapi.json` 을 9524 로 프록시 (`vite.config.ts`) |

2026-09-29 결정 R21-D1: 두 포트는 계약이 같다. 한 프로세스라 검출기 적재·웜업·운영 루프·`server_instance` 기록이 한 번만 일어난다(lifespan 은 첫 포트). 포트는 `SERVE_PORTS`(.env) 또는 `--ports 9544,9524`. `uvicorn cv_api.app:app --port 9544` 한 포트만 띄워도 전체 앱이다. 오전의 두 서버 분리 구성(`cv_api.web:app` + `create_app("api")`)은 되돌릴 때를 위해 코드에 남아 있다.

## 규격 밖 사진·영상 (웹 화면 전용, `cv_api/media.py`)

`/v1/diagnose` 등 진단 경로는 규격 밖을 그대로 반려한다(BR-CV-11). 웹 화면은 `/v1/web/*` 로 올리고, 이 경로가 규격에 맞춰 `DIAGNOSIS_API_URL`(같은 프로세스의 9544)로 넘긴다. 호출 키는 그대로 전달된다.

| 입력 | 처리 |
|---|---|
| 규격 안 JPEG·PNG | 그대로 전달 (`normalization.applied=false`) |
| 큰 사진·10MB 초과 | 긴 변 1920px 로 축소, JPEG |
| WebP·HEIC·BMP·TIFF·GIF | JPEG 로 변환. 휴대폰 세로 사진은 EXIF 회전 반영 |
| 짧은 변 240px 미만 | **반려 (422 `RESOLUTION_TOO_SMALL`)** — 확대하지 않는다 |
| 영상 (`/v1/web/diagnose-video`) | `interval_s` 간격(기본 2초, 최대 60장 — 넘으면 간격 확대)으로 프레임을 뽑아 각각 진단 + 직전 5장 중앙값(평활). `at_s` 를 주면 그 한 장 |

영상은 OpenCV(FFmpeg)가 파일 경로만 읽어 요청 동안만 임시 파일에 두고 끝나면 지운다(FR-11). 한도는 `settings.py` 의 `NORMALIZE_*`·`MEDIA_MAX_BYTES`·`VIDEO_*`.

## 검출기 두 가지

| DETECTOR | 적재 위치 | 특징 |
|---|---|---|
| `yolov8` (기본) | uvicorn 프로세스 안 | 첫 적재 수 초, 단건 추론 0.1~0.4초(CPU). NFR-01 p95 2초 충족 |
| `ollama_vl` | 공유 Ollama 서버 `gemma4:e4b` (qwen3-vl 은 사고 모드 미해제로 응답이 비어 실측 배제) | 프로세스 메모리 안 씀. 첫 요청 10~30초(모델 로딩), 이후 수 초. 동시 1건. 정확도·지연은 파일럿 비교용 |

두 검출기 모두 `predict.Detector` 인터페이스(사진 → 사람 박스 목록)를 구현하고, 혼잡도 계산(인원 세기 기준 이상 · ROI 안 인원 ÷ 차량 전체 정원, R22)은 공통이다. Ollama 규칙(`num_ctx` 8192, `keep_alive` 5m, 동시 1건, 공용 모델 언로드 금지)은 `ollama_client.py` 가 강제한다.

## 모델 로딩 시간과 화면

- 기동 직후 준비 상태는 `preparing` 이며 적재·웜업이 끝나야 `ready` 가 된다(G0). 그 전 진단 요청은 503.
- `GET /v1/readiness` 가 검출기 종류·적재 소요 시간·마지막 웜업 시각을 함께 준다. 웹 S1 화면이 이를 표시한다.
- `POST /v1/admin/detector/preload` 로 Ollama 모델을 미리 올리고, `GET /v1/admin/detector` 로 적재 상태를 본다.

## 규칙

- 스키마 정본은 `design/cv_ddl.sql`. 기동 시 멱등 적용.
- 원본 프레임·개인 정보는 저장하지 않는다(FR-11).
- 게이트(G0~G17) → HTTP 상태 대응은 `research.md` R7, 구현은 `gates.py`.

## 모델 교체

1. 같은 YOLO 계열: `.env` 의 `MODEL_WEIGHTS` 만 바꾼다.
2. 다른 계열: `predict.py` 에 `Detector` 구현을 추가하고 `DETECTOR=` 값을 만든다.
3. 기동 시 `model_package` 행이 새로 기록되고 이전 정확도 검증은 무효 처리된다. S4 로 재검증하고 인원 세기 기준(S3)·판독 기준을 재보정한다.

## 인증 (T095)

- **이용자**(본 웹서비스 이용자·연계 시스템): `X-API-Key`(호출 키). 진단·실측·후속 차량과 조회 경로 `/v1/reference/*`(카메라·정원·ROI·등급 기준·운영 상태).
- **운영 관리자**: `X-Admin-Key`. `/v1/admin/*` 변경 전부. 웹 화면은 오른쪽 위 «관리자 로그인»으로 입력한다 — 관리자 키는 `frontend/.env` 에 넣지 않는다.
- 키는 `backend/.env` 의 `API_KEYS`·`ADMIN_KEYS` 에 `이름:sha256:<hex>` 로 둔다. 새 키: `python -c "import secrets,hashlib;k=secrets.token_urlsafe(24);print(k, 'sha256:'+hashlib.sha256(k.encode()).hexdigest())"` → `.env` 에 해시, 원문은 전달·보관. 호출 키를 바꾸면 `frontend/.env` 의 `VITE_API_KEY` 도 같이.
- 스크립트는 `--admin`/`--key` 또는 환경변수 `CV_ADMIN_KEY`/`CV_API_KEY`.
