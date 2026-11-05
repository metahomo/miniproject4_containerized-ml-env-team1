# miniproject4_containerized-ml-env-team1

컨테이너 기반 ML 개발·실행 환경 구축 — 미니 프로젝트 4, team1

**숨통**은 대중교통 영상 한 장으로 사람 수와 혼잡 등급을 알려 주는 진단 서비스입니다. 얼굴이나 신원을 다루지 않고, 판독이 불확실하면 등급 대신 `uncertain`과 경고를 돌려줍니다.

현재 버전은 **v1.5**입니다. 이미지는 `hyungnss/sumtong`에 있습니다.

## 구성

| 서비스 | 역할 | 포트 |
|---|---|---|
| `backend` | FastAPI 진단 API, 이중 모델(YOLOv8 머리 + YOLO11) CPU 추론, SQLite | 9544 (공개 API), 9524 (컨테이너 내부) |
| `frontend` | nginx + React 웹 화면, API 요청 전달 | 9504 |
| `prometheus` | 백엔드 지표 수집 (15초 간격, 7일 보관) | 9090 (서버 PC에서만) |
| `grafana` | 모니터링 대시보드 | 3000 (서버 PC에서만) |

- **데이터:** `sumtong_cv-data` 볼륨의 `/data/cv.db`, `/data/logs`
- **모델:** 이미지에 넣지 않고 `models/` 폴더를 읽기 전용으로 연결
- **비밀값:** `docker.env`, `.env`에 두고 Git에 올리지 않음

`prometheus`, `grafana`는 선택 사항입니다. 없어도 숨통 서비스는 동작합니다.

## 실행

Linux 또는 WSL의 터미널에서 실행합니다. 처음 실행하는 절차이며, 운영 절차는 [Runbook](docs/RUNBOOK.md)을 봅니다.

**준비물:** Docker와 Docker Compose, 모델 파일 `head_crowdhuman_n1280.pt`, `yolo11n.pt` (Git에 없음. 팀 드라이브에서 받음)

### 1. 코드와 모델 준비

```bash
git clone -b develop https://github.com/metahomo/miniproject4_containerized-ml-env-team1.git sumtong
cd sumtong
mkdir -p models
cp backend/models/head_crowdhuman_n1280.json backend/models/yolo11n.json models/
# 받은 .pt 파일 2개를 models/ 에 넣는다
sha256sum models/*.pt | cut -c1-16
```

`d740367868d50137`(`head_crowdhuman_n1280.pt`), `0ebbc80d4a7680d1`(`yolo11n.pt`)이 나와야 합니다.

`up`을 먼저 실행하면 Docker가 빈 `models/` 폴더를 root 권한으로 만듭니다. 모델을 넣은 뒤에 실행합니다.

### 2. 키와 설정 파일 만들기

```bash
gen() { docker run --rm python:3.11-slim python -c "import secrets,hashlib;k=secrets.token_urlsafe(24);print(k, 'sha256:'+hashlib.sha256(k.encode()).hexdigest())"; }
read -r API_RAW API_HASH <<< "$(gen)"
read -r ADMIN_RAW ADMIN_HASH <<< "$(gen)"
cp docker.env.example docker.env
sed -i "s|^API_KEYS=.*|API_KEYS=web:$API_HASH|; s|^ADMIN_KEYS=.*|ADMIN_KEYS=op1:$ADMIN_HASH|" docker.env
printf 'CV_IMAGE=hyungnss/sumtong\nCV_TAG=v1.5\nCOMPOSE_FILE=docker-compose.yml:docker-compose.monitoring.yml\nGRAFANA_ADMIN_PASSWORD=%s\n' "$(openssl rand -hex 18)" > .env
chmod 600 .env docker.env
echo "API: $API_RAW"; echo "ADMIN: $ADMIN_RAW"
```

마지막 줄의 키 원문은 다시 볼 수 없으므로 안전한 곳에 보관합니다. 저장소나 메신저에 올리지 않습니다.

실시간 버스 조회를 쓰려면 `docker.env`에 `EXTERNAL_PROVIDER=bis`와 `BIS_API_KEY`를 넣습니다. 기본값 `fixture`는 고정 데이터로 동작합니다.

### 3. 서버 실행

```bash
docker compose pull
docker compose up -d
curl -s http://localhost:9544/v1/readiness; echo
```

`"readiness":"ready"`, `"kind":"dual"`이 나오면 준비된 것입니다. `preparing`이면 잠시 후 다시 확인합니다.

### 4. 기준 정보와 시연 데이터 넣기

```bash
docker compose exec backend python -m cv_api.tools.load_reference
docker compose exec backend python -m cv_api.tools.load_reference --routes data/bis_routes.csv --stops data/bis_stops.csv
docker compose exec -e CV_ADMIN_KEY="$ADMIN_RAW" -e CV_API_KEY="$API_RAW" backend python /app/scripts/demo_prepare.py
```

마지막 명령은 `PASS`로 끝나야 합니다. **샘플 데이터를 넣고 시연 모드를 켜므로 운영 DB에서는 실행하지 않습니다.**

### 5. 사용

| 화면 | 주소 |
|---|---|
| 웹 | http://localhost:9504 |
| API 문서 (Swagger) | http://localhost:9544/docs |
| Grafana (`admin` / `.env`의 비밀번호) | http://localhost:3000 |
| Prometheus | http://localhost:9090 |

API 호출 예시입니다. `bus_full.jpg`는 `backend/samples/`에 있습니다.

```bash
curl -s -H "X-API-Key: $API_RAW" \
  -F "camera_id=CAM-DEMO-01" \
  -F "frame=@backend/samples/bus_full.jpg" \
  http://localhost:9544/v1/diagnose
```

### 6. 내리기

```bash
docker compose down
```

데이터는 볼륨에 남습니다. `docker compose down -v`는 **DB와 로그까지 지우므로** 운영 중에는 쓰지 않습니다.

## 팀

| 역할 | 담당 |
|---|---|
| Git/협업 | Park |
| Linux·자동화 | Ryu |
| Docker·Compose | Oh |
| ML·API | Lee |

## 문서

- [운영 안내 (Runbook)](docs/RUNBOOK.md): 기동, 점검, 로그, 장애 대응, 백업, 롤백, 이미지 빌드
- [검증 기록](docs/RUNBOOK_RECORDS.md)
- [도커 실행 매뉴얼](Docker_Readme.md)
- [기능 명세](specs/001-crowd-vacancy-api/spec.md)
- [학습 도구](scripts/train/README.md)
- [프로젝트 프롬프트](docs/PROMPT.md)
- [협업 규칙](docs/CONTRIBUTING.md)
- [단계별 기록](steps/)
