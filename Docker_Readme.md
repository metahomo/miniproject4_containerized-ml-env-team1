# 숨통(sumtong) — 도커로 실행하기

대전 대중교통 **군중 밀집도·잔여 탑승 공간 진단 서비스**를 내 PC에서 도커로 띄우는 안내입니다.
소스 코드나 Python·Node 설치 없이 **Docker만 있으면** 됩니다.

> 화면에 나오는 혼잡도·잔여 공간 수치는 영상 프레임을 바탕으로 한 **통계적 추정치**입니다.

---

## 1. 준비물

| 준비물 | 받는 곳 / 하는 일 |
|---|---|
| **Docker Desktop** | https://www.docker.com/products/docker-desktop/ 에서 설치 (Windows · Mac · Linux). 메모리는 **4GB 이상** 할당 권장 |
| **파일 2개** (전달자에게 받음) | `docker-compose.yml`, `docker.env.example` |
| **모델 폴더** (드라이브로 받음) | `models` 폴더 — 안에 `head_crowdhuman_n1280.pt`, `head_crowdhuman_n1280.json` |

> 모델 파일은 라이선스(AGPL-3.0 · CrowdHuman CC BY-NC 4.0) 확인 중이라 **다른 곳에 다시 배포하지 마세요.**

---

## 2. 폴더 만들기

아무 곳에 폴더를 하나 만들고(예: `sumtong`), 받은 파일을 아래처럼 둡니다.

```
sumtong/
├─ docker-compose.yml
├─ docker.env.example
└─ models/
   ├─ head_crowdhuman_n1280.pt
   └─ head_crowdhuman_n1280.json
```

받은 모델 파일이 맞는지 확인하려면(선택) — 값이 아래와 같아야 합니다.

```powershell
# Windows PowerShell
Get-FileHash models\head_crowdhuman_n1280.pt -Algorithm SHA256
# Mac / Linux
shasum -a 256 models/head_crowdhuman_n1280.pt
```
`D740367868D50137FCAEDD2EA55086C58395249FC28A82026109A45FE6D9B75A`

이후 명령은 모두 **이 폴더 안에서** 실행합니다 (PowerShell 또는 터미널에서 `cd sumtong`).

---

## 3. 설정 파일(docker.env) 만들기

### 3-1. 복사

```powershell
# Windows PowerShell
Copy-Item docker.env.example docker.env
# Mac / Linux
cp docker.env.example docker.env
```

### 3-2. 키 두 개 만들기

서비스에는 키가 두 개 필요합니다.

| 키 | 용도 |
|---|---|
| **관리자 키** (`ADMIN_KEYS`) | 처음 웹에 들어가 운영 관리자가 될 때 씀 |
| **호출 키** (`API_KEYS`) | 시연 데이터 넣기 등 스크립트용 |

아래 명령을 **두 번** 실행합니다 (Python이 없어도 도커로 돕니다).

```powershell
docker run --rm python:3.11-slim python -c "import secrets,hashlib;k=secrets.token_urlsafe(24);print(k, 'sha256:'+hashlib.sha256(k.encode()).hexdigest())"
```

한 줄에 두 값이 나옵니다.

```
Xy3k...원문키...   sha256:9f2a...해시...
└ 원문 키 (내가 보관) ┘ └ docker.env 에 넣을 값 ┘
```

- **원문 키**는 메모장 등에 따로 보관하세요. 다시 볼 수 없습니다. (관리자 키 원문은 4·5단계에서 씁니다)
- `docker.env`를 열어 비어 있는 두 줄을 채웁니다. **`sha256:...` 부분**을 넣습니다.

```
API_KEYS=web:sha256:<첫 번째 해시>
ADMIN_KEYS=op1:sha256:<두 번째 해시>
```

> 키를 비워 두거나 예시 키(`changeme-…`)를 쓰면 **서버가 시작을 거부**합니다. 누구나 아는 키로 관리자가 되는 것을 막기 위해서입니다.

나머지 값은 그대로 두면 됩니다. 이미 도커에 맞게 채워져 있습니다.

---

## 4. 실행

```powershell
docker compose up -d
```

처음에는 이미지(약 650MB)를 내려받느라 몇 분 걸립니다. 상태 확인:

```powershell
docker compose ps
```

두 줄 모두 `(healthy)` 가 되면 준비 완료입니다. 모델을 올리는 데 **20초~1분** 정도 걸립니다.

| 주소 | 내용 |
|---|---|
| http://localhost:9504 | **웹 화면** |
| http://localhost:9544/docs | API 명세 (Swagger) |

같은 네트워크의 다른 PC에서는 `http://<이 PC의 IP>:9504` 로 접속합니다. (방화벽에서 9504·9544 포트 허용 필요)

---

## 5. 처음 한 번만 할 일

처음 실행하면 데이터베이스가 **비어 있는 상태로 자동 생성**됩니다. 아래 순서로 채웁니다.

### 5-1. 노선·정류장 기준 정보 넣기

```powershell
docker compose exec backend python -m cv_api.tools.load_reference
docker compose exec backend python -m cv_api.tools.load_reference --routes data/bis_routes.csv --stops data/bis_stops.csv
```
두 번째 명령이 `{'routes': 141, 'stops': 10533}` 을 출력하면 정상입니다.

### 5-2. 운영 관리자 계정 만들기

1. http://localhost:9504 접속 → **회원가입** 으로 내 계정을 만듭니다. (처음에는 '일반 사용자')
2. 로그아웃 → 로그인 화면 아래쪽의 작은 **관리자 키** 를 눌러 3-2에서 보관한 **관리자 키 원문**으로 로그인합니다.
3. 왼쪽 메뉴 **계정 · 키 관리** → 방금 만든 내 계정의 역할을 **운영 관리자** 로 바꿉니다.
4. 로그아웃 → 내 아이디·비밀번호로 다시 로그인합니다. 이제 모든 메뉴를 쓸 수 있습니다.

> 관리자 키는 처음 설정용입니다. 평소에는 내 계정으로 로그인하세요.

### 5-3. 시연 데이터 넣기 (선택)

카메라 3대·ROI·정원·차량 연결·시연 프레임까지 한 번에 넣습니다. `<...>` 에 3-2의 **원문 키**를 넣습니다.

```powershell
docker compose exec -e CV_ADMIN_KEY=<관리자 키 원문> -e CV_API_KEY=<호출 키 원문> backend python /app/scripts/demo_prepare.py
```
마지막 줄에 `PASS` 가 나오면 성공입니다. 웹의 **버스 조회** 화면에서 결과를 볼 수 있습니다.

> Windows의 **Git Bash** 에서는 경로가 바뀌어 실패할 수 있습니다. PowerShell을 쓰거나, Git Bash라면 명령 앞에 `MSYS_NO_PATHCONV=1` 을 붙이세요.

---

## 6. 평소 사용

| 하고 싶은 것 | 명령 |
|---|---|
| 끄기 | `docker compose down` |
| 다시 켜기 | `docker compose up -d` |
| 로그 보기 | `docker compose logs -f backend` (끝내기: Ctrl+C) |
| 새 버전 받기 | `docker compose pull` 후 `docker compose up -d` |

- 데이터(계정·카메라·진단 기록)는 `sumtong_cv-data` 라는 도커 볼륨에 저장되어 **껐다 켜도, 새 버전으로 바꿔도 남습니다.**
- PC를 재부팅해도 Docker Desktop이 켜지면 서비스가 자동으로 다시 올라옵니다.

> ⚠️ **`docker compose down -v`** 의 `-v` 는 데이터 볼륨까지 지웁니다. 계정·기록이 모두 사라지니 처음부터 다시 시작할 때만 쓰세요.

### 데이터 백업

```powershell
docker compose stop backend
docker compose cp backend:/data/cv.db ./cv-backup.db
docker compose start backend
```
서버를 잠시 멈춘 뒤 복사해야 파일이 온전합니다.

---

## 7. 선택 설정

`docker.env` 를 고친 뒤 `docker compose up -d` 를 다시 실행하면 반영됩니다.

| 하고 싶은 것 | 설정 |
|---|---|
| 실제 대전 버스 운행 정보 쓰기 | `EXTERNAL_PROVIDER=bis`, `BIS_API_KEY=<공공데이터포털에서 받은 인증키>` (기본값 `fixture` 는 고정 예시 데이터) |
| 인원 세기 기준 조정 | `COUNT_CONF_MIN` (기본 0.2 — 머리 검출 모델 기준. 운영 중에는 웹의 등급 기준 화면에서 조정) |

포트·모델 위치는 이 폴더에 `.env` 파일을 만들어 바꿀 수 있습니다 (`docker.env` 와 다른 파일입니다).

```
CV_WEB_PORT=8504      # 웹 포트 (기본 9504)
CV_API_PORT=8544      # API 포트 (기본 9544)
CV_MODELS_DIR=./models
```

---

## 8. 문제 해결

| 증상 | 원인 · 해결 |
|---|---|
| `env file ... docker.env not found` | 3-1을 안 했습니다. `docker.env` 를 만드세요 |
| `pull access denied` / `manifest unknown` | 이미지 이름·태그가 다릅니다. `docker-compose.yml` 을 고치지 않았는지, 이 폴더에 `.env` 로 `CV_IMAGE`·`CV_TAG` 를 바꾸지 않았는지 확인하세요 |
| backend가 바로 꺼지고 로그에 `시작 거부` | `docker.env` 의 `API_KEYS`·`ADMIN_KEYS` 가 비었거나 예시 키입니다 (3-2) |
| `port is already allocated` | 9504·9544를 다른 프로그램이 쓰고 있습니다. 7단계처럼 포트를 바꾸세요 |
| 웹에서 `502` 오류 | 백엔드가 아직 모델을 올리는 중입니다. 1분쯤 기다리세요. 계속되면 `docker compose logs backend` |
| 진단 결과가 나오지 않고 준비 상태가 `ready` 가 안 됨 | `models` 폴더에 `.pt`·`.json` 이 제대로 있는지, 폴더 위치가 `docker-compose.yml` 옆인지 확인하세요 |
| 시연 스크립트에서 `ROUTE_NOT_FOUND` | 5-1(기준 정보 넣기)을 먼저 하세요 |
| Apple Silicon Mac에서 이상 동작 | arm64 이미지는 아직 실행 검증이 덜 됐습니다. `docker compose logs backend` 내용을 전달자에게 보내 주세요 |

문의할 때는 `docker compose ps` 와 `docker compose logs backend --tail 50` 결과를 함께 보내 주시면 빠릅니다.
(로그에는 키나 원본 영상이 남지 않습니다.)
