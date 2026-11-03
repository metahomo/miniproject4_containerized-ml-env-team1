# 숨통 Runbook 보안·검증 기록

운영 절차는 [RUNBOOK.md](RUNBOOK.md)를 봅니다. 이 문서는 버전별 확인 결과만 기록합니다.

## v1.3 검증 기록

2026-11-03에 Windows 11 및 Docker Compose 환경에서 YOLOv8 Head + YOLO11 이중 융합 모델 추론 엔진과 REST API를 실측 검증했습니다.

| 항목 | 실측 결과 |
|---|---|
| API 단일 진단 응답 시간 | **263ms** (단일 이미지 전송 및 융합 진단 완료) |
| 두부 탐지 인원 [Model A] | **11명** (`head_crowdhuman_n1280.pt`, 24.5MB 정식 모델) |
| 신체 탐지 인원 [Model B] | **7명** (`yolo11n.pt`, 5.6MB 전신 검출) |
| 거리 행렬 및 밀집도 분석 | **21개 거리 쌍(Pairs) 산출**, 승객 간 유클리드 거리 및 근접 쌍 계산 완료 |
| 백엔드 회귀 테스트 | `pytest backend/tests/` 176개 전체 통과 (176 passed, 2 skipped) |
| 모델 해시 정합성 | 두부 모델 `weights-sha256:d740367868d50137`, 신체 모델 `weights-sha256:0ebbc80d4a7680d1` |
| 도커 환경 구성 | 웹(`frontend:v1.3`) + 백엔드(`backend:v1.3-cv-yolo11`) 2개 컨테이너 기반 구동 |

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

- PostgreSQL 앱 테스트의 실패는 `test_web_readiness_reads_db_when_no_detector_in_process`의 데드락입니다. 이전 `develop`에서도 간헐적으로 실패했습니다. 운영 DB는 SQLite이며, PostgreSQL 전환 전에 해결이 필요합니다.
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
