# miniproject4_containerized-ml-env-team1

## 미니 프로젝트 4: 컨테이너 기반 환경 구축

## 적절하게 첨삭해 주시기 바랍니다.

> 저장소: `miniproject4_containerized-ml-env-team1`
> 이 문서는 AI 어시스턴트(Claude, ChatGPT, Copilot 등)에 그대로 붙여 넣어 사용하는 프로젝트 프롬프트다.
> 용도: (A) 프로젝트 기획·설계, (B) 단계별 실습 폴더(코드·문서) 생성

---

## 1. 역할 (Role)

4인 팀이 5일 안에 "컨테이너 기반 ML 개발·실행 환경"을 구축하고 발표할 수 있도록
설계도를 작성한다. 팀원의 역할에 따라 **이슈 하나 = 단계 폴더 하나 = PR 하나** 원칙에 따라
팀원이 직접 수행하는 단계별 실습 폴더를 생성한다.

## 2. 프로젝트 맥락 (Context)

- 과정: ML 엔지니어링 교육 과정, 미니 프로젝트 4
- 팀: team1, 4명
  - A: Git/협업 리드
  - B: Linux·자동화
  - C: Docker·Compose
  - D: ML·API
- 일정 (총 5일)

| Day | 날짜 | 단계 |
|---|---|---|
| Day 1 | 10/30 (금) | 준비 1 — 저장소·협업 체계, Linux 환경 |
| Day 2 | 10/31 (토) | 준비 2 — 이미지 빌드, Compose 통합 |
| Day 3 | 11/01 (일) | 준비 3 — 영속성·자동화·보안·배포 |
| Day 4 | 11/02 (월) | 발표 준비 — 문서화, 다이어그램, 데모 리허설 |
| Day 5 | 11/03 (화) | 발표 |

- 실행 환경: Windows 호스트 + Linux(WSL2 또는 VM) + Docker
- GPU: 미확정 → **CPU 기본 구성**으로 설계하고, GPU는 Compose `profiles: [gpu]`로 선택 실행 가능하게 분리한다.

## 3. 학습 범위 (반드시 반영할 요소)

### 3-1. Git/GitHub 기반 협업과 코드 관리
- 버전 관리, 로컬/원격 저장소
- 브랜치 전략(main / develop / feature/*), 병합·충돌 해결
- 이슈·마일스톤 관리, 팀 브랜치 전략
- Pull Request와 코드 리뷰(최소 1인 승인 후 머지)
- 이력 정리(squash, rebase), 트러블슈팅, `.gitignore` 관리

### 3-2. ML 엔지니어를 위한 Linux 운영
- 파일 시스템·권한, 셸 입출력
- 프로세스·자원 관리, 네트워크 기초, SSH 원격 접속
- 패키지 관리와 Python 개발 환경
- 셸 스크립팅을 통한 반복 작업 자동화
- 시스템 모니터링·로그, GPU 운영(nvidia-smi — GPU 사용 시)

### 3-3. 컨테이너화와 Docker 실무
- 이미지·컨테이너 생명주기
- Dockerfile 작성과 빌드 최적화(멀티스테이지, 레이어 캐시, `.dockerignore`)
- 볼륨을 통한 데이터 영속성과 백업
- 컨테이너 네트워킹, 환경 변수(`.env`) 설정
- Docker Compose: 서비스 구성, `depends_on` + `healthcheck` 준비 상태 관리
- 레지스트리 공유와 이미지 태그 버전 관리(semver + git sha)
- 보안(non-root 사용자, 시크릿 분리)과 리소스 제한(cpus, memory)
- CPU 기반 ML 실행 환경·모델·데이터 관리
- GPU 컨테이너와 ML 프레임워크(선택)

### 3-4. 컨테이너 기반 ML 시스템 운영
<!-- TODO: 교수님 제공 후 세부 항목 추가 -->
- (추후 추가 예정)
- 이 섹션이 채워지면 (1) 기존 단계 중 영향받는 단계, (2) 새로 추가할 단계 폴더(13번 이후)를 제시하라.

## 4. 목표 시스템 (기본안 — 팀 합의로 변경 가능)

Docker Compose 하나로 다음 서비스를 기동하는 ML 환경:

1. `trainer` — 학습 컨테이너(scikit-learn 또는 PyTorch CPU), 모델 아티팩트를 볼륨에 저장
2. `api` — 추론 API(FastAPI), 저장된 모델을 로드해 `/predict`, `/health` 제공
3. `db` — 예측 로그 저장(PostgreSQL 또는 MySQL)
4. `notebook` (선택) — Jupyter 개발 환경
5. `trainer-gpu` (선택, `profiles: [gpu]`) — GPU 학습

공통 요구:
- `make` 또는 셸 스크립트로 `build / up / down / logs / backup / test` 자동화
- 모든 서비스에 healthcheck 정의
- 모델·데이터·DB는 named volume으로 영속화하고 백업 스크립트 제공
- 이미지를 레지스트리(Docker Hub 또는 GHCR)에 태그 규칙에 따라 푸시

## 5. 단계 목록

| 단계 폴더 | 내용 | 대응 모듈 | 담당 | Day |
|---|---|---|---|---|
| 01-issue-template | 이슈·PR 템플릿(`.github/`), 라벨 체계 | 3-1 | A | 1 |
| 02-repo-init | README 골격, `.gitignore`, 브랜치 전략, 커밋 규칙 | 3-1 | A | 1 |
| 03-linux-env | WSL 설정, 권한, Python 환경 점검 스크립트 | 3-2 | B | 1 |
| 04-trainer-image | 학습 코드와 Dockerfile(멀티스테이지), `.dockerignore` | 3-3 | D | 2 |
| 05-api-image | FastAPI 추론 서버와 Dockerfile | 3-3 | D | 2 |
| 06-compose-db | Compose, DB, 네트워크, healthcheck, `.env.example` | 3-3 | C | 2 |
| 07-volume-backup | named volume, 백업·복원 스크립트 | 3-2, 3-3 | C | 3 |
| 08-automation-monitoring | Makefile, 로그·자원 모니터링 스크립트 | 3-2 | B | 3 |
| 09-security-resources | non-root, 시크릿 분리, 리소스 제한 | 3-3 | C | 3 |
| 10-registry-release | 이미지 태깅, GHCR/Docker Hub 푸시 | 3-1, 3-3 | A | 3 |
| 11-gpu-profile (선택) | GPU 프로필, nvidia-smi 확인 | 3-2, 3-3 | D | 3 |
| 12-docs-demo | 최종 README, PlantUML 아키텍처, 데모 시나리오 | 전체 | A(리드)+전원 | 4 |
| 13~ (예약) | 3-4 모듈 내용 — 교수님 제공 후 추가 | 3-4 | 미정 | 미정 |

원칙:
- 모든 팀원이 최소 1개 PR 작성, 1개 리뷰 수행
- 단계는 번호 순서대로 머지하며, 각 단계는 이전 단계의 `completed/` 위에서 시작한다.

## 6. 단계 폴더 구조 (필수 형식)

각 단계는 아래 구조로 생성한다. **9개 항목 모두 필수이며 생략하지 않는다.**

```
NN-slug/
├── README.md          # 목표·선행 조건·직접 진행할 순서
├── ISSUE.md           # 직접 등록할 이슈 제목과 본문
├── GUIDE.md           # 명령어와 작업 방법, 각 명령어의 의미
├── changes/           # 이번 단계에서 추가·수정할 파일
├── completed/         # 이번 단계까지 반영된 누적 완성본
├── EXPLANATION.md     # 파일별 역할과 설계 이유
├── VERIFY.md          # 확인 방법·예상 결과·실제 검증 여부
├── COMMIT_MESSAGE.txt # 커밋 메시지 예시
└── PR.md              # 직접 작성할 PR 예시
```

### 6-1. 항목별 작성 규칙

**README.md**
- 이번 단계의 목표(1~3줄), 담당자, 대응 학습 모듈
- 선행 조건: 이전 단계 번호, 필요한 도구와 버전
- 직접 진행할 순서: 번호 목록(브랜치 생성 → 파일 반영 → 검증 → 커밋 → 푸시 → PR)

**ISSUE.md**
- 이슈 제목: `[NN] 동사형 요약` (예: `[06] Compose로 api·db 서비스 연결`)
- 본문: 배경, 할 일 체크리스트, 완료 조건(Definition of Done), 라벨, 마일스톤, 담당자

**GUIDE.md**
- 실행 순서대로 명령어를 코드 블록으로 제시
- 각 명령어 아래에 의미와 주요 옵션 설명
- Windows + WSL2 주의점(경로, 줄바꿈 LF, 권한, Docker Desktop 연동)을 해당 위치에 명시

**changes/**
- 이번 단계에서 새로 만들거나 수정하는 파일만, 저장소 루트 기준 경로를 유지해 배치
- 수정 파일은 변경 후 전체 내용을 넣는다(부분 diff 금지)

**completed/**
- 이전 단계 `completed/` + 이번 단계 `changes/`를 합친 **저장소 전체 스냅샷**
- 이 폴더만 복사해도 해당 단계까지 그대로 실행되어야 한다

**EXPLANATION.md**
- 파일별 표: 파일 경로 | 역할 | 설계 이유 | 대안과 선택하지 않은 이유
- 구조나 흐름 설명이 필요하면 PlantUML 코드 블록 사용

**VERIFY.md**
- 표: 확인 항목 | 확인 명령 | 예상 결과 | 실제 검증 여부
- 실제 검증 여부는 `검증됨` / `미검증` / `실패(사유)` 중 하나로 표기
- AI가 직접 실행하지 않은 항목은 반드시 `미검증`으로 표기한다(추정으로 `검증됨` 표기 금지)

**COMMIT_MESSAGE.txt**
- Conventional Commits 형식: `type(scope): 요약` + 빈 줄 + 본문 + `Refs: #이슈번호`
- 커밋을 나눌 경우 여러 개를 순서대로 제시

**PR.md**
- PR 제목, 대상 브랜치(feature/NN-slug → develop)
- 본문: 변경 요약, 관련 이슈(`Closes #`), 검증 결과(VERIFY.md 요약), 스크린샷/로그 자리, 리뷰어 체크리스트

### 6-2. 공통 규칙
- 모든 파일은 **전체 내용**을 작성한다("...", "생략", "기존과 동일" 금지).
- 각 파일 앞에 경로를 명시한다.
- 비밀값은 하드코딩하지 않고 `.env.example`로 분리한다.
- 브랜치명: `feature/NN-slug`, 이슈 라벨과 마일스톤(Day 1~4)을 일관되게 사용한다.
- 출력이 길면 단계 폴더 단위로 나누어 출력하고, 중간에 끊기면 끊긴 파일부터 이어서 출력한다.

## 7. 작업 모드

### 모드 A — 기획·설계
요청 시 다음을 산출한다.
1. 아키텍처 개요와 PlantUML 다이어그램(컴포넌트·네트워크·볼륨)
2. 최종 저장소 디렉터리 구조(tree)
3. 5절 단계 목록 검토와 조정안(담당·일정 포함)
4. 리스크와 대응(GPU 미지원, 포트 충돌, WSL 볼륨 권한, 일정 지연 등)
5. 학습 범위(3-1 ~ 3-4) 대비 단계별 반영 체크리스트

### 모드 B — 단계 폴더 생성
"NN 단계 생성"과 같은 요청을 받으면 6절 형식에 따라 해당 단계 폴더 전체를 생성한다.
- 이전 단계의 `completed/`를 기준으로 작성한다. 이전 단계 내용이 대화에
