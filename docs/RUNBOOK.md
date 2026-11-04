# 숨통 운영 안내 (Runbook) — v1.5

| 항목 | 값 |
|---|---|
| 운영 버전 | `CV_TAG=v1.5` (이중 모델 + Prometheus·Grafana 모니터링 + 운영 로그) |
| 담당자 | 류재현 |
| 장애 연락처 | (입력 필요) |
| 기준일 | 2026-11-04 |

## 1. 구성

```text
web user ---- 9504 ----> frontend (nginx) ---- 9524, 9544 ----> backend
API client ---------------- 9544 -----------------------------> backend

backend ---> sumtong_cv-data volume (SQLite: /data/cv.db)
backend ---> ./models folder (이중 모델: head_crowdhuman_n1280.pt, yolo11n.pt, 사이드카 .json, read-only)

prometheus (127.0.0.1:9090) ---- 15초마다 backend:9524/metrics 수집 ----> backend
grafana    (127.0.0.1:3000) ---- 조회 ----> prometheus
```

| 항목 | 값 |
|---|---|
| 백엔드 이미지 | `hyungnss/sumtong:backend-v1.5` (`sha256:7d0bc0686d49a56d7aa28032766c22371be73055f103058a83e03089f2002bf1`) |
| 프론트엔드 이미지 | `hyungnss/sumtong:frontend-v1.5` (`sha256:4f6fe21f4bf05c4098094afbc5ade4379dc8fd570b6ab67fdd1ab32b18bc7243`) |
| 이미지 저장소 | `hyungnss/sumtong`(Docker Hub 공개 저장소). v1.2~v1.4는 팀원 저장소에 있고, 롤백 버전 v1.4는 `ryujh33/sumtong`에 있습니다. `.env`의 `CV_IMAGE`로 고릅니다 |
| 소스 | Git 태그 `v1.5` (`b856408`) |
| 모델 | 이중 융합 모델 (두부: `head_crowdhuman_n1280.pt`, 전신/거리: `yolo11n.pt` 및 `.json`). 호스트 `./models` 폴더에서 마운트 |
| 포트 | 웹 9504, API 9544 |
| 데이터 | `sumtong_cv-data` 볼륨, `/data/cv.db` |
| 운영 로그 | 같은 볼륨의 `/data/logs`에 `app.log`, `error.log`, `security.log`. 시간은 UTC. 보는 방법은 4장 |
| 설정 파일 | `docker.env`: 백엔드 설정과 키 해시. `.env`: `CV_IMAGE=hyungnss/sumtong`, `CV_TAG=v1.5`, 포트, `CV_MODELS_DIR=./models`, `GRAFANA_ADMIN_PASSWORD`, `COMPOSE_FILE` |
| 모니터링 이미지 | `prom/prometheus:v3.5.0`, `grafana/grafana:12.1.1` (`docker-compose.monitoring.yml`에 버전 고정) |
| 모니터링 포트 | Prometheus 9090, Grafana 3000. 둘 다 `127.0.0.1`에만 열려 운영 PC에서만 접속됩니다. 지표 경로 `/metrics`는 내부 포트 9524에서만 응답하고 공개 포트 9544에서는 404입니다 |
| 모니터링 데이터 | `sumtong_prom-data` 볼륨(지표, 7일 보관 후 자동 삭제), `sumtong_grafana-data` 볼륨(Grafana 계정·설정). 대시보드와 수집 설정은 `monitoring/` 폴더에서 자동 등록 |

## 2. 기동

사전 준비: Docker Desktop(메모리 4GB 이상 권장). 운영 폴더에 `docker-compose.yml`, `docker-compose.monitoring.yml`, `monitoring/` 폴더, `docker.env.example`, `models/`를 둡니다. `models/` 폴더 안에는 `head_crowdhuman_n1280.pt`와 `yolo11n.pt` 및 메타데이터 `.json` 파일이 포함되어야 합니다. 모든 명령은 이 폴더의 PowerShell에서 실행합니다. WSL에서 실행할 때는 `curl.exe` 대신 `curl`을 쓰고, `.env`는 `printf "CV_IMAGE=hyungnss/sumtong\nCV_TAG=v1.5\n" > .env`로 만듭니다.

### 처음 실행할 때

1. 이미지 저장소와 버전을 지정하고 설정 파일을 만듭니다. 값을 적어 두면 `latest`나 compose 기본값이 바뀌어도 운영 버전이 그대로 유지됩니다.

    ```powershell
    Set-Content .env "CV_IMAGE=hyungnss/sumtong","CV_TAG=v1.5" -Encoding ascii
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

4. 모니터링(Prometheus·Grafana)을 함께 켭니다. Grafana 관리자 비밀번호를 만들어 안전한 곳에 보관하고, `.env`에 두 줄을 추가합니다.

    ```powershell
    docker run --rm python:3.11-slim python -c "import secrets;print(secrets.token_urlsafe(18))"
    Add-Content .env "GRAFANA_ADMIN_PASSWORD=<만든 비밀번호>" -Encoding ascii
    Add-Content .env "COMPOSE_FILE=docker-compose.yml;docker-compose.monitoring.yml" -Encoding ascii
    docker compose config --services
    ```

    - 마지막 명령이 `backend`, `frontend`, `prometheus`, `grafana` 네 줄을 출력해야 합니다. 두 줄만 나오면 `COMPOSE_FILE`이 적용되지 않은 것입니다.
    - `COMPOSE_FILE`의 파일 구분자는 Windows(PowerShell)에서 `;`, WSL·Linux에서 `:`입니다. WSL에서는 `echo "COMPOSE_FILE=docker-compose.yml:docker-compose.monitoring.yml" >> .env`로 넣습니다.
    - `GRAFANA_ADMIN_PASSWORD`는 Grafana를 **처음** 시작할 때만 적용됩니다. 나중에 바꾸는 방법은 8장을 봅니다.
    - 모니터링 없이 운영하려면 이 단계를 건너뜁니다. 숨통 서비스에는 영향이 없습니다.

### 기동과 준비 확인

```powershell
docker compose up -d
curl.exe -s http://localhost:9544/v1/readiness
```

- 준비 완료 기준: `"readiness":"ready"`. `preparing`이면 잠시 후 다시 확인합니다.
- 다시 시작한 직후 1~2초 동안은 이전 기록 때문에 `ready`로 보일 수 있고, 이때 진단하면 `503 NOT_READY`가 나옵니다. 몇 초 뒤 다시 확인하고 진단합니다.
- 컨테이너 상태: `readiness`가 `ready`일 때만 `(healthy)`로 표시됩니다. 모델이 없어 `unavailable`이면 약 3분 뒤 `(unhealthy)`로 바뀝니다.
- 통상 소요 시간: 이미지를 받아 둔 상태에서 6~13초(2026-11-03, 35회 실측). 처음에는 이미지(백엔드 약 660MB, 모니터링 포함 시 Prometheus·Grafana 이미지 추가)를 받느라 몇 분 더 걸립니다.

### PC를 다시 켠 뒤

1. Docker Desktop을 실행하고 **Engine running**이 될 때까지 기다립니다.
2. 운영 폴더에서 컨테이너를 다시 만들어 기동합니다. 데이터 볼륨은 유지됩니다.

    ```powershell
    docker compose up -d --force-recreate
    ```

3. 3장 확인을 수행합니다. 특히 `readiness`가 `ready`인지 봅니다.

재부팅 직후에는 Docker Desktop이 폴더 연결을 제대로 잡지 못해, 컨테이너가 자동으로 다시 떠도 `models/`가 빈 폴더로 보이거나 Prometheus가 시작하지 못할 수 있습니다(5장). `--force-recreate`는 연결을 다시 잡습니다.

### 모니터링 끄기

```powershell
docker compose stop prometheus grafana
```

계속 끄려면 `.env`의 `COMPOSE_FILE` 줄을 지웁니다. 숨통 서비스(backend, frontend)에는 영향이 없습니다.

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
| 이미지 버전 | `docker compose images` | 저장소 `hyungnss/sumtong`, 태그 `backend-v1.5`, `frontend-v1.5` |
| 준비 상태, 모델 | `curl.exe -s http://localhost:9544/v1/readiness` | `"readiness":"ready"`, `"model_commit":"weights-sha256:d740367868d50137"` |
| 로그 | `docker compose logs backend` | `detector ready: dual head_crowdhuman_n1280.pt+yolo11n.pt` |
| 이중 모델 CLI 추론 | `docker compose exec backend python -m cv_api.tools.infer_dual --source samples/bus_full.jpg` | 두부 9명, 전신 7명 검출 및 거리 쌍 요약 정상 출력 |
| 웹 화면 | `http://localhost:9504` | 화면 표시 |
| API 문서 | `http://localhost:9544/docs` | Swagger 표시 |
| 모니터링 컨테이너 | `docker compose ps` | `prometheus`, `grafana` 모두 `(healthy)` |
| 지표 외부 차단 | `curl.exe -s -o NUL -w "%{http_code}" http://localhost:9544/metrics` | `404` |
| 운영 로그 | `docker compose exec backend ls /data/logs` | `app.log`, `error.log`. `security.log`는 첫 보안 기록이 생긴 뒤에 나타납니다 |
| 수집 대상 | `http://localhost:9090/targets` | `prometheus`, `sumtong-backend` 모두 **UP** |
| 대시보드 | `http://localhost:3000` (`admin` / `.env`의 비밀번호) → **Dashboards** → **숨통** → **숨통 백엔드 개요** | "백엔드 수집 상태", "검출기 준비"가 **예** |

### 샘플 동작 (시연·교차실행 환경 전용)

샘플 데이터를 넣고 시연 모드를 켜므로 실제 운영 DB에서는 실행하지 않습니다. 기준 정보를 넣은 뒤 실행하며, 마지막 줄에 `PASS`가 나오면 정상입니다. `<...>`에는 2장에서 보관한 **원문**을 넣습니다. 해시를 넣으면 인증에 실패합니다.

```powershell
docker compose exec -e CV_ADMIN_KEY=<관리자 키 원문> -e CV_API_KEY=<호출 키 원문> backend python /app/scripts/demo_prepare.py
```

## 4. 점검

| 점검 항목 | 명령 | 정상 기준 |
|---|---|---|
| 컨테이너 상태 | `docker compose ps` | 모든 서비스 `(healthy)`(모니터링 포함 시 4개). `Restarting`이 없어야 합니다 |
| 실시간 로그 | `docker compose logs -f backend` | `ERROR`가 반복되지 않아야 합니다. `Ctrl+C`로 종료합니다 |
| 오류 기록 | `docker compose exec backend tail -n 50 /data/logs/error.log` | 새 기록이 계속 늘지 않아야 합니다. 아래 "운영 로그" |
| CPU, 메모리 | `docker stats --no-stream` | 메모리가 한도에 가깝지 않아야 합니다. v1.5 운영 서버 실측(2026-11-04, 진단 후): 백엔드 약 531MiB, 프론트엔드 약 9MiB, Grafana 약 112MiB, Prometheus 약 29MiB |
| 대시보드 | Grafana **숨통 백엔드 개요** (30초마다 새로고침) | 아래 "대시보드 점검 기준" |
| 모니터링 디스크 | `docker system df -v` | `sumtong_prom-data`가 7일 보관 기준 이상으로 계속 커지지 않아야 합니다. 실측: 약 19시간 수집 후 4.5MB, `sumtong_grafana-data` 52MB |

### 운영 로그

로그는 두 곳에 남습니다. 파일 로그는 `sumtong_cv-data` 볼륨의 `/data/logs`에 저장되며, 운영 폴더에서 `ls`로는 보이지 않으므로 컨테이너를 통해 확인합니다.

| 파일 | 내용 |
|---|---|
| `app.log` | 모든 요청과 서버 시작 기록 |
| `error.log` | 5xx 오류, 모델 적재 실패, 느린 진단 |
| `security.log` | 잘못된 키, 계정 잠금과 해제. 첫 기록이 생길 때 만들어집니다 |

#### 보는 방법

```bash
# 파일 목록
docker compose exec backend ls -la /data/logs

# 최근 50줄
docker compose exec backend tail -n 50 /data/logs/app.log

# 실시간 보기 (Ctrl+C로 종료)
docker compose exec backend tail -f /data/logs/app.log

# 표준 출력 로그
docker compose logs backend
```

#### 운영 폴더로 복사하는 방법

```bash
docker compose cp backend:/data/logs ./logs-copy
```

운영 폴더에 `logs-copy` 폴더가 생깁니다. 아이디 같은 정보가 들어 있으므로 접근을 제한하고, 다 쓰면 지웁니다.

#### 언제 지워지나요

| 작업 | 파일 로그 (`/data/logs`) | 표준 출력 로그 (`docker compose logs`) |
|---|---|---|
| 컨테이너 재시작 | 남음 | 남음 |
| 컨테이너를 다시 만들기, 버전 올리기 | 남음 | **지워짐** |
| `docker compose down` | 남음 | **지워짐** |
| `docker compose down -v` | **지워짐** | **지워짐** |

- 시간은 UTC입니다. 한국 시간은 9시간을 더합니다.
- DB 백업에는 로그가 포함되지 않습니다. 보관이 필요하면 위의 복사 명령을 씁니다.
- 파일은 5MB를 넘으면 교체되고, 백업은 3개까지 남습니다.

### 대시보드 점검 기준

| 패널 | 정상 | 이상일 때 할 일 |
|---|---|---|
| 백엔드 수집 상태 | 예 | **아니오** → 5장 "수집 대상 DOWN" |
| 검출기 준비 | 예 | **아니오** → 5장 "백엔드 `(unhealthy)`, 진단 불가" |
| 최근 추론 시간 | 2초 미만(초록). 기동 직후 첫 값은 예열이라 2초를 넘을 수 있습니다(실측 3.3초) | 진단 후에도 계속 빨강이면 `docker stats`로 CPU 확인 |
| 검출기 적재 시간 | 수 초(실측 2.9초). 재시작할 때마다 갱신됩니다 | 평소보다 크게 길어지면 디스크·메모리 확인 |
| BIS 오늘 호출 수 | 하루 할당량 이내 | 할당량에 가까우면 담당자에게 알림 |
| 5분 오류 비율 (5xx) | 0% | 0%보다 크면 `docker compose logs backend`에서 `ERROR` 확인 |
| 응답 시간 p95 | 빨간 선(2초, NFR-01) 아래 | 선을 넘는 시간이 이어지면 요청 수와 CPU를 함께 확인 |
| 백엔드 메모리·CPU | 진단할 때 올라갔다가 평평하게 유지 | 내려오지 않고 계속 오르면 재시작 후 담당자에게 알림 |

진단 결과 패널은 진단 요청이 있어야 채워집니다. 기동 직후 `No data`는 정상입니다. 값이 소수로 보이는 것은 1시간 누적을 추정하는 계산 방식 때문입니다.

## 5. 장애 대응

| 증상 | 확인 방법 | 원인 | 조치 | 복구 확인 |
|---|---|---|---|---|
| 백엔드 `(unhealthy)`, 진단 불가 | `readiness`가 `unavailable`, `model_commit`이 `weights-sha256:missing`. 로그에 `detector load failed` | `models/` 폴더가 비었거나 이중 모델 파일(`head_crowdhuman_n1280.pt`, `yolo11n.pt`)이 없음 | `models/`의 이중 `.pt`, `.json`을 확인한 뒤 `docker compose up -d --force-recreate backend` | 3장 확인 |
| 로그인할 때 `로그인 실패가 많아 잠겼다` (HTTP 429) | **계정 · 키 관리**에 `잠김` 표시. `docker compose exec backend cat /data/logs/security.log`에 `login_locked` | 15분 안에 로그인 5번 실패 | 15분 뒤 자동 해제. 급하면 운영 관리자가 **잠금 해제** 버튼을 누름. 운영 관리자가 잠겼으면 관리자 키로 로그인해 해제 | 해당 계정 로그인 성공 |
| 백엔드 `(unhealthy)`, 진단 불가. 모델 파일은 있음 | `readiness`가 `unavailable`, 로그에 `detector load failed: 추론 시간 초과 (> 30.0s)` | 시작할 때 부하가 커서 모델 점검이 30초를 넘음. 실패하면 자동으로 다시 시도하지 않음 | 다른 작업이 끝난 뒤 `docker compose up -d --force-recreate backend` | 3장 확인 |
| 백엔드 `Restarting` 반복 | 로그에 `시작 거부` | `docker.env`의 `API_KEYS`, `ADMIN_KEYS`가 비었거나 기본값 | 2장대로 키를 넣고 `docker compose up -d` | 3장 확인 |
| 재부팅 후 백엔드 `(unhealthy)`, 진단 불가. 웹에 "서버를 준비하고 있으니" 표시 | `readiness`가 `unavailable`, 로그에 `detector load failed: 가중치 파일이 없다`. `docker compose exec backend ls -la /app/backend/models`는 비어 있는데 운영 폴더의 `models/`에는 파일이 있음 | 재부팅 직후 Docker Desktop이 `models/` 폴더 연결을 잃음 | `docker compose up -d --force-recreate`. 그래도 같으면 PowerShell에서 `wsl --shutdown` 후 Docker Desktop 재시작 | 3장 확인 |
| 재부팅 후 `prometheus`만 시작 실패 (`error mounting ... prometheus.yml ... not a directory`) | `monitoring/prometheus/prometheus.yml`이 파일로 있는지 확인 | 위와 같음 | `docker compose up -d --force-recreate prometheus`. 파일이 폴더로 바뀌어 있으면 그 폴더를 지우고 저장소에서 파일을 다시 받음 | `prometheus` `(healthy)` |
| 수집 대상 `sumtong-backend` **DOWN** | `http://localhost:9090/targets`의 오류 문구, `docker compose images`의 백엔드 버전 | ① 백엔드가 멈춤 ② 백엔드 이미지가 `/metrics` 미지원 버전(v1.3 이하) | ① 3장 확인부터 수행 ② `CV_TAG`를 v1.4 이상으로 올림(7장) | 대상 **UP** |
| `prometheus`, `grafana`가 목록에 없음 (`no such service`) 또는 `GRAFANA_ADMIN_PASSWORD is missing a value` | `docker compose config --services`가 두 줄 | `.env`에 `COMPOSE_FILE`이나 비밀번호 줄이 없거나 구분자가 틀림(Windows `;`, WSL `:`) | 2장 처음 실행할 때 4번대로 다시 넣음 | 네 줄 표시 |
| 9090 또는 3000 포트 사용 중 (`port is already allocated`) | 오류 문구 | 다른 Prometheus·Grafana(실습용 등)가 실행 중 | 다른 쪽을 끄거나 `.env`에 `PROM_PORT=19090`, `GRAFANA_PORT=13000`처럼 바꿈 | 바꾼 포트로 접속 |
| Grafana 로그인 실패 | `.env`의 `GRAFANA_ADMIN_PASSWORD`와 비교 | 처음 기동 이후 `.env` 값을 바꿈(바꿔도 적용되지 않음) | 8장 "Grafana 비밀번호 변경" | `admin`으로 로그인 |
| 시작 직후 로그에 `no such table` | `curl.exe -s http://localhost:9544/v1/readiness` | 새 볼륨에서 DB 준비 전에 들어온 상태 조회 | `ready`가 되면 조치 없음. 1분이 지나도 `ready`가 아니면 로그의 `startup failed` 줄을 담당자에게 전달 | `"readiness":"ready"` |

`security.log`의 시간은 UTC입니다. 한국 시간은 9시간을 더합니다. 없는 아이디는 `(없는 아이디)`로 기록되며, 해제할 계정이 없으므로 15분 뒤 자동으로 풀립니다.

## 6. 백업과 복구

> **주의:** `docker compose down -v`는 데이터 볼륨까지 지웁니다. 운영 중에는 쓰지 않습니다.

모니터링 데이터(`sumtong_prom-data`, `sumtong_grafana-data`)는 백업하지 않습니다. 지표는 7일만 보관하는 보조 자료이고, 대시보드와 수집 설정은 `monitoring/` 폴더에서 다시 만들어집니다. 모니터링 데이터만 지울 때는 볼륨을 이름으로 지정합니다.

```powershell
docker compose rm -sf prometheus grafana
docker volume rm sumtong_prom-data sumtong_grafana-data
```

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

되돌릴 버전은 v1.4입니다. 운영에서는 `latest` 대신 `.env`의 `CV_TAG`로 버전을 고정합니다. 배포한 버전 태그는 다시 푸시하지 않습니다.

### 버전 올리기

1. 6장대로 DB를 백업합니다. 새 버전은 기동할 때 DB 구조를 바꿀 수 있습니다.
2. `.env`의 `CV_TAG`를 새 버전으로 바꿉니다. 예: `CV_TAG=v2.0`
3. `docker compose pull` 후 `docker compose up -d`를 실행합니다.
4. 3장 확인을 수행하고, 이 문서의 운영 버전을 갱신합니다.
5. 운영 서버에서 확인을 마친 뒤 Docker Hub의 `latest`를 새 버전으로 옮깁니다.

### 롤백

되돌릴 버전은 v1.4입니다. v1.4는 `ryujh33/sumtong` 저장소에 있습니다.

1. 6장대로 DB를 백업합니다.
2. `.env`를 `CV_IMAGE=ryujh33/sumtong`, `CV_TAG=v1.4`로 바꿉니다.
3. `docker compose pull` 후 `docker compose up -d`를 실행합니다.
4. 3장 확인을 수행합니다. 이미지 버전의 정상 결과는 저장소 `ryujh33/sumtong`, 태그 `backend-v1.4`, `frontend-v1.4`입니다.
5. 데이터까지 업그레이드 전으로 되돌릴 때만 6장대로 백업을 복구합니다.

- `docker.env`, `models/`, 모니터링 설정은 v1.4와 v1.5가 같아 바꾸지 않습니다.
- v1.5와 v1.4를 오갈 때는 DB를 복구하지 않아도 시작, 로그인, 진단, 쓰기가 정상입니다(2026-11-04 확인).
- **v1.4에는 운영 로그 기능이 없습니다.** 되돌린 동안에는 `app.log`, `error.log`에 새 기록이 쌓이지 않고, 잘못된 키 요청도 `security.log`에 남지 않습니다. 이때는 `docker compose logs backend`로 확인합니다. 기존 로그 파일은 그대로 남고, v1.5로 돌아오면 다시 쌓입니다.
- 모니터링 이미지는 `docker-compose.monitoring.yml`에 버전이 고정되어 있어 `CV_TAG`를 바꿔도 함께 바뀌지 않습니다.
- `/metrics`가 없는 버전(v1.3 이하)으로 롤백하면 수집 대상이 **DOWN**이 됩니다. 숨통 서비스에는 영향이 없으므로 롤백 중에는 모니터링을 끄거나(2장) DOWN을 무시합니다.

v1.1로 되돌려야 할 때는 `.env`를 `CV_IMAGE=hyungnss/sumtong`, `CV_TAG=v1.1`로 바꾸고, v1.1에는 이중 모델이 없으므로 `docker.env`도 `DETECTOR=yolov8`로 바꿉니다. v1.5 데이터로 v1.1을 시작해도 DB 복구 없이 로그인과 진단이 정상입니다(2026-11-04 확인).

## 8. 민감정보

문서에는 값을 적지 않고 키 이름만 적습니다. `docker.env`와 백업 DB는 저장소나 메신저에 올리지 않습니다.

| 키 이름 | 용도 | 보관 위치 |
|---|---|---|
| `API_KEYS` | API 호출 키 | 호출 키 해시: `docker.env`. 호출 키 원문: (입력 필요) |
| `ADMIN_KEYS` | 최초 관리자 로그인. 평소에는 개인 계정 사용 | 관리자 키 해시: `docker.env`. 관리자 키 원문: (입력 필요) |
| `BIS_API_KEY` | 대전 BIS 공공 API. `EXTERNAL_PROVIDER=bis`일 때만 사용 | `docker.env` |
| `GRAFANA_ADMIN_PASSWORD` | Grafana `admin` 계정 최초 비밀번호. 처음 기동할 때만 적용 | `.env`. 원문: (입력 필요) |

### Grafana 비밀번호 변경

```powershell
docker compose exec grafana grafana cli admin reset-admin-password <새 비밀번호>
```

바꾼 뒤 `.env`의 `GRAFANA_ADMIN_PASSWORD`도 같은 값으로 고쳐 둡니다. 볼륨을 지우고 다시 만들 때 이 값이 쓰입니다.

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

## 10. 이미지 만들기와 배포 (개발 담당)

새 버전 이미지를 소스에서 만들고 확인한 뒤 Docker Hub에 올리는 절차입니다. 운영 담당은 이 장이 필요 없습니다. v1.5부터 `hyungnss/sumtong`에 올립니다. 다른 계정에 올릴 때는 아래 `hyungnss`를 그 계정으로 바꾸고 1장·2장의 `CV_IMAGE`도 함께 바꿉니다. 검증 기록은 RUNBOOK_RECORDS에 있습니다.

명령은 저장소 루트의 WSL 터미널에서 실행합니다.

### 준비

| 항목 | 내용 |
|---|---|
| 소스 | `git switch develop` → `git pull`. 이미지에 넣을 커밋을 `git rev-parse --short HEAD`로 기록 (v1.5: `b856408`) |
| 모델 | 저장소 루트 `models/`에 `head_crowdhuman_n1280.pt`, `yolo11n.pt`와 각 `.json`. `.json`은 `backend/models/`에서 복사. `yolo11n.pt`는 `yolo11n.json`의 `repo_url`에서 받음 |
| 모델 해시 | `sha256sum models/*.pt` → `head_crowdhuman_n1280.pt` `d740367868d50137…`, `yolo11n.pt` `0ebbc80d4a7680d1…` |
| `docker.env` | `DETECTOR=dual`, `MODEL_WEIGHTS=models/head_crowdhuman_n1280.pt`, `MODEL_DISTANCE_WEIGHTS=models/yolo11n.pt`, `DISTANCE_THRESHOLD=150.0`. 예전 `DETECTOR=yolov8`이 남아 있으면 이중 모델이 꺼집니다 |
| 버전 확인 | `docker manifest inspect ryujh33/sumtong:backend-<새 버전>`과 `hyungnss/sumtong:backend-<새 버전>`이 모두 `no such manifest`여야 합니다. 이미 쓴 버전 번호는 다시 쓰지 않습니다 |

### 빌드

```bash
echo "CV_IMAGE=hyungnss/sumtong" >> .env
echo "CV_TAG=<새 버전>" >> .env
echo "COMPOSE_FILE=docker-compose.yml:docker-compose.build.yml:docker-compose.monitoring.yml" >> .env
docker compose config --images
time docker compose build
```

- `.env`에 `CV_IMAGE`, `CV_TAG`, `COMPOSE_FILE`이 이미 있으면 추가하지 말고 값을 고칩니다.
- `config --images`에 `hyungnss/sumtong:backend-<새 버전>`, `frontend-<새 버전>`이 나와야 합니다. 빌드할 때 이 이름이 그대로 이미지에 붙습니다.
- 빌드 시간 실측: 캐시가 있을 때 약 9초(v1.4), `--pull --no-cache`일 때 백엔드와 프론트엔드 합쳐 약 7분(v1.5).
- 기반 이미지의 보안 패치를 반영하려면 `docker compose build --pull --no-cache`로 빌드합니다. SQLite 버전은 `docker run --rm --entrypoint sh hyungnss/sumtong:backend-<새 버전> -c "dpkg -s libsqlite3-0 | grep ^Version"`로 확인합니다.

### 확인

```bash
docker compose up -d --force-recreate
docker compose images
docker image inspect --format '{{.Id}} {{.Size}}' hyungnss/sumtong:backend-<새 버전> hyungnss/sumtong:frontend-<새 버전>
docker compose ps
curl -s http://localhost:9544/v1/readiness; echo
docker compose logs backend | grep detector | tail -3
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9544/metrics
```

정상 기준은 3장과 같습니다. 추가로 아래를 확인합니다.

- `readiness`의 `detector.kind`가 `dual`
- 9544 `/metrics`가 `404`, Prometheus 수집 대상 **UP**
- 웹에서 진단 2~3회 후 Grafana의 진단 결과 패널과 최근 추론 시간이 갱신됨
- 테스트: `python -m pytest -q` (저장소 `backend/`, Python 3.11 가상환경) 실패 0건

### 배포

이미지에는 모델(`*.pt`), `docker.env`, `.env`, DB가 들어가지 않습니다(`.dockerignore`). 그래서 공개 저장소에 올려도 됩니다.

```bash
docker login -u hyungnss
docker push hyungnss/sumtong:backend-<새 버전>
docker push hyungnss/sumtong:frontend-<새 버전>
docker buildx imagetools inspect hyungnss/sumtong:backend-<새 버전> | grep Digest
docker buildx imagetools inspect hyungnss/sumtong:frontend-<새 버전> | grep Digest
```

- `docker login`은 비밀번호 대신 Docker Hub **Personal access token**(Account settings → Personal access tokens, 권한 Read & Write)을 넣습니다.
- 처음 push하면 Docker Hub에 `sumtong` 저장소가 만들어집니다. 저장소 **Settings**에서 공개(Public)인지 확인합니다. 비공개면 다른 사람이 로그인 없이 받을 수 없습니다.
- 출력된 digest를 1장 이미지 행에 적습니다.
- 다른 PC에서 받아지는지 확인합니다: `docker manifest inspect hyungnss/sumtong:backend-<새 버전>`
- 소스 커밋에 Git 태그를 붙입니다: `git tag <새 버전> <커밋>` → `git push origin <새 버전>`.
- `latest`는 운영 서버에서 3장 확인을 마친 뒤에 옮깁니다(7장 5번).
- 배포 후 이 문서 머리말의 운영 버전과 RUNBOOK_RECORDS의 검증 기록을 갱신합니다.
