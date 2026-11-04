# 숨통 운영 안내 (Runbook) — v1.3

| 항목 | 값 |
|---|---|
| 운영 버전 | `CV_TAG=v1.3` |
| 담당자 | (입력 필요) |
| 장애 연락처 | (입력 필요) |
| 기준일 | 2026-11-03 |

## 1. 구성

```text
web user ---- 9504 ----> frontend (nginx) ---- 9524, 9544 ----> backend
API client ---------------- 9544 -----------------------------> backend

backend ---> sumtong_cv-data volume (SQLite: /data/cv.db)
backend ---> ./models folder (이중 모델: head_crowdhuman_n1280.pt, yolo11n.pt, 사이드카 .json, read-only)
```

| 항목 | 값 |
|---|---|
| 백엔드 이미지 | `hyungnss/sumtong:backend-v1.3` |
| 프론트엔드 이미지 | `hyungnss/sumtong:frontend-v1.3` |
| 소스 | Git 브랜치/태그 `v1.3` |
| 모델 | 이중 융합 모델 (두부: `head_crowdhuman_n1280.pt`, 전신/거리: `yolo11n.pt` 및 `.json`). 호스트 `./models` 폴더에서 마운트 |
| 포트 | 웹 9504, API 9544 |
| 데이터 | `sumtong_cv-data` 볼륨, `/data/cv.db` |
| 보안 로그 | 같은 볼륨의 `/data/logs/security.log`. 계정 잠금과 잠금 해제 기록, 시간은 UTC |
| 설정 파일 | `docker.env`: 백엔드 설정과 키 해시. `.env`: `CV_TAG=v1.3`, 포트, `CV_MODELS_DIR=./models` |

## 2. 기동

사전 준비: Docker Desktop(메모리 4GB 이상 권장). 운영 폴더에 `docker-compose.yml`, `docker.env.example`, `models/`를 둡니다. `models/` 폴더 안에는 `head_crowdhuman_n1280.pt`와 `yolo11n.pt` 및 메타데이터 `.json` 파일이 포함되어야 합니다. 모든 명령은 이 폴더의 PowerShell에서 실행합니다. WSL에서 실행할 때는 `curl.exe` 대신 `curl`을 쓰고, `.env`는 `echo "CV_TAG=v1.3" > .env`로 만듭니다.

### 처음 실행할 때

1. 버전을 지정하고 설정 파일을 만듭니다.

    ```powershell
    Set-Content .env "CV_TAG=v1.3" -Encoding ascii
    Copy-Item docker.env.example docker.env
    ```

2. 아래 명령을 두 번 실행해 키를 2개 만듭니다. 첫 번째 결과가 **호출 키**, 두 번째 결과가 **관리자 키**입니다. 각 줄의 앞 값이 원문, 뒤 값(`sha256:...`)이 해시입니다.

    ```powershell
    docker run --rm python:3.11-slim python -c "import secrets,hashlib;k=secrets.token_urlsafe(24);print(k, 'sha256:'+hashlib.sha256(k.encode()).hexdigest())"
    ```

    | 값 | 쓰는 곳 |
    |---|---|
    | 호출 키 해시 | 2장 3번 `docker.env`의 `API_KEYS` |
    | 관리자 키 해시 | 2장 3번 `docker.env`의 `ADMIN_KEYS` |
    | 호출 키 원문 | 3장 샘플 동작 |
    | 관리자 키 원문 | 2장 최초 1회 작업의 관리자 로그인, 3장 샘플 동작 |

    해시는 `docker.env`에만 넣고, 원문은 로그인과 스크립트에 씁니다. 원문은 다시 볼 수 없으므로 안전한 곳에 보관합니다.

3. `docker.env`의 두 줄에 해시를 넣습니다. 해시는 `sha256:`까지 포함한 값 전체입니다.

    ```text
    API_KEYS=web:<호출 키 해시>
    ADMIN_KEYS=op1:<관리자 키 해시>
    ```

### 기동과 준비 확인

```powershell
docker compose up -d
curl.exe -s http://localhost:9544/v1/readiness
```

- 준비 완료 기준: `"readiness":"ready"`. `preparing`이면 잠시 후 다시 확인합니다.
- 컨테이너 상태: `readiness`가 `ready`일 때만 `(healthy)`로 표시됩니다. 모델이 없어 `unavailable`이면 약 3분 뒤 `(unhealthy)`로 바뀝니다.
- 통상 소요 시간: 이미지를 받아 둔 상태에서 6~13초(2026-11-03, 35회 실측). 처음에는 이미지(약 650MB)를 받느라 몇 분 더 걸립니다.

### 최초 1회 작업

1. 기준 정보를 넣습니다. 두 번째 명령이 `{'routes': 141, 'stops': 10533}`을 출력하면 정상입니다.

    ```powershell
    docker compose exec backend python -m cv_api.tools.load_reference
    docker compose exec backend python -m cv_api.tools.load_reference --routes data/bis_routes.csv --stops data/bis_stops.csv
    ```

2. 관리자 계정을 만듭니다.
    1. `http://localhost:9504`에서 회원가입합니다.
    2. 로그아웃한 뒤 로그인 화면의 **관리자 키**를 눌러 관리자 키 원문으로 로그인합니다.
    3. **계정 · 키 관리**에서 내 계정을 **운영 관리자**로 바꿉니다.
    4. 로그아웃한 뒤 내 계정으로 다시 로그인합니다.

## 3. 확인

기동, 복구, 버전 변경 후 모두 확인합니다.

| 확인 항목 | 명령 또는 위치 | 정상 결과 |
|---|---|---|
| 이미지 버전 | `docker compose images` | `hyungnss/sumtong:backend-v1.3`, `hyungnss/sumtong:frontend-v1.3` (또는 `backend-v1.3`, `frontend-v1.3`) |
| 준비 상태, 모델 | `curl.exe -s http://localhost:9544/v1/readiness` | `"readiness":"ready"`, `"model_commit":"weights-sha256:d740367868d50137"` |
| 로그 | `docker compose logs backend` | `detector ready: dual head_crowdhuman_n1280.pt+yolo11n.pt` |
| 이중 모델 CLI 추론 | `docker compose exec backend python -m cv_api.tools.infer_dual --source samples/bus_full.jpg` | 두부 9명, 전신 7명 검출 및 거리 쌍 요약 정상 출력 |
| 웹 화면 | `http://localhost:9504` | 화면 표시 |
| API 문서 | `http://localhost:9544/docs` | Swagger 표시 |

### 샘플 동작 (시연·교차실행 환경 전용)

샘플 데이터를 넣고 시연 모드를 켜므로 실제 운영 DB에서는 실행하지 않습니다. 기준 정보를 넣은 뒤 실행하며, 마지막 줄에 `PASS`가 나오면 정상입니다. `<...>`에는 2장에서 보관한 **원문**을 넣습니다. 해시를 넣으면 인증에 실패합니다.

```powershell
docker compose exec -e CV_ADMIN_KEY=<관리자 키 원문> -e CV_API_KEY=<호출 키 원문> backend python /app/scripts/demo_prepare.py
```

## 4. 점검

| 점검 항목 | 명령 | 정상 기준 |
|---|---|---|
| 컨테이너 상태 | `docker compose ps` | 두 서비스 `(healthy)`. `Restarting`이 없어야 합니다 |
| 실시간 로그 | `docker compose logs -f backend` | `ERROR`가 반복되지 않아야 합니다. `Ctrl+C`로 종료합니다 |
| CPU, 메모리 | `docker stats --no-stream` | 메모리가 한도에 가깝지 않아야 합니다. 기동 직후 대기 상태 실측: 백엔드 약 494MiB, 프론트엔드 약 7MiB |

## 5. 장애 대응

| 증상 | 확인 방법 | 원인 | 조치 | 복구 확인 |
|---|---|---|---|---|
| 백엔드 `(unhealthy)`, 진단 불가 | `readiness`가 `unavailable`, `model_commit`이 `weights-sha256:missing`. 로그에 `detector load failed` | `models/` 폴더가 비었거나 이중 모델 파일(`head_crowdhuman_n1280.pt`, `yolo11n.pt`)이 없음 | `models/`의 이중 `.pt`, `.json`을 확인한 뒤 `docker compose up -d --force-recreate backend` | 3장 확인 |
| 로그인할 때 `로그인 실패가 많아 잠겼다` (HTTP 429) | **계정 · 키 관리**에 `잠김` 표시. `docker compose exec backend cat /data/logs/security.log`에 `login_locked` | 15분 안에 로그인 5번 실패 | 15분 뒤 자동 해제. 급하면 운영 관리자가 **잠금 해제** 버튼을 누름. 운영 관리자가 잠겼으면 관리자 키로 로그인해 해제 | 해당 계정 로그인 성공 |
| 백엔드 `Restarting` 반복 | 로그에 `시작 거부` | `docker.env`의 `API_KEYS`, `ADMIN_KEYS`가 비었거나 기본값 | 2장대로 키를 넣고 `docker compose up -d` | 3장 확인 |
| 시작 직후 로그에 `no such table` | `curl.exe -s http://localhost:9544/v1/readiness` | 새 볼륨에서 DB 준비 전에 들어온 상태 조회 | `ready`가 되면 조치 없음. 1분이 지나도 `ready`가 아니면 로그의 `startup failed` 줄을 담당자에게 전달 | `"readiness":"ready"` |

`security.log`의 시간은 UTC입니다. 한국 시간은 9시간을 더합니다. 없는 아이디는 `(없는 아이디)`로 기록되며, 해제할 계정이 없으므로 15분 뒤 자동으로 풀립니다.

## 6. 백업과 복구

> **주의:** `docker compose down -v`는 데이터 볼륨까지 지웁니다. 운영 중에는 쓰지 않습니다.

### 백업

백엔드를 멈추지 않고 SQLite 백업 기능으로 복사합니다. 아직 `cv.db`에 합쳐지지 않은 최근 기록(`cv.db-wal`)도 함께 담깁니다.

```powershell
docker compose exec -T backend python -c "import sqlite3; s=sqlite3.connect('/data/cv.db'); d=sqlite3.connect('/data/cv-backup.db'); s.backup(d); d.close(); s.close(); print('backup ok')"
docker compose exec -T backend python -c "import sqlite3; c=sqlite3.connect('/data/cv-backup.db'); print(c.execute('pragma integrity_check').fetchone()[0], c.execute('select count(*) from account').fetchone()[0], c.execute('select count(*) from route').fetchone()[0])"
docker compose cp backend:/data/cv-backup.db ./cv-backup.db
docker compose exec -T backend rm /data/cv-backup.db
```

두 번째 명령은 `ok <계정 수> <노선 수>`를 출력합니다. `ok`가 아니거나 수가 현재 운영 상태와 다르면 그 백업을 쓰지 않습니다.

백업 파일에는 계정 정보가 들어 있습니다. 접근이 제한된 곳에 보관합니다.

### 복구

복구는 백엔드를 잠시 멈추므로 진단 서비스가 중단됩니다. 백업 이후의 데이터는 사라지므로, 현재 DB를 다른 파일 이름으로 먼저 백업합니다.

`cv-backup.db`를 현재 폴더에 두고 실행합니다.

```powershell
docker compose stop backend
docker run --rm --user root -v sumtong_cv-data:/data -v "${PWD}:/backup:ro" python:3.11-slim sh -c "rm -f /data/cv.db-wal /data/cv.db-shm && cp /backup/cv-backup.db /data/cv.db && chown 1000:1000 /data/cv.db"
docker compose start backend
```

복구 후 3장 확인을 수행합니다.

## 7. 버전 변경과 롤백

되돌릴 수 있는 이전 버전은 v1.1입니다. 운영에서는 `latest` 대신 `.env`의 `CV_TAG`로 버전을 고정합니다. 배포한 버전 태그는 다시 푸시하지 않습니다.

### 버전 올리기

1. 6장대로 DB를 백업합니다. 새 버전은 기동할 때 DB 구조를 바꿀 수 있습니다.
2. `.env`의 `CV_TAG`를 새 버전으로 바꿉니다. 예: `CV_TAG=v2.0`
3. `docker compose pull` 후 `docker compose up -d`를 실행합니다.
4. 3장 확인을 수행하고, 이 문서의 운영 버전을 갱신합니다.
5. 운영 서버에서 확인을 마친 뒤 Docker Hub의 `latest`를 새 버전으로 옮깁니다.

### 롤백

1. `.env`를 `CV_TAG=v1.1`로 되돌립니다.
2. `docker compose pull` 후 `docker compose up -d`를 실행합니다.
3. 3장 확인을 수행합니다. 이미지 버전의 정상 결과는 `backend-v1.1`, `frontend-v1.1`입니다.
4. 데이터까지 업그레이드 전으로 되돌릴 때만 6장대로 백업을 복구합니다.

v1.3에서 v1.1로 되돌릴 때는 DB를 복구하지 않아도 시작, 로그인, 쓰기가 정상입니다(2026-11-03 확인). 다만 v1.1은 단일 모델(두부 탐지) 기반입니다.

## 8. 민감정보

문서에는 값을 적지 않고 키 이름만 적습니다. `docker.env`와 백업 DB는 저장소나 메신저에 올리지 않습니다.

| 키 이름 | 용도 | 보관 위치 |
|---|---|---|
| `API_KEYS` | API 호출 키 | 호출 키 해시: `docker.env`. 호출 키 원문: (입력 필요) |
| `ADMIN_KEYS` | 최초 관리자 로그인. 평소에는 개인 계정 사용 | 관리자 키 해시: `docker.env`. 관리자 키 원문: (입력 필요) |
| `BIS_API_KEY` | 대전 BIS 공공 API. `EXTERNAL_PROVIDER=bis`일 때만 사용 | `docker.env` |

## 9. 교차실행 결과

- 수행 팀:
- 수행일:
- 전달한 파일:

| 순서 | 작업 | 결과 (성공/실패) | 실패 지점 | 문서 반영 내용 |
|---|---|---|---|---|
| 1 | 내리기 | | | |
| 2 | 올리기 | | | |
| 3 | 확인 | | | |
| 4 | 장애 1종 재현 | | | |
| 5 | 복구 | | | |
