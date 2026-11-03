# 숨통 Runbook 보안·검증 기록

운영 절차는 [RUNBOOK.md](RUNBOOK.md)를 봅니다. 이 문서는 버전별 확인 결과만 기록합니다.

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
