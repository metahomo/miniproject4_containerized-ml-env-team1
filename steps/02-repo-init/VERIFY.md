# 확인 방법

| 확인 항목 | 확인 명령 | 예상 결과 | 실제 검증 여부 |
|---|---|---|---|
| PR 머지 | 웹 develop 최근 커밋 | (#4) 커밋 존재 | 검증됨 |
| 이슈 자동 종료 | 웹 Issues → Closed | #3 Closed | 미검증 |
| 프롬프트 이동 | ls docs | PROMPT.md, CONTRIBUTING.md | 미검증 |
| 이름 변경 이력 | git log --follow --oneline docs/PROMPT.md | 이동 전 README 커밋까지 표시 | 미검증 |
| .env 무시 | touch .env && git status --short | .env가 표시되지 않음 | 미검증 |
| 줄바꿈 | git ls-files --eol README.md | i/lf | 미검증 |

미검증 항목은 확인 후 검증됨 / 실패(사유)로 수정한다. .env 확인 후에는 rm .env 로 지운다.
