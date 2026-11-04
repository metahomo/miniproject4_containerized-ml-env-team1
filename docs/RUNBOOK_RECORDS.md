# 숨통 Runbook 보안·검증 기록

운영 절차는 [RUNBOOK.md](RUNBOOK.md)를 봅니다. 이 문서는 버전별 확인 결과만 기록합니다.

## v1.5 빌드·검증·배포 기록

2026-11-04에 Git 태그 `v1.5`(`b856408`)로 이미지를 만들어 운영 서버(WSL Ubuntu 24.04 + Docker Desktop, 메모리 4GB)에 배포했습니다. v1.4에 #67 운영 로그와 #70 PostgreSQL 코드 제거를 더한 판입니다.

| 항목 | 결과 |
|---|---|
| 소스 | Git 태그 `v1.5`, `b856408` |
| 빌드 | `docker build --pull --no-cache`, 백엔드와 프론트엔드 합쳐 407초 |
| 백엔드 이미지 | `hyungnss/sumtong:backend-v1.5`, digest `sha256:7d0bc0686d49a56d7aa28032766c22371be73055f103058a83e03089f2002bf1`, 디스크 2.8GB / 내려받기 약 654MB |
| 프론트엔드 이미지 | `hyungnss/sumtong:frontend-v1.5`, digest `sha256:4f6fe21f4bf05c4098094afbc5ade4379dc8fd570b6ab67fdd1ab32b18bc7243`, 디스크 92.2MB / 내려받기 약 26.5MB |
| `latest` | `backend-latest`, `frontend-latest`를 위 digest로 옮김 |
| SQLite | 이미지의 `libsqlite3-0` `3.46.1-7+deb13u2` |
| 이미지 내용 | 모델 가중치, `.env`, `docker.env`, DB 없음. PostgreSQL 패키지와 DDL 없음 (`.pt`는 torch 패키지의 2.8KB 테스트 파일 1개뿐) |
| 백엔드 테스트 | `pytest` 199 passed |
| 운영 로그 컨테이너 시험 | 24개 통과. 파일 분류, 비밀값 없음, 컨테이너 재생성 후 유지, 모델 없을 때 503 기록 |
| SQLite 컨테이너 시험 | 24개 중 23개 통과. 빈 볼륨 새 시작 10회 정상 |
| 4개 서비스 기동 | 운영 서버를 내리고 디스크 캐시를 비운 상태로 3회, 22개 항목 모두 통과. 시작 21.7~30.0초 |

### 운영 서버 배포

| 항목 | 결과 |
|---|---|
| 이전 버전 | v1.1 |
| 추가한 것 | `models/yolo11n.pt`, `yolo11n.json`, `docker-compose.monitoring.yml`, `monitoring/` |
| 바꾼 설정 | `docker.env`의 `DETECTOR=dual`, `MODEL_DISTANCE_WEIGHTS`, `DISTANCE_THRESHOLD`. `.env`의 `CV_IMAGE`, `CV_TAG`, `COMPOSE_FILE`, `GRAFANA_ADMIN_PASSWORD` |
| 백업 | 배포 전 DB 백업 `ok`, 계정 1개, 노선 143개 |
| 배포 후 | 4개 서비스 `(healthy)`, `ready`, `dual`, 시작 7.6초. DB `ok`, 계정 1개, 노선 143개로 유지 |
| 웹 확인 | 로그인 정상, 진단 10건 모두 200, 응답 0.36~1.2초, `error.log` 0줄 |
| 모니터링 | Prometheus 수집 대상 `up`, 진단 지표 수집 |
| 로그 확인 명령 | `ls`, `tail`, `docker compose cp` 실행 확인 |
| 메모리 (진단 후) | 백엔드 531.4MiB, 프론트엔드 9.1MiB, Grafana 112.3MiB, Prometheus 29.1MiB |

### 롤백 시험

| 항목 | 결과 |
|---|---|
| v1.1 데이터 → v1.5 → v1.4 → v1.5 (3회 반복) | 시험용 볼륨에서 105개 항목 모두 통과. 시작, 로그인, 진단, 쓰기, 공개 `/metrics` 차단, 수집 대상 `up`, DB `ok` |
| v1.4 이미지 | digest가 v1.4 기록과 일치 |
| v1.4 동안의 로그 | 2·3회차에 `app.log`, `security.log` 줄 수 변화 없음. 기존 파일은 유지되고 v1.5로 돌아오면 다시 쌓임 |
| v1.1 ↔ v1.5 (5회 반복) | v1.1 진단 15회 모두 200 |

### 시험 중 발견한 내용

| 현상 | 내용 | 현재 판단 |
|---|---|---|
| 재시작 직후 `ready` 표시 | 시작 1.9초에 `ready`로 보였으나 진단은 `503 NOT_READY`. 준비 상태를 DB의 마지막 기록에서 읽는 코드 구조로 v1.1에도 있음 | 몇 초 뒤 풀림. RUNBOOK 2장에 반영. SQLite 컨테이너 시험의 실패 1개도 이 현상으로 판단하나, 당시 응답은 남아 있지 않음 |
| 모델 점검 시간 초과 | 빌드와 다른 시험 직후, 운영 v1.1과 함께 4개 서비스를 처음 띄울 때 1회 `추론 시간 초과 (> 30.0s)`로 `unavailable`. 이후 6회는 재현되지 않음 | 원인 미확정. 부하로 추정. 자동 재시도 없음. RUNBOOK 5장에 반영 |

### 실행하지 않은 항목

운영 서버 재부팅 후 동작, 모델 점검 시간 초과 상태에서의 복구(재현되지 않음), Windows PowerShell 절차, 운영 서버에서의 실제 롤백.

## v1.4 빌드·검증 기록

2026-11-04에 WSL(Ubuntu 24.04) + Docker Desktop에서 `develop` `69e1ad7`(#61 모니터링, #64·#65 이중 모델 포함)로 v1.4 이미지를 만들고 확인했습니다(RUNBOOK 10장 절차). 이미지는 빌드한 사람의 Docker Hub 공개 저장소 `ryujh33/sumtong`에 올립니다(v1.1 이하는 `hyungnss/sumtong`).

| 항목 | 결과 |
|---|---|
| 소스 | `develop` `69e1ad7` |
| 백엔드 이미지 | `ryujh33/sumtong:backend-v1.4`, 이미지 ID `sha256:16a8d31b6c249157d131e1ed6e0dae69481a9cbf87a288216b016e6af6d7a091`, 디스크 2.83GB / 내려받기 약 660MB |
| 프론트엔드 이미지 | `ryujh33/sumtong:frontend-v1.4`, 이미지 ID `sha256:a54de3283d0ac34276168ba6a843a54ceda1c6fec0bc5d1fdb5529534294ee81`, 디스크 92.2MB / 내려받기 약 26.5MB |
| Docker Hub digest | 백엔드 `sha256:2eda79d30bd10feae441fce6894996ef2f70047020fcee2a266f695952770824`, 프론트엔드 `sha256:3c5a27f7f85eed5cb93bebb19e0a49e1158e005afe25eb174fe05f3dc5312731` |
| 빌드 시간 | 8.9초 (이전 빌드 캐시 사용) |
| 백엔드 회귀 테스트 | `pytest` 180 passed, 2 skipped (Python 3.11) |
| 기동 | 4개 서비스(backend, frontend, prometheus, grafana) `(healthy)` |
| 이중 모델 | `readiness` `ready`, `detector.kind` `dual`, 로그 `detector ready: dual head_crowdhuman_n1280.pt+yolo11n.pt (6.2s)`, 적재 2.91초 |
| 모델 해시 | `head_crowdhuman_n1280.pt` `d740367868d50137…`, `yolo11n.pt` `0ebbc80d4a7680d1…` |
| 지표 | 내부 9524 `/metrics`에서 `cv_detector_loaded 1.0`, 공개 9544 `/metrics`는 404 |
| 대시보드 | 진단 후 진단 결과·최근 추론 시간(336ms)·경로별 요청 수 반영, 응답 시간 p95 약 550ms 이하 |
| 메모리 (대기) | 백엔드 451.6MiB, 프론트엔드 8.2MiB, Grafana 142.9MiB, Prometheus 48.6MiB |
| 모니터링 볼륨 | `sumtong_prom-data` 4.5MB(약 19시간 수집), `sumtong_grafana-data` 52.4MB |

### PC 재부팅 후 재기동 (v1.3 이하에서도 해당)

| 항목 | 결과 |
|---|---|
| 재부팅 직후 (2026-11-04) | 컨테이너는 자동으로 다시 떴지만 백엔드 `unavailable`(컨테이너 안 `/app/backend/models` 비어 있음, 호스트 `models/`에는 파일 있음), Prometheus는 `prometheus.yml` 마운트 오류로 시작 실패. 5분 기다려도 풀리지 않음 |
| 조치 | `docker compose up -d --force-recreate` 후 백엔드 `ready`, 4개 서비스 `(healthy)`. RUNBOOK 2장 "PC를 다시 켠 뒤"에 반영 |

### 실행하지 않은 항목

운영 서버 배포, Windows PowerShell에서의 `COMPOSE_FILE`(`;` 구분자)·`Add-Content` 절차, `grafana cli admin reset-admin-password`, 포트 변경(`PROM_PORT`, `GRAFANA_PORT`), 캐시 없는 첫 빌드 시간 측정.

## v1.3 검증 기록

2026-11-03에 Windows 11 및 Docker Compose 환경에서 YOLOv8 Head + YOLO11 이중 융합 모델 추론 엔진과 REST API를 실측 검증했습니다.

| 항목 | 실측 결과 |
|---|---|
| API 단일 진단 응답 시간 | **263ms** (단일 이미지 전송 및 융합 진단 완료) |
| 두부 탐지 인원 [Model A] | **CLI 9명 / API 8명** (`head_crowdhuman_n1280.pt`, 24.5MB 정식 모델) *API는 ROI 다각형 및 신뢰도 기준 필터링 적용 |
| 신체 탐지 인원 [Model B] | **7명** (`yolo11n.pt`, 5.6MB 전신 검출) |
| 거리 행렬 및 밀집도 분석 | **21개 거리 쌍(Pairs) 산출**, 승객 간 유클리드 거리 및 근접 쌍 계산 완료 |
| 백엔드 회귀 테스트 | `pytest backend/tests/` 176개 전체 통과 (176 passed, 2 skipped) |
| 모델 해시 정합성 | 두부 모델 `weights-sha256:d740367868d50137`, 신체 모델 `weights-sha256:0ebbc80d4a7680d1` |
| 도커 환경 구성 | 웹(`hyungnss/sumtong:frontend-v1.3`) + 백엔드(`hyungnss/sumtong:backend-v1.3`) 2개 컨테이너 기반 구동 |

## v1.1 보안 기록

### SQLite 미해결 취약점

v1.1 백엔드 이미지는 v1.0과 같은 `libsqlite3-0 3.46.1-7+deb13u2`를 사용합니다. Debian 13(trixie)의 최신 패키지이며, 2026-11-03 [Debian 보안 트래커](https://security-tracker.debian.org/tracker/source-package/sqlite3) 기준 미해결 15건이 남아 있습니다.

| 트래커 분류 | 건수 | CVE |
|---|---|---|
| 취약, 긴급 공지 없음 (no DSA) | 12 | CVE-2026-119591, CVE-2026-119371 ~ CVE-2026-119379, CVE-2026-50812, CVE-2026-50813 |
| 판단 보류 | 1 | CVE-2026-119586 |
| 취약, 중요도 낮음 | 2 | CVE-2025-70873, CVE-2021-45346 |

- 결정: 현재 패키지를 유지합니다. Debian 패치가 나오면 `--pull --no-cache`로 이미지를 다시 빌드합니다.
- 확인 명령: `docker run --rm --entrypoint dpkg hyungnss/sumtong:backend-v1.1 -s libsqlite3-0`

### 로그인 시도 제한

15분 안에 5번 실패하면 15분 동안 잠급니다. 없는 아이디도 같은 방식으로 처리합니다. `security.log`에는 비밀번호, 키, 없는 아이디의 값을 남기지 않습니다.

## v1.1 검증 기록

2026-11-03에 `a576aca`로 만든 이미지를 Windows 11의 격리된 Compose 프로젝트에서 실행했습니다. 포트는 19504, 19544로 바꿨고, 테스트 후 환경을 삭제했습니다.

| 항목 | 결과 |
|---|---|
| SQLite 테스트 | Windows, 리눅스 이미지 모두 176개 통과, 2개 건너뜀 |
| PostgreSQL 15 테스트 | DDL 2개 통과. 앱 168개 통과, 7개 건너뜀, 1개 실패 |
| 프론트엔드 테스트 | 타입 검사 통과, `vitest` 55개 통과 |
| 빈 볼륨 반복 시작 | 35번 모두 `ready` (6~13초), `startup failed` 0건. 9번은 시작 직후 `no such table` 로그 2줄 |
| 상태 표시 | 빈 볼륨에서 12초 만에 `healthy` |
| 모델 폴더 비움 | 180초에 `unhealthy`, 재시작 없음, `readiness`는 `unavailable` |
| 키 비움 | 백엔드 재시작 반복, 로그에 `시작 거부`. 키를 되돌린 뒤 7초 만에 `ready` |
| v1.0 → v1.1 업그레이드 | 계정과 핵심 데이터 유지, `login_attempt` 표 추가, `demo_prepare.py`가 `PASS` 출력 |
| 로그인 잠금 | 5번째 실패에 HTTP 429, 맞는 비밀번호도 차단, 없는 아이디도 같은 동작 |
| 잠금 해제 | API, 운영 관리자 화면, 관리자 키 화면 모두 성공. `security.log`에 해제한 주체 기록 |
| 컨테이너 재생성 | 잠금 상태, `security.log`, 계정 유지 |
| v1.0 롤백 (복구 없음) | 시작, 로그인, 쓰기, `demo_prepare.py` 정상. 다시 v1.1로 올려도 정상 |
| v1.0 롤백 (백업 복구) | 복구 성공, 백업 이후 계정은 사라짐 |
| 멈추지 않는 백업 | 백업 중 `ready` 유지. 복구 후 백업 전 계정만 남고 무결성 검사 `ok` |

운영 서버 배포는 2026-11-03에 완료했습니다. 두 서비스 `healthy`, 재시작 0회, 모델 `weights-sha256:d740367868d50137`을 확인했고, 업그레이드 전 백업과 비교해 줄어든 표는 없었습니다.

### 알려진 사항

- PostgreSQL 앱 테스트의 실패는 `test_web_readiness_reads_db_when_no_detector_in_process`의 데드락입니다. 이전 `develop`에서도 간헐적으로 실패했습니다. 운영 DB는 SQLite라 서비스와 무관합니다.
- `test_media.py`의 6개 테스트는 `DIAGNOSIS_API_URL`이 있어야 통과합니다. 로컬 `backend/.env`가 없는 환경에서는 값을 지정합니다.
- v1.0 이미지는 빈 볼륨 첫 시작에서 준비가 끝나지 않는 경우가 다시 나타났습니다. 볼륨을 새로 만들어 다시 시작하니 9초 만에 `ready`가 됐습니다.
- 운영 서버의 업그레이드 전 백업(이전 절차)에는 백업 시점 이전의 서버 시작 기록 1건이 빠져 있었습니다. 원인은 찾지 못했고 테스트 환경에서는 재현되지 않아, 백업 절차를 SQLite 백업 기능으로 바꿨습니다. 새 절차는 장시간 운영한 서버에서 아직 시험하지 않았습니다.

실행하지 않은 항목은 PC 재부팅 후 재기동, 짝팀 교차실행입니다.

## v1.0 보안 기록

### CVE-2025-6965

v1.0 백엔드 이미지는 패치가 포함된 `libsqlite3-0 3.46.1-7+deb13u2`를 사용합니다. 버전 숫자만 보고 3.50.2 미만으로 탐지되면 오탐으로 처리합니다.

- 근거: [Debian 보안 트래커](https://security-tracker.debian.org/tracker/CVE-2025-6965)는 trixie의 이 버전을 `fixed`로 표시합니다.
- 확인 명령: `docker run --rm --entrypoint dpkg hyungnss/sumtong:backend-v1.0 -s libsqlite3-0`

### 운영 시 지킬 사항

- `docker.env`와 키 원문은 저장소나 메신저에 올리지 않습니다.
- 관리자 키는 최초 설정에만 쓰고, 평소에는 개인 계정으로 로그인합니다.
- 모델 파일은 라이선스(AGPL-3.0, CrowdHuman CC BY-NC 4.0) 확인 중이므로 재배포하지 않습니다.
- 다른 PC에서 접속해야 할 때만 방화벽에서 9504, 9544 포트를 엽니다.

## v1.0 검증 기록

2026-11-02에 Windows 11의 격리된 Compose 프로젝트에서 `CV_TAG=v1.0`으로 실행했습니다. 포트는 19504, 19544로 바꿨고, 테스트 후 환경을 삭제했습니다.

| 항목 | 결과 |
|---|---|
| 기동 | 두 서비스 `healthy`, 모델 적재 후 `ready` |
| 준비 상태 | `healthy`인 동안 `preparing`이 나오는 것을 확인 |
| 웹, API 문서 | 모두 HTTP 200 |
| 기준 정보 입력 | `{'routes': 141, 'stops': 10533}` |
| 백업, 복구 | 백업 후 추가한 표가 복구로 제거되고, 앱 사용자 쓰기 성공 |
| `docker compose down` | 볼륨 유지 |
| 기동 시간 | 이미지를 받아 둔 상태에서 `ready`까지 10초, 두 서비스 `healthy`까지 11초 |
| 이미지 확인 | `docker compose images`에 `backend-v1.0`, `frontend-v1.0` 표시 |
| 시연 데이터 | `demo_prepare.py`가 `PASS` 출력, 시연 모드 켜짐 |
| 메모리 | 기동 직후 대기 상태에서 백엔드 494.1MiB, 프론트엔드 7.395MiB |
| 모델 폴더 비움 | `readiness`가 `unavailable`, 로그에 `detector load failed`, 컨테이너는 `healthy` |
| 키 비움 | 백엔드 `Restarting (1)`, 로그에 `시작 거부`. 키를 되돌린 뒤 9초 만에 `ready` |
| 메모리 200MB 제한 | 백엔드 재시작 6회 반복. 확인 시점에는 재시작 직후라 `OOMKilled=false`, 종료 코드 0으로 표시되어 OOM 표시는 확인하지 못함 |

실행하지 않은 항목은 실제 운영 서버, 웹 로그인과 관리자 전환, 이미지 롤백입니다. 짝팀 교차실행도 아직 수행하지 않았습니다.
